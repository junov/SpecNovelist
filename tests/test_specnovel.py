"""Tests for scripts/specnovel.py (8-stage + directives architecture; run: uv run python -m unittest discover tests)."""
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
THEMES = """\
# Themes

## THM-001: Exile and Duty
- **Central Question:** Can loyalty survive exile?
"""
ARCS = """\
# Story Arcs

## ARC-001: The Departure Arc
- **Type:** main
- **Themes:** [[THM-001]]
- **Characters:** [[CHR-001]], [[CHR-002]]
- **Summary:** Elena and Karl confront the summons to leave Hamburg.
"""
BEATS = """\
# Narrative Beats (Beat DAG)

## BET-001: Elena receives the harbor summons
- **Place:** [[PLC-001]]
- **Time:** 1912-04-10 Morning
- **Arcs:** [[ARC-001]]
- **Dependencies:** none
- **Cast:** [[CHR-001]]
- **Summary:** Elena opens the sealed letter at Hamburg harbor.

## BET-002: Karl refuses to board
- **Place:** [[PLC-001]]
- **Time:** 1912-04-10 Noon
- **Arcs:** [[ARC-001]]
- **Dependencies:** [[BET-001]]
- **Cast:** [[CHR-002]]
- **Facts:** [[FCT-001]]
- **Summary:** Karl refuses to leave Hamburg despite the shipping schedule.

## BET-003: Elena boards the steamer
- **Place:** [[PLC-001]]
- **Time:** 1912-04-10 Evening
- **Arcs:** [[ARC-001]]
- **Dependencies:** [[BET-002]]
- **Denouement:** true
- **Cast:** [[CHR-001]]
- **Summary:** Elena boards the steamer at dusk, resolving the departure crisis.
"""
ILLUSTRATIONS = """\
# Illustrations

## ILL-001: Hamburg Harbor Chart
- **Type:** map
- **Target:** publishable/graphics/ILL-001.png
- **Prerequisites:** [[PLC-001]]
- **Caption:** Map of Hamburg Harbor Piers
- **Description:** Period nautical chart of Hamburg piers in 1912.
"""
OUTLINE = """\
# Physical Structure Outline

## VOL-001: Departure

## ACT-001: The Summons

### CHP-001: The Letter
POV: [[CHR-001]]

#### SCN-001: Elena receives the letter
- **Where:** [[PLC-001]]
- **When:** 1912-04-10 Morning
- **Beats:** [[BET-001]]
- **Cast:** [[CHR-001]]
- **Target words:** 2000

#### SCN-002: Karl refuses
- **Prerequisites:** [[SCN-001]]
- **Where:** [[PLC-001]]
- **When:** 1912-04-10 Noon
- **Beats:** [[BET-002]]
- **Cast:** [[CHR-002]]
- **Facts:** [[FCT-001]]
- **Target words:** 1500

### CHP-002: The Ship

#### SCN-003: Boarding
- **Prerequisites:** [[SCN-002]]
- **Where:** [[PLC-001]]
- **When:** 1912-04-10 Evening
- **Beats:** [[BET-003]]
- **Cast:** [[CHR-001]]
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
        self.write("setup/synopsis.md", "---\ntitle: The Crossing\n---\n# Synopsis\n" + "word " * 50)
        self.write("setup/themes.md", THEMES)
        self.write("setup/style.md", "# Style\n# Locale: en-US\n## Glossary Guidelines\n## Graphics Guidelines\n## Publication & Book Design Guidelines\n" + "rule " * 500)
        self.write("world/characters/CHR-001-elena.md", CHAR)
        self.write("world/characters/CHR-002-karl.md", CHAR2)
        self.write("world/places/PLC-001-harbor.md", PLACE)
        self.write("world/facts/shipping.md", FACTS)
        self.write("world/sources/bibliography.md", SOURCES)
        self.write("narrative/arcs.md", ARCS)
        self.write("narrative/beats.md", BEATS)
        self.write("narrative/illustrations.md", ILLUSTRATIONS)
        self.write("structure/outline.md", OUTLINE)

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
    def test_init_scaffolds_8_stages_and_directives(self):
        for rel in (
            "setup/brief.md",
            "setup/config.md",
            "setup/themes.md",
            "setup/style.md",
            "research/questions.md",
            "world/facts/.gitkeep",
            "narrative/arcs.md",
            "narrative/beats.md",
            "narrative/illustrations.md",
            "structure/outline.md",
            "structure/back-matter/acknowledgements.md",
            "abridged/.gitkeep",
            "manuscript/.gitkeep",
            "publishable/graphics/.gitkeep",
            "directives/template.md",
        ):
            self.assertTrue((self.root / rel).exists(), rel)
        self.assertIn(".specnovel/", (self.root / ".gitignore").read_text())

    def test_check_ok(self):
        code, res = self.json_cli("check")
        self.assertEqual(res["errors"], [])
        self.assertEqual(code, 0)

    def test_dangling_reference_and_unsourced_fact(self):
        self.write("world/facts/more.md", "## FCT-002: Unsourced\n**Statement:** x [[PLC-009]]\n")
        code, res = self.json_cli("check")
        self.assertEqual(code, 1)
        joined = "\n".join(res["errors"])
        self.assertIn("dangling reference [[PLC-009]]", joined)
        self.assertIn("fact FCT-002 does not cite any", joined)

    def test_duplicate_ids(self):
        self.write("world/characters/dupe.md", "# CHR-001: Someone else\n")
        _, res = self.json_cli("check")
        self.assertTrue(any("duplicate ID CHR-001" in e for e in res["errors"]))

    def test_source_without_url_or_citation(self):
        self.write("world/sources/bad.md", "## SRC-002: Mystery\n- **Type:** secondary\n")
        _, res = self.json_cli("check")
        self.assertTrue(any("SRC-002 has neither" in e for e in res["errors"]))

    def test_next_id_respects_history(self):
        self.assertEqual(self.run_cli("next-id", "CHR")[1].strip(), "CHR-003")
        self.assertEqual(self.run_cli("next-id", "BET")[1].strip(), "BET-004")
        self.assertEqual(self.run_cli("next-id", "ARC")[1].strip(), "ARC-002")
        self.assertEqual(self.run_cli("next-id", "ILL")[1].strip(), "ILL-002")
        self.assertEqual(self.run_cli("next-id", "DIR")[1].strip(), "DIR-001")
        self.run_cli("accept", "--stage", "plan", "-m", "plan")
        (self.root / "world/characters/CHR-002-karl.md").unlink()
        self.assertEqual(self.run_cli("next-id", "CHR")[1].strip(), "CHR-003")
        self.assertEqual(self.run_cli("next-id", "TML")[1].strip(), "TML-001")

    def test_trace(self):
        _, res = self.json_cli("trace", "PLC-001")
        self.assertEqual([s["id"] for s in res["scenes"]], ["SCN-001", "SCN-002", "SCN-003"])
        _, res = self.json_cli("trace", "CHR-001")
        self.assertIn("SCN-001", [s["id"] for s in res["scenes"]])

    def test_abridged_order_and_placement(self):
        self.write("abridged/CHP-001.md", "# CHP-001: The Letter\n\n## SCN-002: Karl\nx\n\n## SCN-001: Elena\ny\n")
        _, res = self.json_cli("check")
        self.assertTrue(any("scene order in CHP-001" in e for e in res["errors"]))
        self.write("abridged/CHP-001.md", "# CHP-002: The Ship\n\n## SCN-001: Elena\ny\n")
        _, res = self.json_cli("check")
        self.assertTrue(any("places it in CHP-001" in e for e in res["errors"]))

    def test_synchronization_generation_gate_and_impact_flow(self):
        # 1. Synchronization Generation Gate: impact/delta on ungenerated stage must fail!
        code_uninit, out_uninit = self.run_cli("impact", "--stage", "abridged")
        self.assertEqual(code_uninit, 1)
        self.assertIn("Synchronization cannot be performed for stage 'abridged'", out_uninit)

        code_delta_uninit, out_delta_uninit = self.run_cli("delta", "--stage", "setup")
        self.assertEqual(code_delta_uninit, 1)
        self.assertIn("Synchronization delta cannot be computed for stage 'setup'", out_delta_uninit)

        # 2. Perform initial generation and accept for plan & abridged
        self.write("abridged/CHP-001.md", ABRIDGED_1)
        self.write("abridged/CHP-002.md", "# CHP-002: The Ship\n\n## SCN-003: Boarding\nThey board.\n")
        code, _ = self.run_cli("accept", "--stage", "plan", "--stage", "abridged", "-m", "first draft")
        self.assertEqual(code, 0)

        # Now abridged has been generated at least once; impact succeeds and reports 0 dirty scenes
        code, imp = self.json_cli("impact", "--stage", "abridged")
        self.assertEqual(code, 0)
        self.assertEqual(imp["scenes"], [])

        # Change a fact -> SCN-002 (and BET-002) references FCT-001
        self.write("world/facts/shipping.md", FACTS.replace("Something true.", "Something else true."))
        code, imp = self.json_cli("impact", "--stage", "abridged")
        self.assertEqual(code, 0)
        self.assertEqual([s["id"] for s in imp["scenes"]], ["SCN-002"])
        self.assertTrue(any("FCT-001" in r for r in imp["scenes"][0]["reasons"]))

        # Manuscript has not been generated yet -> gate blocks manuscript sync until generated
        code_ms, _ = self.run_cli("impact", "--stage", "manuscript")
        self.assertEqual(code_ms, 1)

        # Generate initial manuscript baseline, then test impact
        self.run_cli("accept", "--stage", "manuscript", "--force", "-m", "initial manuscript")
        code_ms2, imp_ms = self.json_cli("impact", "--stage", "manuscript")
        self.assertEqual(code_ms2, 0)
        self.assertEqual(len(imp_ms["scenes"]), 3)

    def test_manuscript_style_change_is_global(self):
        for layer in ("abridged", "manuscript"):
            self.write(f"{layer}/CHP-001.md", ABRIDGED_1)
            self.write(f"{layer}/CHP-002.md", "# CHP-002: The Ship\n\n## SCN-003: Boarding\nThey board.\n")
        self.run_cli("accept", "--stage", "all", "-m", "all")
        self.write("setup/style.md", "# Style\n# Locale: en-US\n## Glossary Guidelines\n## Graphics Guidelines\n## Publication & Book Design Guidelines\n" + "rule " * 500 + "\n\n## Dialogue\nSaid only.\n")
        _, imp = self.json_cli("impact", "--stage", "manuscript")
        self.assertTrue(any("style guide" in g for g in imp["global"]))
        _, imp = self.json_cli("impact", "--stage", "abridged")
        self.assertFalse(any("style" in g for g in imp["global"]))

    def test_moved_scene(self):
        self.write("abridged/CHP-001.md", ABRIDGED_1)
        self.write("abridged/CHP-002.md", "# CHP-002: The Ship\n\n## SCN-003: Boarding\nThey board.\n")
        self.run_cli("accept", "--stage", "plan", "--stage", "abridged")
        block = (
            "#### SCN-002: Karl refuses\n"
            "- **Prerequisites:** [[SCN-001]]\n"
            "- **Where:** [[PLC-001]]\n"
            "- **When:** 1912-04-10 Noon\n"
            "- **Beats:** [[BET-002]]\n"
            "- **Cast:** [[CHR-002]]\n"
            "- **Facts:** [[FCT-001]]\n"
            "- **Target words:** 1500\n"
        )
        moved = OUTLINE.replace(block, "").replace("### CHP-002: The Ship\n", "### CHP-002: The Ship\n\n" + block)
        self.write("structure/outline.md", moved)
        _, imp = self.json_cli("impact", "--stage", "abridged")
        reasons = {s["id"]: s["reasons"] for s in imp["scenes"]}
        self.assertIn("moved from CHP-001 to CHP-002", reasons["SCN-002"])

    def test_beat_dag_and_physical_serialization_valid(self):
        code, out = self.run_cli("dag")
        self.assertEqual(code, 0)
        self.assertIn("[OK] Acyclic Check", out)
        self.assertIn("[OK] Physical Serialization Coherence", out)
        self.assertIn("[OK] Denouement Essentiality", out)
        self.assertIn("BET-003", out)

        code, res = self.json_cli("dag")
        self.assertEqual(code, 0)
        self.assertTrue(res["ok"])
        self.assertEqual(res["root"], "BET-003")
        self.assertEqual(res["cycles"], [])
        self.assertEqual(res["readingOrderErrors"], [])
        self.assertEqual(res["essentialityErrors"], [])

        code, out = self.run_cli("dag", "--mermaid")
        self.assertEqual(code, 0)
        self.assertIn("graph TD", out)
        self.assertIn("BET-001 --> BET-002", out)
        self.assertIn("BET-002 --> BET-003", out)

    def test_beat_metadata_and_dag_violations(self):
        # 1. Beat missing Place, Time, or Arcs fails check
        bad_beats = BEATS + "\n## BET-004: Floating Beat\n- **Summary:** Missing place, time, and arc.\n"
        self.write("narrative/beats.md", bad_beats)
        code, res = self.json_cli("check")
        self.assertEqual(code, 1)
        joined = "\n".join(res["errors"])
        self.assertIn("beat BET-004 is missing a valid Place", joined)
        self.assertIn("beat BET-004 is missing valid Time metadata", joined)
        self.assertIn("beat BET-004 must be associated with at least one story arc", joined)

        # 2. Cycle in Beat DAG
        cycled_beats = BEATS.replace(
            "## BET-001: Elena receives the harbor summons\n- **Place:** [[PLC-001]]\n- **Time:** 1912-04-10 Morning\n- **Arcs:** [[ARC-001]]\n- **Dependencies:** none",
            "## BET-001: Elena receives the harbor summons\n- **Place:** [[PLC-001]]\n- **Time:** 1912-04-10 Morning\n- **Arcs:** [[ARC-001]]\n- **Dependencies:** [[BET-003]]",
        )
        self.write("narrative/beats.md", cycled_beats)
        code, res = self.json_cli("dag")
        self.assertEqual(code, 1)
        self.assertFalse(res["ok"])
        self.assertTrue(len(res["cycles"]) > 0)

        # 3. Physical structure topological reading-order violation (BET-002 placed before BET-001 in outline)
        self.write("narrative/beats.md", BEATS)
        bad_outline = OUTLINE.replace("#### SCN-001: Elena receives the letter\n- **Where:** [[PLC-001]]\n- **When:** 1912-04-10 Morning\n- **Beats:** [[BET-001]]",
                                      "#### SCN-001: Elena receives the letter\n- **Where:** [[PLC-001]]\n- **When:** 1912-04-10 Morning\n- **Beats:** [[BET-002]]").replace(
                                      "#### SCN-002: Karl refuses\n- **Prerequisites:** [[SCN-001]]\n- **Where:** [[PLC-001]]\n- **When:** 1912-04-10 Noon\n- **Beats:** [[BET-002]]",
                                      "#### SCN-002: Karl refuses\n- **Prerequisites:** [[SCN-001]]\n- **Where:** [[PLC-001]]\n- **When:** 1912-04-10 Noon\n- **Beats:** [[BET-001]]")
        self.write("structure/outline.md", bad_outline)
        code, res = self.json_cli("check")
        self.assertEqual(code, 1)
        self.assertTrue(any("reading order violation: beat BET-002" in e for e in res["errors"]))

        # 4. Inessential beat (dead end in Beat DAG)
        self.write("structure/outline.md", OUTLINE)
        dead_beat = BEATS + (
            "\n## BET-004: Unresolved Side Beat\n"
            "- **Place:** [[PLC-001]]\n"
            "- **Time:** 1912-04-10 Afternoon\n"
            "- **Arcs:** [[ARC-001]]\n"
            "- **Dependencies:** [[BET-001]]\n"
            "- **Summary:** Dead end.\n"
        )
        self.write("narrative/beats.md", dead_beat)
        code, res = self.json_cli("dag")
        self.assertEqual(code, 1)
        self.assertTrue(any("BET-004 has no causal path to the root denouement (BET-003)" in e for e in res["essentialityErrors"]))

    def test_directives_preservation_autolinking_and_factoring(self):
        # 1. Factor a shared instruction into DIR-001 across CHR-001 and SCN-001
        code, factor_res = self.json_cli(
            "directives",
            "factor",
            "--title",
            "Maritime Bureaucratic Register",
            "--scope",
            "[[PLC-001]], [[CHR-001]]",
            "--instruction",
            "Characters at Hamburg harbor speak in clipped official phrasing without contractions.",
            "--targets",
            "CHR-001",
            "SCN-001",
        )
        self.assertEqual(code, 0)
        self.assertEqual(factor_res["directive_id"], "DIR-001")
        self.assertIn("CHR-001", factor_res["linked_targets"])
        self.assertIn("SCN-001", factor_res["linked_targets"])
        self.assertTrue((self.root / "directives/DIR-001.md").is_file())

        # Verify CHR-001 and SCN-001 now reference [[DIR-001]]
        self.assertIn("[[DIR-001]]", (self.root / "world/characters/CHR-001-elena.md").read_text(encoding="utf-8"))
        self.assertIn("[[DIR-001]]", (self.root / "structure/outline.md").read_text(encoding="utf-8"))

        # 2. Accept world & structure baselines so DIR-001 links are locked in
        code, _ = self.run_cli("accept", "--stage", "plan", "-m", "Baseline with DIR-001")
        self.assertEqual(code, 0)

        # 3. Directive Preservation check: if an update to CHR-001 drops [[DIR-001]], check MUST fail!
        self.write("world/characters/CHR-001-elena.md", CHAR)  # overwrites without [[DIR-001]]
        code, check_res = self.json_cli("check")
        self.assertEqual(code, 1)
        self.assertTrue(any("dropped associated directive [[DIR-001]]" in e for e in check_res["errors"]))

        # Restore [[DIR-001]] on CHR-001 and check passes
        self.write("world/characters/CHR-001-elena.md", CHAR + "- **Directives:** [[DIR-001]]\n")
        code, check_res2 = self.json_cli("check")
        self.assertEqual(code, 0)

        # 4. Auto-Linking on newly created records:
        # Create a new character CHR-003 associated with [[PLC-001]] (which matches DIR-001's Scope!)
        self.write("world/characters/CHR-003-inspector.md", "# CHR-003: Harbor Inspector\n- **Location:** [[PLC-001]]\n")
        code, link_res = self.json_cli("directives", "link", "--record", "CHR-003", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(len(link_res["links"]), 1)
        self.assertEqual(link_res["links"][0]["record"], "CHR-003")
        self.assertIn("DIR-001", link_res["links"][0]["directives"])
        self.assertIn("[[DIR-001]]", (self.root / "world/characters/CHR-003-inspector.md").read_text(encoding="utf-8"))

    def test_stats_and_compile(self):
        self.write("manuscript/CHP-001.md", ABRIDGED_1.replace("## SCN-002", "<!-- note [[CHR-002]] -->\n## SCN-002"))
        _, st = self.json_cli("stats")
        self.assertEqual(st["totals"]["target"], 3500)
        self.assertGreater(st["totals"]["manuscript"], 10)
        code, _ = self.run_cli("compile")
        self.assertEqual(code, 0)
        book = (self.root / "publishable/en-US/manuscript.md").read_text(encoding="utf-8")
        self.assertIn('title: "The Crossing"', book)
        self.assertIn("# Act One: The Summons", book)
        self.assertIn("## Chapter One: The Letter", book)
        self.assertIn("* * *", book)
        self.assertNotIn("SCN-", book)
        self.assertNotIn("<!--", book)

    def test_status_and_index(self):
        code, res = self.json_cli("status")
        self.assertEqual(code, 0)
        self.assertEqual(res["scenes"]["outline"], 3)
        self.run_cli("index")
        idx = (self.root / "world/INDEX.md").read_text(encoding="utf-8")
        self.assertIn("| CHR-001 | Elena Voss |", idx)
        _, res = self.json_cli("check")
        self.assertEqual(res["errors"], [])

    def test_placeholders_detection_and_create_rq(self):
        synopsis_with_placeholders = """\
