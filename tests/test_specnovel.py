"""Tests for scripts/specnovel.py (standard library unittest; run: python -m unittest discover tests)."""
import io
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import specnovel  # noqa: E402

CHAR = """\
# CHR-001: Elena Voss
- **Role:** Protagonist
- **Relationships:** sister of [[CHR-002]]
"""
CHAR2 = "# CHR-002: Karl Voss\n- **Role:** Brother\n"
PLACE = "# PLC-001: Hamburg harbor\n- **Type:** port\n- **Facts:** [[FCT-001]]\n"
FACTS = """\
# Shipping facts

## FCT-001: Example fact
**Statement:** Something true.
**Sources:**
- [[SRC-001]], p. 4
"""
SOURCES = """\
## SRC-001: Example primary source
- **Type:** primary
- **URL:** https://example.org/doc
- **Accessed:** 2026-10-23
"""
OUTLINE = """\
# Outline

## PRT-001: Departure

### CHP-001: The Letter
POV: [[CHR-001]]

#### SCN-001: Elena receives the letter
- **Where:** [[PLC-001]]
- **Cast:** [[CHR-001]]
- **Target words:** 2000

#### SCN-002: Karl refuses
- **Cast:** [[CHR-002]]
- **Facts:** [[FCT-001]]
- **Target words:** 1500

### CHP-002: The Ship

#### SCN-003: Boarding
- **Where:** [[PLC-001]]
"""
ABRIDGED_1 = """\
# CHP-001: The Letter

## SCN-001: Elena receives the letter
Elena opens the letter at the harbor. "It's from Karl," she says.

## SCN-002: Karl refuses
Karl refuses to come.
"""


class ProjectTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.run_cli("init")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "Test")
        self.write("story/synopsis.md", "---\ntitle: The Crossing\n---\n# Synopsis\n" + "word " * 50)
        self.write("story/style.md", "# Style\n" + "rule " * 500)
        self.write("kb/characters/CHR-001-elena.md", CHAR)
        self.write("kb/characters/CHR-002-karl.md", CHAR2)
        self.write("kb/places/PLC-001-harbor.md", PLACE)
        self.write("kb/facts/shipping.md", FACTS)
        self.write("kb/sources/bibliography.md", SOURCES)
        self.write("outline/outline.md", OUTLINE)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(text), encoding="utf-8")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True, check=True).stdout

    def run_cli(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = specnovel.main(["-C", str(self.root), *args])
        return code, buf.getvalue()

    def json_cli(self, *args):
        code, out = self.run_cli(*args, "--json")
        return code, json.loads(out)

    # ---------------------------------------------------------------- tests
    def test_init_scaffolds_templates(self):
        for rel in ("story/brief.md", "outline/outline.md", "kb/facts/.gitkeep", "manuscript/.gitkeep"):
            self.assertTrue((self.root / rel).exists(), rel)
        self.assertIn("build/", (self.root / ".gitignore").read_text())

    def test_check_ok(self):
        code, res = self.json_cli("check")
        self.assertEqual(res["errors"], [])
        self.assertEqual(code, 0)

    def test_dangling_reference_and_unsourced_fact(self):
        self.write("kb/facts/more.md", "## FCT-002: Unsourced\n**Statement:** x [[PLC-009]]\n")
        code, res = self.json_cli("check")
        self.assertEqual(code, 1)
        joined = "\n".join(res["errors"])
        self.assertIn("dangling reference [[PLC-009]]", joined)
        self.assertIn("fact FCT-002 does not cite any", joined)

    def test_duplicate_ids(self):
        self.write("kb/characters/dupe.md", "# CHR-001: Someone else\n")
        _, res = self.json_cli("check")
        self.assertTrue(any("duplicate ID CHR-001" in e for e in res["errors"]))

    def test_source_without_url_or_citation(self):
        self.write("kb/sources/bad.md", "## SRC-002: Mystery\n- **Type:** secondary\n")
        _, res = self.json_cli("check")
        self.assertTrue(any("SRC-002 has neither" in e for e in res["errors"]))

    def test_next_id_respects_history(self):
        self.assertEqual(self.run_cli("next-id", "CHR")[1].strip(), "CHR-003")
        self.run_cli("accept", "--stage", "plan", "-m", "plan")
        (self.root / "kb/characters/CHR-002-karl.md").unlink()
        self.assertEqual(self.run_cli("next-id", "CHR")[1].strip(), "CHR-003")
        self.assertEqual(self.run_cli("next-id", "TML")[1].strip(), "TML-001")

    def test_trace(self):
        _, res = self.json_cli("trace", "PLC-001")
        self.assertEqual([s["id"] for s in res["scenes"]], ["SCN-001", "SCN-003"])
        _, res = self.json_cli("trace", "CHR-001")  # chapter-level POV reaches both scenes of CHP-001
        self.assertEqual([s["id"] for s in res["scenes"]], ["SCN-001", "SCN-002"])

    def test_abridged_order_and_placement(self):
        self.write("abridged/CHP-001.md", "# CHP-001: The Letter\n\n## SCN-002: Karl\nx\n\n## SCN-001: Elena\ny\n")
        _, res = self.json_cli("check")
        self.assertTrue(any("scene order in CHP-001" in e for e in res["errors"]))
        self.write("abridged/CHP-001.md", "# CHP-002: The Ship\n\n## SCN-001: Elena\ny\n")
        _, res = self.json_cli("check")
        self.assertTrue(any("outline places it in CHP-001" in e for e in res["errors"]))

    def test_impact_flow(self):
        _, imp = self.json_cli("impact", "--stage", "abridged")
        self.assertEqual([s["id"] for s in imp["scenes"]], ["SCN-001", "SCN-002", "SCN-003"])
        self.write("abridged/CHP-001.md", ABRIDGED_1)
        self.write("abridged/CHP-002.md", "# CHP-002: The Ship\n\n## SCN-003: Boarding\nThey board.\n")
        code, _ = self.run_cli("accept", "--stage", "plan", "--stage", "abridged", "-m", "first draft")
        self.assertEqual(code, 0)
        _, imp = self.json_cli("impact", "--stage", "abridged")
        self.assertEqual(imp["scenes"], [])
        # change a fact -> only SCN-002 references it directly
        self.write("kb/facts/shipping.md", FACTS.replace("Something true.", "Something else true."))
        _, imp = self.json_cli("impact", "--stage", "abridged")
        self.assertEqual([s["id"] for s in imp["scenes"]], ["SCN-002"])
        self.assertIn("references changed FCT-001", imp["scenes"][0]["reasons"][0])
        # manuscript stage: everything unwritten; abridged change marks scene
        _, imp = self.json_cli("impact", "--stage", "manuscript")
        self.assertEqual(len(imp["scenes"]), 3)

    def test_manuscript_style_change_is_global(self):
        for layer in ("abridged", "manuscript"):
            self.write(f"{layer}/CHP-001.md", ABRIDGED_1)
            self.write(f"{layer}/CHP-002.md", "# CHP-002: The Ship\n\n## SCN-003: Boarding\nThey board.\n")
        self.run_cli("accept", "--stage", "all", "-m", "all")
        self.write("story/style.md", "# Style\n" + "rule " * 500 + "\n\n## Dialogue\nSaid only.\n")
        _, imp = self.json_cli("impact", "--stage", "manuscript")
        self.assertTrue(any("style guide" in g for g in imp["global"]))
        _, imp = self.json_cli("impact", "--stage", "abridged")
        self.assertFalse(any("style" in g for g in imp["global"]))

    def test_moved_scene(self):
        self.write("abridged/CHP-001.md", ABRIDGED_1)
        self.write("abridged/CHP-002.md", "# CHP-002: The Ship\n\n## SCN-003: Boarding\nThey board.\n")
        self.run_cli("accept", "--stage", "plan", "--stage", "abridged")
        # move SCN-002 from CHP-001 to the end of CHP-002
        block = "#### SCN-002: Karl refuses\n- **Cast:** [[CHR-002]]\n- **Facts:** [[FCT-001]]\n- **Target words:** 1500\n"
        moved = OUTLINE.replace(block, "") + "\n" + block
        self.write("outline/outline.md", moved)
        _, imp = self.json_cli("impact", "--stage", "abridged")
        reasons = {s["id"]: s["reasons"] for s in imp["scenes"]}
        self.assertIn("moved from CHP-001 to CHP-002", reasons["SCN-002"])

    def test_stats_and_compile(self):
        self.write("manuscript/CHP-001.md", ABRIDGED_1.replace("## SCN-002", "<!-- note [[CHR-002]] -->\n## SCN-002"))
        _, st = self.json_cli("stats")
        self.assertEqual(st["totals"]["target"], 3500)
        self.assertGreater(st["totals"]["manuscript"], 10)
        code, out = self.run_cli("compile")
        self.assertEqual(code, 0)
        book = (self.root / "build/manuscript.md").read_text(encoding="utf-8")
        self.assertIn('title: "The Crossing"', book)
        self.assertIn("# Part One: Departure", book)
        self.assertIn("## Chapter One: The Letter", book)
        self.assertIn("* * *", book)
        self.assertNotIn("SCN-", book)
        self.assertNotIn("<!--", book)

    def test_status_and_index(self):
        code, res = self.json_cli("status")
        self.assertEqual(code, 0)
        self.assertEqual(res["scenes"]["outline"], 3)
        self.run_cli("index")
        idx = (self.root / "kb/INDEX.md").read_text(encoding="utf-8")
        self.assertIn("| CHR-001 | Elena Voss |", idx)
        _, res = self.json_cli("check")  # INDEX.md must not create duplicates
        self.assertEqual(res["errors"], [])

    def test_fenced_examples_are_ignored(self):
        self.write("kb/README.md", "# KB\n```markdown\n# CHR-001: Example\n[[CHR-999]]\n```\n")
        _, res = self.json_cli("check")
        self.assertEqual(res["errors"], [])


if __name__ == "__main__":
    unittest.main()
