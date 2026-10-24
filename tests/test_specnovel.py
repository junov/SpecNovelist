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
- **Prerequisites:** [[SCN-001]]
- **Cast:** [[CHR-002]]
- **Facts:** [[FCT-001]]
- **Target words:** 1500

### CHP-002: The Ship

#### SCN-003: Boarding
- **Prerequisites:** [[SCN-002]]
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
        # move SCN-002 from CHP-001 into CHP-002 before SCN-003
        block = "#### SCN-002: Karl refuses\n- **Prerequisites:** [[SCN-001]]\n- **Cast:** [[CHR-002]]\n- **Facts:** [[FCT-001]]\n- **Target words:** 1500\n"
        moved = OUTLINE.replace(block, "").replace("### CHP-002: The Ship\n", "### CHP-002: The Ship\n\n" + block)
        self.write("outline/outline.md", moved)
        _, imp = self.json_cli("impact", "--stage", "abridged")
        reasons = {s["id"]: s["reasons"] for s in imp["scenes"]}
        self.assertIn("moved from CHP-001 to CHP-002", reasons["SCN-002"])

    def test_dag_valid(self):
        code, out = self.run_cli("dag")
        self.assertEqual(code, 0)
        self.assertIn("[OK] Acyclic Check", out)
        self.assertIn("[OK] Reading Order Coherence", out)
        self.assertIn("[OK] Essentiality Check", out)
        self.assertIn("SCN-003", out)

        # test json output
        code, res = self.json_cli("dag")
        self.assertEqual(code, 0)
        self.assertTrue(res["ok"])
        self.assertEqual(res["root"], "SCN-003")
        self.assertEqual(res["cycles"], [])
        self.assertEqual(res["readingOrderErrors"], [])
        self.assertEqual(res["essentialityErrors"], [])

        # test mermaid output
        code, out = self.run_cli("dag", "--mermaid")
        self.assertEqual(code, 0)
        self.assertIn("graph TD", out)
        self.assertIn("SCN-001 --> SCN-002", out)
        self.assertIn("SCN-002 --> SCN-003", out)

    def test_dag_cycle_detection(self):
        # Create a cycle: SCN-001 requires SCN-003
        cycled_outline = OUTLINE.replace(
            "#### SCN-001: Elena receives the letter\n",
            "#### SCN-001: Elena receives the letter\n- **Prerequisites:** [[SCN-003]]\n"
        )
        self.write("outline/outline.md", cycled_outline)
        code, res = self.json_cli("check")
        self.assertEqual(code, 1)
        self.assertTrue(any("cycle detected in story causality graph" in e for e in res["errors"]))
        code, res = self.json_cli("dag")
        self.assertEqual(code, 1)
        self.assertFalse(res["ok"])
        self.assertTrue(len(res["cycles"]) > 0)

    def test_dag_reading_order_violation(self):
        # Make SCN-001 require SCN-002 (which appears later in the outline)
        bad_outline = OUTLINE.replace(
            "#### SCN-001: Elena receives the letter\n",
            "#### SCN-001: Elena receives the letter\n- **Prerequisites:** [[SCN-002]]\n"
        ).replace(
            "#### SCN-002: Karl refuses\n- **Prerequisites:** [[SCN-001]]\n",
            "#### SCN-002: Karl refuses\n"
        )
        self.write("outline/outline.md", bad_outline)
        code, res = self.json_cli("check")
        self.assertEqual(code, 1)
        self.assertTrue(any("reading order violation" in e for e in res["errors"]))

    def test_dag_inessential_element(self):
        # Add SCN-004 that does not lead to SCN-003 (denouement)
        dead_end_outline = OUTLINE + """\
#### SCN-004: Detour
- **Prerequisites:** [[SCN-001]]
- **Where:** [[PLC-001]]
"""
        # Explicitly mark SCN-003 as the root denouement
        dead_end_outline = dead_end_outline.replace(
            "#### SCN-003: Boarding\n",
            "#### SCN-003: Boarding\n- **Denouement:** true\n"
        )
        self.write("outline/outline.md", dead_end_outline)
        code, res = self.json_cli("check")
        self.assertEqual(code, 1)
        self.assertTrue(any("inessential element: SCN-004 has no causal path to the root denouement (SCN-003)" in e for e in res["errors"]))

    def test_dag_with_plot_element_prerequisites(self):
        # Add a plot element with prerequisites and valid time/place metadata that is advanced in scenes
        self.write(
            "kb/plot/PLT-001-escape.md",
            "# PLT-001: The Escape\n- **Time:** April 1912\n- **Place:** [[PLC-001]]\n- **Prerequisites:** [[FCT-001]]\n"
        )
        plot_outline = OUTLINE.replace(
            "#### SCN-002: Karl refuses\n- **Prerequisites:** [[SCN-001]]\n",
            "#### SCN-002: Karl refuses\n- **Prerequisites:** [[SCN-001]], [[PLT-001]]\n- **Plot:** [[PLT-001]]\n"
        )
        self.write("outline/outline.md", plot_outline)
        code, res = self.json_cli("check")
        self.assertEqual(code, 0)
        self.assertEqual(res["errors"], [])
        code, dag_res = self.json_cli("dag")
        self.assertEqual(code, 0)
        self.assertIn("PLT-001", dag_res["nodes"])
        self.assertIn("FCT-001", dag_res["nodes"])

    def test_plt_missing_time_metadata(self):
        self.write("kb/plot/PLT-001-escape.md", "# PLT-001: The Escape\n- **Place:** [[PLC-001]]\n")
        code, res = self.json_cli("check")
        self.assertEqual(code, 1)
        self.assertTrue(any("plot element PLT-001 is missing valid time metadata" in e for e in res["errors"]))

    def test_plt_missing_place_metadata(self):
        self.write("kb/plot/PLT-001-escape.md", "# PLT-001: The Escape\n- **Time:** 1912-04-12\n")
        code, res = self.json_cli("check")
        self.assertEqual(code, 1)
        self.assertTrue(any("plot element PLT-001 is missing valid place metadata" in e for e in res["errors"]))

    def test_plt_placeholder_metadata_fails(self):
        self.write("kb/plot/PLT-001-escape.md", "# PLT-001: The Escape\n- **Time:** <e.g. 1912>\n- **Place:** <location>\n")
        code, res = self.json_cli("check")
        self.assertEqual(code, 1)
        self.assertTrue(any("plot element PLT-001 is missing valid time metadata" in e for e in res["errors"]))
        self.assertTrue(any("plot element PLT-001 is missing valid place metadata" in e for e in res["errors"]))

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

    def test_edt_validation_and_feedback_cli(self):
        edt = """\
# EDT-001: Tone down Elena's panic
- **Target:** [[SCN-001]]
- **Stage:** manuscript
- **Status:** open

## Issue
Elena appears too frail.

## Directive
Make her colder and more diagnostic.
"""
        self.write("story/editorial/EDT-001.md", edt)
        code, res = self.json_cli("check")
        self.assertEqual(code, 0)
        self.assertTrue(any("1 open editorial directive(s)" in info for info in res["infos"]))

        # CLI feedback list
        code, fb_list = self.json_cli("feedback")
        self.assertEqual(code, 0)
        self.assertEqual(len(fb_list), 1)
        self.assertEqual(fb_list[0]["id"], "EDT-001")

        # Impact should flag SCN-001 for manuscript stage
        code, imp = self.json_cli("impact", "--stage", "manuscript")
        self.assertEqual(code, 0)
        flagged = next((s for s in imp["scenes"] if s["id"] == "SCN-001"), None)
        self.assertIsNotNone(flagged)
        self.assertTrue(any("open editorial directive EDT-001" in r for r in flagged["reasons"]))

        # Impact for abridged stage should NOT flag SCN-001 because stage is manuscript
        code, imp_ab = self.json_cli("impact", "--stage", "abridged")
        flagged_ab = next((s for s in imp_ab["scenes"] if s["id"] == "SCN-001"), None)
        if flagged_ab:
            self.assertFalse(any("open editorial directive EDT-001" in r for r in flagged_ab["reasons"]))

    def test_edt_dangling_target_and_invalid_fields(self):
        self.write("story/editorial/EDT-002.md", """\
# EDT-002: Bad directive
- **Target:** [[SCN-999]]
- **Stage:** invalid_stage
- **Status:** invalid_status
""")
        code, res = self.json_cli("check")
        self.assertEqual(code, 1)
        self.assertTrue(any("dangling reference [[SCN-999]]" in e for e in res["errors"]))
        self.assertTrue(any("invalid or missing 'Stage:'" in e for e in res["errors"]))
        self.assertTrue(any("invalid or missing 'Status:'" in e for e in res["errors"]))

    def test_placeholders_detection_and_create_rq(self):
        # Add placeholders to synopsis and a provisional character file
        synopsis_with_placeholders = """\
---
title: "The Iron Mill"
---
# Synopsis
In [summer 1892], in an industrial town near [Pittsburgh], [Protagonist - Eldest Daughter] discovers a secret.
Her father, [Father - Disgraced Physician], treats wounded workers.

### Placeholders Requiring Research
- Period poison: Need uncommon medical alkaloid available in 1892.
"""
        self.write("story/synopsis.md", synopsis_with_placeholders)
        self.write("kb/characters/CHR-003.md", "# CHR-003: [Protagonist - Eldest Daughter]\n- **Role:** Lead\n")

        # 1. Scan placeholders via CLI --json
        code, items = self.json_cli("placeholders")
        self.assertEqual(code, 0)
        self.assertGreaterEqual(len(items), 4)

        protag_item = next((it for it in items if it["text"] == "Protagonist - Eldest Daughter"), None)
        self.assertIsNotNone(protag_item)
        self.assertIsNone(protag_item["tracked_by"])
        # Should have 2 occurrences (synopsis.md and CHR-003.md)
        self.assertEqual(len(protag_item["occurrences"]), 2)
        chr_occ = next((occ for occ in protag_item["occurrences"] if occ["section_id"] == "CHR-003"), None)
        self.assertIsNotNone(chr_occ)

        # 2. Automatically generate RQs via --create-rq
        code, out = self.run_cli("placeholders", "--create-rq")
        self.assertEqual(code, 0)
        self.assertIn("Generated", out)
        self.assertIn("RQ-", out)

        # Verify kb/research/questions.md was written with proper fields
        rq_file = self.root / "kb/research/questions.md"
        self.assertTrue(rq_file.exists())
        rq_content = rq_file.read_text(encoding="utf-8")
        self.assertIn("# Research Questions", rq_content)
        self.assertIn("## RQ-001:", rq_content)
        self.assertIn("- **Status:** open", rq_content)
        # Check that CHR-003 was linked in Needed for:
        self.assertIn("[[CHR-003]]", rq_content)

        # 3. Subsequent run should recognize all placeholders as TRACKED
        code, items_after = self.json_cli("placeholders")
        self.assertEqual(code, 0)
        untracked = [it for it in items_after if it["tracked_by"] is None]
        self.assertEqual(len(untracked), 0)

        # Running --create-rq again should report all tracked
        code, out_again = self.run_cli("placeholders", "--create-rq")
        self.assertEqual(code, 0)
        self.assertIn("All detected placeholders are already tracked", out_again)

    def test_manuscript_placeholder_warning(self):
        # Putting an unresolved bracketed placeholder in manuscript prose triggers a warning
        self.write(
            "manuscript/CHP-001.md",
            "# CHP-001: The Letter\n\n#### SCN-001: Elena receives the letter\n[Protagonist] stared at the letter.\n"
        )
        code, res = self.json_cli("check")
        self.assertTrue(any("unresolved placeholder '[Protagonist]'" in w for w in res["warnings"]))

    def test_parallel_sync_baselines_and_brief_delta(self):
        # 1. Accept initial plan baseline (establishes baseline for all spec stages: brief, research, bible, outline)
        code, out = self.run_cli("accept", "--stage", "plan", "-m", "Initial baseline")
        self.assertEqual(code, 0)
        self.assertIn("Accepted", out)

        # Verify status reports all spec baselines
        code, status_res = self.json_cli("status")
        self.assertEqual(code, 0)
        self.assertIsNotNone(status_res["baselines"]["brief"])
        self.assertIsNotNone(status_res["baselines"]["bible"])

        # 2. Modify story/synopsis.md
        current_synopsis = (self.root / "story/synopsis.md").read_text(encoding="utf-8")
        self.write("story/synopsis.md", current_synopsis + "\n\nNew premise turning point.\n")

        # 3. Check delta --stage brief isolates the synopsis change
        code, brief_delta = self.json_cli("delta", "--stage", "brief")
        self.assertEqual(code, 0)
        self.assertEqual(len(brief_delta["changes"]), 1)
        self.assertEqual(brief_delta["changes"][0]["file"], "story/synopsis.md")

        # 4. Check delta --stage bible shows NO changes because bible files were not touched
        code, bible_delta = self.json_cli("delta", "--stage", "bible")
        self.assertEqual(code, 0)
        self.assertEqual(len(bible_delta["changes"]), 0)

        # 5. Accept updated brief baseline with Git trailer verification
        code, out = self.run_cli("accept", "--stage", "brief", "-m", "Update premise")
        self.assertEqual(code, 0)

        # Check commit trailers in git log
        log_out = subprocess.run(["git", "log", "-1", "--format=%B"], cwd=self.root, capture_output=True, text=True, check=True).stdout
        self.assertIn("Novel-Sync: brief", log_out)
        self.assertIn("Novel-Brief-Modified: story/synopsis.md", log_out)

        # 6. Subsequent delta --stage brief is now clean
        code, brief_delta_after = self.json_cli("delta", "--stage", "brief")
        self.assertEqual(code, 0)
        self.assertEqual(len(brief_delta_after["changes"]), 0)


if __name__ == "__main__":
    unittest.main()