---
title: "The Iron Mill"
---
# Synopsis
In [summer 1892], in an industrial town near [Pittsburgh], [Protagonist - Eldest Daughter] discovers a secret.
"""
        self.write("setup/synopsis.md", synopsis_with_placeholders)
        self.write("world/characters/CHR-003.md", "# CHR-003: [Protagonist - Eldest Daughter]\n- **Role:** Lead\n")

        code, items = self.json_cli("placeholders")
        self.assertEqual(code, 0)
        self.assertGreaterEqual(len(items), 3)

        code, out = self.run_cli("placeholders", "--create-rq")
        self.assertEqual(code, 0)
        self.assertIn("Generated", out)
        self.assertIn("RQ-", out)

        rq_file = self.root / "research/questions.md"
        self.assertTrue(rq_file.exists())
        rq_content = rq_file.read_text(encoding="utf-8")
        self.assertIn("## RQ-001:", rq_content)
        self.assertIn("[[CHR-003]]", rq_content)

    def test_parallel_sync_baselines_and_setup_delta(self):
        code, out = self.run_cli("accept", "--stage", "plan", "-m", "Initial baseline")
        self.assertEqual(code, 0)
        self.assertIn("Accepted", out)

        code, status_res = self.json_cli("status")
        self.assertEqual(code, 0)
        self.assertIsNotNone(status_res["baselines"]["setup"])
        self.assertIsNotNone(status_res["baselines"]["world"])

        current_synopsis = (self.root / "setup/synopsis.md").read_text(encoding="utf-8")
        self.write("setup/synopsis.md", current_synopsis + "\n\nNew premise turning point.\n")

        code, setup_delta = self.json_cli("delta", "--stage", "setup")
        self.assertEqual(code, 0)
        self.assertEqual(len(setup_delta["changes"]), 1)
        self.assertEqual(setup_delta["changes"][0]["file"], "setup/synopsis.md")

        code, world_delta = self.json_cli("delta", "--stage", "world")
        self.assertEqual(code, 0)
        self.assertEqual(len(world_delta["changes"]), 0)

    def test_illustrations_and_publishable_graphics_tracking(self):
        # Define a second illustration ILL-002 in narrative/illustrations.md (inactive)
        ill_both = ILLUSTRATIONS + """
## ILL-002: Elena Portrait
- **Type:** portrait
- **Target:** publishable/graphics/ILL-002.png
- **Prerequisites:** [[CHR-001]]
"""
        self.write("narrative/illustrations.md", ill_both)

        # Reference ILL-001 in SCN-001 in structure/outline.md
        updated_outline = OUTLINE.replace(
            "#### SCN-001: Elena receives the letter\n",
            "#### SCN-001: Elena receives the letter\n- **Illustrations:** [[ILL-001]]\n",
        )
        self.write("structure/outline.md", updated_outline)

        # Accept plan and initial publishable baseline to unlock sync
        self.run_cli("accept", "--stage", "plan", "--stage", "publishable", "-m", "Initial publishable baseline")

        code, imp = self.json_cli("impact", "--stage", "publishable")
        self.assertEqual(code, 0)
        self.assertEqual(len(imp["active"]), 1)
        self.assertEqual(imp["active"][0]["id"], "ILL-001")
        self.assertEqual(len(imp["inactive"]), 1)
        self.assertEqual(imp["inactive"][0]["id"], "ILL-002")

        # Render ILL-001 in publishable/graphics/ILL-001.png and accept
        self.write("publishable/graphics/ILL-001.png", "dummy-png-data")
        code, _ = self.run_cli("accept", "--stage", "publishable", "--asset", "ILL-001", "-m", "Render ILL-001")
        self.assertEqual(code, 0)

        code, imp_after = self.json_cli("impact", "--stage", "publishable")
        self.assertEqual(code, 0)
        self.assertEqual(imp_after["active"][0]["status"], "UP_TO_DATE")

    def test_ai_model_tracking_and_acknowledgements(self):
        (self.root / "structure/back-matter/acknowledgements.md").unlink()
        code, res = self.json_cli("check")
        self.assertEqual(code, 1)
        self.assertTrue(any("missing mandatory acknowledgements file" in e for e in res["errors"]))

        self.write("structure/back-matter/acknowledgements.md", "# Acknowledgements\n\nAssisted by Google Gemini 2.5 Pro.\n")
        code, _ = self.run_cli("accept", "--stage", "setup", "--model", "gemini-2.5-pro", "-m", "Setup update")
        self.assertEqual(code, 0)

        code, models_res = self.json_cli("models")
        self.assertEqual(code, 0)
        self.assertTrue(models_res["all_acknowledged"])

    def test_epistemic_and_chekhov_gun_checks(self):
        self.write("world/objects/OBJ-001-letter.md", "# OBJ-001: The letter\n")
        outline_valid = OUTLINE.replace(
            "- **Beats:** [[BET-001]]",
            "- **Beats:** [[BET-001]]\n- **Plants:** [[OBJ-001]]",
        ).replace(
            "- **Beats:** [[BET-002]]",
            "- **Beats:** [[BET-002]]\n- **Pays off:** [[OBJ-001]]",
        )
        self.write("structure/outline.md", outline_valid)
        code, res = self.json_cli("check")
        self.assertEqual(code, 0)

    def test_harvest_scenarios_takes_and_audit_report(self):
        # 1. Harvest
        sample_draft = (
            "# The Harbor Rendezvous\n\n"
            "Elena looked across the fog-shrouded piers of Southampton Harbor.\n\n"
            '"Where is the packet?" asked Karl.\n'
        )
        self.write("draft_sample.txt", sample_draft)
        code, res = self.json_cli("harvest", "draft_sample.txt", "--apply", "--batch", "-t", "Harbor Rendezvous")
        self.assertEqual(code, 0)
        self.assertTrue(res["applied"])

        # 2. Scenarios
        code, s_res = self.json_cli("scenario", "create", "alt-ending", "-m", "Alt")
        self.assertEqual(code, 0)
        self.assertTrue(s_res["created"])

        # 3. Takes
        self.write(
            "manuscript/en-US/CHP-001.md",
            "# CHP-001: The Letter\n\n## SCN-001: Elena\nElena opened the envelope with trembling hands.\n\n## SCN-002: Karl\nKarl turned away.\n",
        )
        code, t_res = self.json_cli("takes", "save", "SCN-001", "default-third", "-m", "Third person")
        self.assertEqual(code, 0)
        self.assertTrue(t_res["saved"])

        # 4. Audit report generation
        code, out = self.run_cli("audit", "--report", "--output", "reports/analysis.md")
        self.assertEqual(code, 0)
        rep_txt = (self.root / "reports/analysis.md").read_text(encoding="utf-8")
        self.assertIn("# Developmental Editorial & Style Analysis Report", rep_txt)
        self.assertIn("[[SCN-001]]", rep_txt)


if __name__ == "__main__":
    unittest.main()
