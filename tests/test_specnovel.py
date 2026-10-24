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
        self.write("story/style.md", "# Style\n# Locale: en-US\n## Glossary Guidelines\n## Graphics Guidelines\n## Publication & Book Design Guidelines\n" + "rule " * 500)
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
        for rel in ("story/brief.md", "story/config.md", "story/acknowledgements.md", "outline/outline.md", "kb/facts/.gitkeep", "manuscript/.gitkeep"):
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

    def test_graphics_stage_and_per_asset_sync_tracking(self):
        # 1. Scaffolding check: graphics/ and kb/graphics/ exist
        self.assertTrue((self.root / "graphics").is_dir())
        self.assertTrue((self.root / "kb/graphics").is_dir())

        # 2. Define two graphical assets in kb/graphics/
        gfx1_content = """\
# GFX-001: Hamburg Harbor Map
- **Type:** map
- **Target:** graphics/map.png
- **Prerequisites:** [[PLC-001]]
- **Embed:** [[SCN-001]]
"""
        gfx2_content = """\
# GFX-002: Elena Portrait
- **Type:** portrait
- **Target:** graphics/portrait.png
- **Prerequisites:** [[CHR-001]]
"""
        self.write("kb/graphics/GFX-001-map.md", gfx1_content)
        self.write("kb/graphics/GFX-002-portrait.md", gfx2_content)

        # 3. Reference GFX-001 in SCN-001 in outline. GFX-002 is left unreferenced.
        current_outline = (self.root / "outline/outline.md").read_text(encoding="utf-8")
        updated_outline = current_outline.replace(
            "#### SCN-001: Elena receives the letter\n",
            "#### SCN-001: Elena receives the letter\n- **Graphics:** [[GFX-001]]\n"
        )
        self.write("outline/outline.md", updated_outline)

        # Establish plan baseline first
        code, _ = self.run_cli("accept", "--stage", "plan", "-m", "Baseline with GFX definitions")
        self.assertEqual(code, 0)

        # 4. Check impact on graphics stage
        code, imp = self.json_cli("impact", "--stage", "graphics")
        self.assertEqual(code, 0)
        self.assertEqual(len(imp["active"]), 1)
        self.assertEqual(imp["active"][0]["id"], "GFX-001")
        self.assertEqual(imp["active"][0]["status"], "NEEDS_RENDERING")
        self.assertIn("rendered file missing on disk (graphics/map.png)", imp["active"][0]["reasons"])

        # GFX-002 is inactive (token saver!)
        self.assertEqual(len(imp["inactive"]), 1)
        self.assertEqual(imp["inactive"][0]["id"], "GFX-002")
        self.assertEqual(imp["inactive"][0]["status"], "INACTIVE")
        self.assertIn("skipped (not in Story DAG - 0 tokens used", imp["inactive"][0]["reason"])
        self.assertEqual(imp["token_savings_count"], 1)

        # 5. Render GFX-001 (create fake rendered image file)
        self.write("graphics/map.png", "dummy-png-data")

        # 6. Accept graphics stage
        code, out = self.run_cli("accept", "--stage", "graphics", "-m", "Render harbor map")
        self.assertEqual(code, 0)

        # Verify git commit trailer Novel-GFX-Sync includes GFX-001 but NOT GFX-002
        log_out = subprocess.run(["git", "log", "-1", "--format=%B"], cwd=self.root, capture_output=True, text=True, check=True).stdout
        self.assertIn("Novel-Sync: graphics", log_out)
        gfx_sync_line = [line for line in log_out.splitlines() if line.startswith("Novel-GFX-Sync:")][0]
        self.assertIn("GFX-001", gfx_sync_line)
        self.assertNotIn("GFX-002", gfx_sync_line)

        # Verify GFX-001 is now UP_TO_DATE
        code, imp_after = self.json_cli("impact", "--stage", "graphics")
        self.assertEqual(code, 0)
        self.assertEqual(imp_after["active"][0]["status"], "UP_TO_DATE")
        self.assertEqual(imp_after["needs_update_count"], 0)

        # 7. Modify prerequisite PLC-001 and advance bible baseline
        current_plc = (self.root / "kb/places/PLC-001-harbor.md").read_text(encoding="utf-8")
        self.write("kb/places/PLC-001-harbor.md", current_plc + "\n- **Piers:** Expanded in 1912\n")
        self.run_cli("accept", "--stage", "bible", "-m", "Update harbor piers")

        # 8. Check how far out of sync GFX-001 is
        code, imp_oos = self.json_cli("impact", "--stage", "graphics")
        self.assertEqual(code, 0)
        gfx1_stat = imp_oos["active"][0]
        self.assertEqual(gfx1_stat["status"], "OUT_OF_SYNC")
        self.assertEqual(gfx1_stat["commits_behind"], 1)
        self.assertIn("referenced [[PLC-001]] modified", gfx1_stat["reasons"])

        # 9. Newly reference GFX-002 in SCN-002 in outline
        outline_with_gfx2 = (self.root / "outline/outline.md").read_text(encoding="utf-8").replace(
            "#### SCN-002: Karl refuses\n",
            "#### SCN-002: Karl refuses\n- **Graphics:** [[GFX-002]]\n"
        )
        self.write("outline/outline.md", outline_with_gfx2)
        self.run_cli("accept", "--stage", "outline", "-m", "Add GFX-002 to SCN-002")

        # GFX-002 is now active in Story DAG and reports out-of-sync status
        code, imp_newly_active = self.json_cli("impact", "--stage", "graphics")
        self.assertEqual(code, 0)
        active_ids = {a["id"]: a for a in imp_newly_active["active"]}
        self.assertIn("GFX-002", active_ids)
        self.assertEqual(active_ids["GFX-002"]["status"], "NEEDS_RENDERING")
        self.assertIn("no sync baseline (never rendered)", active_ids["GFX-002"]["reasons"])
        self.assertIn("rendered file missing on disk (graphics/portrait.png)", active_ids["GFX-002"]["reasons"])

        # 10. Accept specifically GFX-002 using --asset
        self.write("graphics/portrait.png", "dummy-portrait-data")
        code, _ = self.run_cli("accept", "--stage", "graphics", "--asset", "GFX-002", "-m", "Render portrait")
        self.assertEqual(code, 0)

        log_out2 = subprocess.run(["git", "log", "-1", "--format=%B"], cwd=self.root, capture_output=True, text=True, check=True).stdout
        self.assertIn("Novel-GFX-Sync: GFX-002", log_out2)

    def test_config_schema_validation(self):
        # 1. Invalid schema: unknown top-level key
        bad_config = """\
# Project Configuration
- **Schema Version:** 1.0
- **Unknown Key:** invalid

## Project
- **Title:** Valid Title

## Author
- **Name:** Author

## Languages
- **Primary:** en-US
- **Targets:**
  - en-US
"""
        self.write("story/config.md", bad_config)
        code, res = self.json_cli("check")
        self.assertEqual(code, 1)
        self.assertTrue(any("unknown top-level configuration key 'unknown_key'" in e for e in res["errors"]))

        # 2. Invalid schema: primary language not in targets
        mismatched_langs = """\
# Project Configuration
- **Schema Version:** 1.0

## Project
- **Title:** Valid Title

## Author
- **Name:** Author

## Languages
- **Primary:** de-DE
- **Targets:** en-US, fr-FR
"""
        self.write("story/config.md", mismatched_langs)
        code, res = self.json_cli("check")
        self.assertEqual(code, 1)
        self.assertTrue(any("primary language 'de-DE' must be included in 'languages.targets'" in e for e in res["errors"]))

        # 3. Missing foreword file
        fwd_config = """\
# Project Configuration
- **Schema Version:** 1.0

## Project
- **Title:** Valid Title

## Author
- **Name:** Author

## Languages
- **Primary:** en-US
- **Targets:** en-US

## Front Matter
- **Foreword:** story/missing_foreword.md
"""
        self.write("story/config.md", fwd_config)
        code, res = self.json_cli("check")
        self.assertEqual(code, 1)
        self.assertTrue(any("front_matter.foreword references missing file" in e for e in res["errors"]))

        # 4. Legacy config.yaml detection
        (self.root / "story/config.md").unlink()
        self.write("story/config.yaml", "legacy: true\n")
        code, res = self.json_cli("check")
        self.assertEqual(code, 1)
        self.assertTrue(any("legacy configuration file 'config.yaml' detected" in e for e in res["errors"]))
        (self.root / "story/config.yaml").unlink()

    def test_bibliography_filtered_by_dag(self):
        # Add an unattached fact and source to KB
        self.write("kb/sources/unattached_source.md", "## SRC-002: Maritime Archive\n- **Type:** archival\n- **Citation:** Naval Records 1912\n")
        self.write("kb/facts/unattached_fact.md", "## FCT-002: Sea temperature\n**Statement:** 31 degrees.\n**Sources:**\n- [[SRC-002]]\n")

        # FCT-001 / SRC-001 is attached to SCN-002 in outline. FCT-002 / SRC-002 is not attached to any scene.
        code, bib_res = self.json_cli("bibliography")
        self.assertEqual(code, 0)
        self.assertIn("FCT-001", bib_res["activeFacts"])
        self.assertNotIn("FCT-002", bib_res["activeFacts"])
        self.assertIn("SRC-001", bib_res["activeSources"])
        self.assertNotIn("SRC-002", bib_res["activeSources"])
        self.assertIn("SRC-001", bib_res["markdown"])
        self.assertNotIn("SRC-002", bib_res["markdown"])

    def test_multilingual_editorial_directives_and_graphics_checks(self):
        # Configure multilingual targets
        multi_config = """\
# Project Configuration
- **Schema Version:** 1.0

## Project
- **Title:** The Crossing

## Author
- **Name:** Justin Novosad

## Languages
- **Primary:** en-US
- **Targets:**
  - en-US
  - fr-FR

## Back Matter
- **Include Glossary:** true
- **Include Bibliography:** true
"""
        self.write("story/config.md", multi_config)
        # Update style.md with fr-FR section
        self.write("story/style.md", "# Style\n# Locale: en-US\n# Locale: fr-FR\n## Glossary Guidelines\n## Graphics Guidelines\n## Publication & Book Design Guidelines\n" + "rule " * 500)

        # 1. Editorial directives tagged with locales
        edt_fr = """\
# EDT-001: French dialogue register
- **Target:** [[SCN-001]]
- **Stage:** manuscript
- **Locale:** fr-FR
- **Status:** open

## Directive
Use formal vouvoiement between Elena and the harbor master.
"""
        edt_all = """\
# EDT-002: Pacing cut
- **Target:** [[SCN-001]]
- **Stage:** manuscript
- **Locale:** all
- **Status:** open

## Directive
Trim opening paragraph by three sentences.
"""
        edt_invalid = """\
# EDT-003: Invalid locale
- **Target:** [[SCN-001]]
- **Stage:** manuscript
- **Locale:** de-DE
- **Status:** open

## Directive
Some directive.
"""
        self.write("story/editorial/EDT-001.md", edt_fr)
        self.write("story/editorial/EDT-002.md", edt_all)
        self.write("story/editorial/EDT-003.md", edt_invalid)

        code, res = self.json_cli("check")
        self.assertEqual(code, 1)
        self.assertTrue(any("has invalid 'Locale:' 'de-DE'" in e for e in res["errors"]))

        # Remove invalid EDT
        (self.root / "story/editorial/EDT-003.md").unlink()

        # Feedback filter by locale
        code, fb_fr = self.json_cli("feedback", "--locale", "fr-FR")
        self.assertEqual(code, 0)
        fb_ids_fr = {f["id"] for f in fb_fr}
        self.assertIn("EDT-001", fb_ids_fr)
        self.assertIn("EDT-002", fb_ids_fr)

        code, fb_en = self.json_cli("feedback", "--locale", "en-US")
        self.assertEqual(code, 0)
        fb_ids_en = {f["id"] for f in fb_en}
        self.assertNotIn("EDT-001", fb_ids_en)
        self.assertIn("EDT-002", fb_ids_en)

        # 2. Localized graphics reference verification
        gfx_spec = """\
# GFX-001: Harbor Map
- **Type:** map
- **Target:** graphics/GFX-001.png
- **Has-Text:** true
"""
        self.write("kb/graphics/GFX-001-map.md", gfx_spec)
        self.write("graphics/GFX-001.en-US.png", "dummy-en")
        self.write("graphics/GFX-001.fr-FR.png", "dummy-fr")

        # French manuscript file incorrectly referencing en-US asset
        fr_chapter_mismatched = """\
# CHP-001: La Lettre

## SCN-001: Elena reçoit la lettre
![Carte du Port](../../graphics/GFX-001.en-US.png)
Elena ouvre la lettre.
"""
        self.write("manuscript/fr-FR/CHP-001.md", fr_chapter_mismatched)

        code, check_res = self.json_cli("check")
        self.assertEqual(code, 1)
        self.assertTrue(any("references mismatched graphic" in e and "expected localized version 'graphics/GFX-001.fr-FR.png'" in e for e in check_res["errors"]))

        # Fix French manuscript file to reference localized version
        fr_chapter_fixed = fr_chapter_mismatched.replace("GFX-001.en-US.png", "GFX-001.fr-FR.png")
        self.write("manuscript/fr-FR/CHP-001.md", fr_chapter_fixed)

        # Also add en-US manuscript referencing en-US
        en_chapter = """\
# CHP-001: The Letter

## SCN-001: Elena receives the letter
![Harbor Map](../../graphics/GFX-001.en-US.png)
Elena opens the letter.
"""
        self.write("manuscript/en-US/CHP-001.md", en_chapter)

        code, check_fixed = self.json_cli("check")
        self.assertEqual(code, 0)

    def test_ai_model_tracking_and_acknowledgements(self):
        # 1. Missing acknowledgements file
        (self.root / "story/acknowledgements.md").unlink()
        code, res = self.json_cli("check")
        self.assertEqual(code, 1)
        self.assertTrue(any("missing mandatory acknowledgements file" in e for e in res["errors"]))

        # 2. Empty acknowledgements file
        self.write("story/acknowledgements.md", "   \n")
        code, res = self.json_cli("check")
        self.assertEqual(code, 1)
        self.assertTrue(any("mandatory acknowledgements file" in e and "empty" in e for e in res["errors"]))

        # 3. Model used in accept --model when not acknowledged
        self.write("story/acknowledgements.md", "# Acknowledgements\n\nThanks to friends and family.\n")
        code, _ = self.run_cli("accept", "--stage", "brief", "--model", "gemini-2.5-pro", "-m", "Brief update")
        self.assertNotEqual(code, 0)

        # 4. Acknowledging the model allows accept to succeed
        self.write("story/acknowledgements.md", "# Acknowledgements\n\nAssisted by Google Gemini 2.5 Pro.\n")
        code, _ = self.run_cli("accept", "--stage", "brief", "--model", "gemini-2.5-pro", "-m", "Brief update")
        self.assertEqual(code, 0)

        # Verify Novel-Model trailer in git log
        log_out = subprocess.run(["git", "log", "-1", "--format=%B"], cwd=self.root, capture_output=True, text=True, check=True).stdout
        self.assertIn("Novel-Model: gemini-2.5-pro", log_out)

        # 5. CLI models command checks status
        code, models_res = self.json_cli("models")
        self.assertEqual(code, 0)
        self.assertTrue(models_res["all_acknowledged"])
        self.assertTrue(any(m["model"] == "gemini-2.5-pro" and m["acknowledged"] for m in models_res["models"]))

        # 6. Introducing a new model without updating acknowledgements causes check to fail
        code, _ = self.run_cli("accept", "--stage", "brief", "--model", "claude-3-7-sonnet", "-m", "Claude step")
        self.assertNotEqual(code, 0)

        # Acknowledge Claude and accept succeeds
        self.write("story/acknowledgements.md", "# Acknowledgements\n\nAssisted by Gemini 2.5 Pro and Claude 3.7 Sonnet.\n")
        code, _ = self.run_cli("accept", "--stage", "brief", "--model", "claude-3-7-sonnet", "-m", "Claude step")
        self.assertEqual(code, 0)

        # 7. Compile includes acknowledgements verbatim
        code, _ = self.run_cli("compile")
        self.assertEqual(code, 0)
        compiled_book = (self.root / "build/manuscript.md").read_text(encoding="utf-8")
        self.assertIn("# Acknowledgements", compiled_book)
        self.assertIn("Assisted by Gemini 2.5 Pro and Claude 3.7 Sonnet.", compiled_book)

    def test_style_graphics_guidelines_and_outline_placement(self):
        # 1. Missing Graphics Guidelines in style.md emits warning in check
        self.write("story/style.md", "# Style\n# Locale: en-US\n## Glossary Guidelines\n## Publication & Book Design Guidelines\n" + "rule " * 500)
        code, res = self.json_cli("check")
        self.assertEqual(code, 0)
        self.assertTrue(any("lacks '## Graphics Guidelines' section" in w for w in res["warnings"]))

        # 2. Restoring Graphics Guidelines resolves warning
        self.write("story/style.md", "# Style\n# Locale: en-US\n## Glossary Guidelines\n## Graphics Guidelines\n## Publication & Book Design Guidelines\n" + "rule " * 500)
        code, res = self.json_cli("check")
        self.assertEqual(code, 0)
        self.assertFalse(any("lacks '## Graphics Guidelines' section" in w for w in res["warnings"]))

        # 3. Graphics placeholder [GFX: ...] scanned and recognized with kind='gfx'
        outline_with_gfx = OUTLINE.replace(
            "- **Where:** [[PLC-001]]",
            "- **Where:** [[PLC-001]]\n- **Graphics:** [GFX: Harbor approach chart]"
        )
        self.write("outline/outline.md", outline_with_gfx)
        code, pl_res = self.json_cli("placeholders")
        self.assertEqual(code, 0)
        self.assertTrue(any(p["kind"] == "gfx" and p["text"] == "Harbor approach chart" for p in pl_res))

        # 4. Referencing [[GFX-001]] in outline activates it in the Story DAG
        gfx_def = """# GFX-001: Harbor approach chart
- **Type:** map
- **Target:** graphics/GFX-001.png
- **Description:** Nautical chart of harbor.
"""
        self.write("kb/graphics/GFX-001-harbor.md", gfx_def)
        outline_with_gfx_ref = OUTLINE.replace(
            "- **Where:** [[PLC-001]]",
            "- **Where:** [[PLC-001]]\n- **Graphics:** [[GFX-001]]"
        )
        self.write("outline/outline.md", outline_with_gfx_ref)

        code, impact_res = self.json_cli("impact", "--stage", "graphics")
        self.assertEqual(code, 0)
        active_assets = [item["id"] for item in impact_res["active"]]
        self.assertIn("GFX-001", active_assets)

    def test_publication_guidelines_and_compile(self):
        # 1. Missing Publication Guidelines in style.md emits warning in check
        self.write("story/style.md", "# Style\n# Locale: en-US\n## Glossary Guidelines\n## Graphics Guidelines\n" + "rule " * 500)
        code, res = self.json_cli("check")
        self.assertEqual(code, 0)
        self.assertTrue(any("lacks '## Publication & Book Design Guidelines' section" in w for w in res["warnings"]))

        # 2. Add full Publication & Book Design Guidelines to style.md
        pub_style = """# Style
# Locale: en-US
## Glossary Guidelines
## Graphics Guidelines
## Publication & Book Design Guidelines

### Page Layout & Trim Size
- **Trim Size:** 6in x 9in
- **Inner Margin:** 0.85in
- **Outer Margin:** 0.60in
- **Top Margin:** 0.80in
- **Bottom Margin:** 0.80in

### Interior Typography
- **Body Font:** Baskerville
- **Heading Font:** Playfair Display
- **Font Size:** 11.5pt
- **Line Height:** 1.40
- **Scene Break:** ❦

""" + "rule " * 500
        self.write("story/style.md", pub_style)
        code, res = self.json_cli("check")
        self.assertEqual(code, 0)
        self.assertFalse(any("lacks '## Publication & Book Design Guidelines' section" in w for w in res["warnings"]))

        # 3. Compile manuscript and verify publication typography & geometry in output
        self.write("manuscript/CHP-001.md", ABRIDGED_1)
        code, _ = self.run_cli("compile")
        self.assertEqual(code, 0)

        book_md = (self.root / "build/manuscript.md").read_text(encoding="utf-8")
        self.assertIn("paperwidth=6in", book_md)
        self.assertIn("paperheight=9in", book_md)
        self.assertIn("inner=0.85in", book_md)
        self.assertIn("outer=0.60in", book_md)
        self.assertIn('mainfont: "Baskerville"', book_md)
        self.assertIn("fontsize: 11.5pt", book_md)
        self.assertIn("linestretch: 1.40", book_md)
        self.assertIn("❦", book_md)

        # 4. Verify generated EPUB stylesheet
        epub_css = (self.root / "build/epub.css").read_text(encoding="utf-8")
        self.assertIn('font-family: "Baskerville", "Georgia", serif;', epub_css)
        self.assertIn('font-family: "Playfair Display", "Baskerville", serif;', epub_css)
        self.assertIn("line-height: 1.40;", epub_css)

    def test_epistemic_and_chekhov_gun_checks_and_scene_functions(self):
        self.write("kb/objects/OBJ-001-letter.md", "# OBJ-001: The letter\n")
        self.write("kb/plot/PLT-001-main.md", "# PLT-001: Main plot\n- **Time:** 1912\n- **Place:** [[PLC-001]]\n")

        # 1. Unearned payoff (Chekhov's gun violation)
        outline_unearned = OUTLINE.replace(
            "- **Where:** [[PLC-001]]",
            "- **Where:** [[PLC-001]]\n- **Pays off:** [[OBJ-001]]"
        )
        self.write("outline/outline.md", outline_unearned)
        code, res = self.json_cli("check")
        self.assertEqual(code, 1)
        self.assertTrue(any("unearned payoff" in e for e in res["errors"]))

        # 2. Orphan plant (Chekhov's gun violation)
        outline_orphan = OUTLINE.replace(
            "- **Where:** [[PLC-001]]",
            "- **Where:** [[PLC-001]]\n- **Plants:** [[OBJ-001]]"
        )
        self.write("outline/outline.md", outline_orphan)
        code, res = self.json_cli("check")
        self.assertEqual(code, 1)
        self.assertTrue(any("orphan plant" in e for e in res["errors"]))

        # 3. Valid Plant in SCN-001 and Payoff in SCN-002 resolves violation
        outline_valid = OUTLINE.replace(
            "- **Where:** [[PLC-001]]",
            "- **Where:** [[PLC-001]]\n- **Plants:** [[OBJ-001]]"
        ).replace(
            "- **Facts:** [[FCT-001]]",
            "- **Facts:** [[FCT-001]]\n- **Pays off:** [[OBJ-001]]"
        )
        self.write("outline/outline.md", outline_valid)
        code, res = self.json_cli("check")
        self.assertEqual(code, 0)

        # 4. Epistemic contradiction: same character declared learning and hidden from secret
        outline_ep_contradiction = outline_valid.replace(
            "- **Where:** [[PLC-001]]\n- **Plants:** [[OBJ-001]]",
            "- **Where:** [[PLC-001]]\n- **Plants:** [[OBJ-001]]\n- **Reveals:** [[PLT-001]]\n- **Learns:** [[CHR-001]]\n- **Hidden From:** [[CHR-001]]"
        )
        self.write("outline/outline.md", outline_ep_contradiction)
        code, res = self.json_cli("check")
        self.assertEqual(code, 1)
        self.assertTrue(any("epistemic contradiction" in e for e in res["errors"]))

        # 5. Epistemic violation: character acts on secret while declared hidden from them
        outline_ep_violation = outline_valid.replace(
            "- **Where:** [[PLC-001]]\n- **Plants:** [[OBJ-001]]",
            "- **Where:** [[PLC-001]]\n- **Plants:** [[OBJ-001]]\n- **Reveals:** [[PLT-001]]\n- **Learns:** [[CHR-001]]\n- **Hidden From:** [[CHR-002]]"
        ).replace(
            "- **Facts:** [[FCT-001]]\n- **Pays off:** [[OBJ-001]]",
            "- **Facts:** [[FCT-001]]\n- **Pays off:** [[OBJ-001]], [[PLT-001]]"
        )
        self.write("outline/outline.md", outline_ep_violation)
        code, res = self.json_cli("check")
        self.assertEqual(code, 1)
        self.assertTrue(any("epistemic violation" in e for e in res["errors"]))

        # 6. Atmospheric Breather function tag satisfies essentiality
        outline_breather = outline_valid.replace(
            "#### SCN-002: Karl refuses",
            "#### SCN-002: Karl refuses\n- **Function:** atmospheric-breather"
        )
        self.write("outline/outline.md", outline_breather)
        code, dag_res = self.json_cli("dag")
        self.assertEqual(code, 0)
        self.assertTrue(dag_res["ok"])

    def test_harvest_ingestion_and_scaffolding(self):
        sample_draft = (
            "# The Harbor Rendezvous\n\n"
            "Elena looked across the fog-shrouded piers of Southampton Harbor.\n\n"
            '"Where is the packet?" asked Karl.\n\n'
            '"I left it in the safe at Northam Tower," she replied.\n\n'
            "They walked along the quay in silence as the church bells rang.\n"
        )
        self.write("draft_sample.txt", sample_draft)

        # 1. Harvest dry run
        code, res = self.json_cli("harvest", "draft_sample.txt")
        self.assertEqual(code, 0)
        self.assertGreater(res["word_count"], 20)
        self.assertIn("Karl", res["entities"]["characters"])
        self.assertTrue(any("Southampton Harbor" in p or "Northam Tower" in p for p in res["entities"]["places"]))
        self.assertTrue(any("Where is the packet?" in d for d in res["dialogues"]))
        self.assertFalse(res["applied"])

        # 2. Harvest with --apply
        code, res_apply = self.json_cli("harvest", "draft_sample.txt", "--apply", "--batch", "-t", "Harbor Rendezvous")
        self.assertEqual(code, 0)
        self.assertTrue(res_apply["applied"])
        self.assertTrue((self.root / "outline" / "outline.md").is_file())
        outline_txt = (self.root / "outline" / "outline.md").read_text(encoding="utf-8")
        self.assertIn("Harbor Rendezvous", outline_txt)
        self.assertIn("SCN-", outline_txt)

    def test_folder_based_scenarios(self):
        # 1. Create scenario
        code, res = self.json_cli("scenario", "create", "alternate-ending", "-m", "Karl dies at sea")
        self.assertEqual(code, 0)
        self.assertTrue(res["created"])
        scen_outline = self.root / "story" / "scenarios" / "alternate-ending" / "outline.md"
        self.assertTrue(scen_outline.is_file())

        # 2. List scenarios
        code, scen_list = self.json_cli("scenario", "list")
        self.assertEqual(code, 0)
        self.assertEqual(len(scen_list), 1)
        self.assertEqual(scen_list[0]["name"], "alternate-ending")

        # 3. Modify scenario outline and diff
        scen_txt = scen_outline.read_text(encoding="utf-8")
        scen_outline.write_text(scen_txt + "\n#### SCN-099: Karl dies\n- **Where:** [[PLC-001]]\n", encoding="utf-8")
        code, diff_res = self.json_cli("scenario", "diff", "alternate-ending")
        self.assertEqual(code, 0)
        self.assertTrue(diff_res["has_diff"])
        self.assertIn("SCN-099", diff_res["diff"])

        # 4. Activate scenario
        code, act_res = self.json_cli("scenario", "activate", "alternate-ending")
        self.assertEqual(code, 0)
        self.assertTrue(act_res["activated"])
        main_outline_txt = (self.root / "outline" / "outline.md").read_text(encoding="utf-8")
        self.assertIn("SCN-099: Karl dies", main_outline_txt)
        self.assertTrue((self.root / "story" / "scenarios" / ".previous_main_outline.md").is_file())

        # 5. Merge and Delete
        code, m_res = self.json_cli("scenario", "merge", "alternate-ending")
        self.assertEqual(code, 0)
        code, d_res = self.json_cli("scenario", "delete", "alternate-ending")
        self.assertEqual(code, 0)
        self.assertFalse((self.root / "story" / "scenarios" / "alternate-ending").exists())

    def test_developmental_editorial_telemetry_audit(self):
        outline_with_data = OUTLINE.replace(
            "- **Where:** [[PLC-001]]",
            "- **Where:** [[PLC-001]]\n- **Plants:** [[OBJ-001]]\n- **Reveals:** [[PLT-001]]\n- **Learns:** [[CHR-001]]\n- **Hidden From:** [[CHR-002]]",
            1
        ).replace(
            "- **Facts:** [[FCT-001]]",
            "- **Facts:** [[FCT-001]]\n- **Pays off:** [[OBJ-001]]"
        )
        self.write("outline/outline.md", outline_with_data)
        self.write("manuscript/en-US/CHP-001.md", "# CHP-001: The Letter\n\n## SCN-001: Elena\n\"The secret is out,\" Elena whispered into the dark room. Karl nodded.\n\n## SCN-002: Karl\n\"We must move quickly,\" Karl said, checking his revolver.\n")

        code, res = self.json_cli("audit")
        self.assertEqual(code, 0)
        self.assertIn("summary", res)
        self.assertGreaterEqual(res["summary"]["total_scenes"], 2)
        self.assertIn("waveform", res)
        self.assertEqual(len(res["waveform"]), 3)
        self.assertGreater(res["waveform"][0]["dialogue_ratio"], 0.0)

        # Chekhov gun matrix
        self.assertIn("chekhov_matrix", res)
        self.assertEqual(len(res["chekhov_matrix"]), 1)
        self.assertEqual(res["chekhov_matrix"][0]["entity"], "OBJ-001")
        self.assertEqual(res["chekhov_matrix"][0]["plant_scene"], "SCN-001")
        self.assertEqual(res["chekhov_matrix"][0]["payoff_scene"], "SCN-002")

        # Epistemic matrix
        self.assertIn("epistemic_matrix", res)
        self.assertIn("PLT-001", res["epistemic_matrix"])
        self.assertEqual(res["epistemic_matrix"]["PLT-001"]["learns"], ["CHR-001"])
        self.assertEqual(res["epistemic_matrix"]["PLT-001"]["hidden_from"], ["CHR-002"])

    def test_baseline_driven_metrics_cache_and_deep_telemetry(self):
        outline_with_data = OUTLINE.replace(
            "- **Where:** [[PLC-001]]",
            "- **Where:** [[PLC-001]]\n- **Plants:** [[OBJ-001]]",
            1
        ).replace(
            "- **Facts:** [[FCT-001]]",
            "- **Facts:** [[FCT-001]]\n- **Pays off:** [[OBJ-001]]"
        )
        self.write("outline/outline.md", outline_with_data)
        self.write("kb/objects/OBJ-001-lock.md", "# OBJ-001: Brass Lock\n- **Category:** Prop\n")
        # Prose with sensory terms, cliché, and passive voice
        prose_scn1 = (
            "# CHP-001: The Letter\n\n"
            "## SCN-001: Elena receives the letter\n"
            "Elena opened the cold brass lock as a chill ran down her spine. "
            "A cold sweat broke out across her forehead. "
            "The iron envelope was taken by Karl in dead silence.\n\n"
            "## SCN-002: Karl refuses\n"
            "Karl listened to the distant church bells echoing across the foggy harbor. "
            "\"We must not fail,\" he whispered.\n"
        )
        self.write("manuscript/en-US/CHP-001.md", prose_scn1)
        self.write("abridged/CHP-001.md", prose_scn1)
        self.write("story/acknowledgements.md", "## Acknowledgements\nWritten with Claude and Gemini.\n")

        # 1. Accept initial manuscript baseline with --force
        self.run_cli("accept", "--stage", "manuscript", "-m", "Initial baseline", "--force")

        # 2. Run deep audit
        code, res_deep = self.json_cli("audit", "--deep")
        self.assertEqual(code, 0)
        self.assertIn("sensory_palette", res_deep)
        self.assertGreater(res_deep["sensory_palette"]["tactile"], 0)
        self.assertGreater(res_deep["sensory_palette"]["auditory"], 0)
        self.assertGreater(res_deep["summary"]["total_cliches"], 0)
        self.assertGreater(res_deep["summary"]["total_passive_constructions"], 0)

        # 3. Verify metrics cache file created
        cache_file = self.root / ".specnovel" / "metrics_cache.json"
        self.assertTrue(cache_file.is_file())
        cache_json = json.loads(cache_file.read_text(encoding="utf-8"))
        self.assertIn("SCN-001", cache_json["scenes"])
        self.assertIn("cliches", cache_json["scenes"]["SCN-001"])

        # 4. Single-scene drill-down
        code, res_scene = self.json_cli("audit", "--scene", "SCN-001")
        self.assertEqual(code, 0)
        self.assertEqual(res_scene["scene_id"], "SCN-001")
        self.assertGreater(len(res_scene["cliches"]), 0)
        self.assertTrue(any("cold sweat" in c["cliche"] for c in res_scene["cliches"]))
        self.assertGreater(res_scene["passive_count"], 0)
        self.assertGreater(res_scene["cadence_entropy"], 0.0)

        # 5. Upstream Semantic Invalidation: modify referenced place kb/places/PLC-001-harbor.md
        # Notice that prose in manuscript/en-US/CHP-001.md is NOT touched!
        self.write("kb/places/PLC-001-harbor.md", PLACE + "\n- **Sensory Note:** sulfur and hot grease.\n")
        code, res_recheck = self.json_cli("audit")
        self.assertEqual(code, 0)
        # SCN-001 references PLC-001, so it must be detected as dirty!
        self.assertGreaterEqual(res_recheck["summary"]["dirty_scenes_count"], 1)

        # 6. Longitudinal Delta: compare against baseline
        code, res_delta = self.json_cli("audit", "--compare", "baseline")
        self.assertEqual(code, 0)
        self.assertIn("baseline_sha", res_delta)
        self.assertIn("metrics", res_delta)
        self.assertIn("word_count", res_delta["metrics"])
        self.assertIn("sensory_density_per_k", res_delta["metrics"])

    def test_versioned_scene_takes(self):
        self.write(
            "manuscript/en-US/CHP-001.md",
            "# CHP-001: The Letter\n\n## SCN-001: Elena\nElena opened the envelope with trembling hands.\n\n## SCN-002: Karl\nKarl turned away.\n"
        )

        # 1. Save take
        code, res = self.json_cli("takes", "save", "SCN-001", "default-third", "-m", "Third person draft")
        self.assertEqual(code, 0)
        self.assertTrue(res["saved"])
        take_file = self.root / "story" / "takes" / "SCN-001" / "default-third.md"
        self.assertTrue(take_file.is_file())

        # 2. List takes
        code, t_list = self.json_cli("takes", "list", "SCN-001")
        self.assertEqual(code, 0)
        self.assertEqual(len(t_list), 1)
        self.assertEqual(t_list[0]["take"], "default-third")

        # 3. Create a second take file
        noir_file = self.root / "story" / "takes" / "SCN-001" / "noir-first.md"
        noir_file.write_text(
            "---\nscene: SCN-001\ntake: noir-first\nlayer: manuscript\n---\n\n## SCN-001: Elena\nI sliced the envelope with an ivory blade.\n",
            encoding="utf-8"
        )

        # 4. Diff takes
        code, diff_res = self.json_cli("takes", "diff", "SCN-001", "default-third", "noir-first")
        self.assertEqual(code, 0)
        self.assertTrue(diff_res["has_diff"])
        self.assertIn("ivory blade", diff_res["diff"])

        # 5. Activate take into manuscript
        code, act_res = self.json_cli("takes", "activate", "SCN-001", "noir-first")
        self.assertEqual(code, 0)
        self.assertEqual(act_res["activated_take"], "noir-first")
        ms_txt = (self.root / "manuscript" / "en-US" / "CHP-001.md").read_text(encoding="utf-8")
        self.assertIn("I sliced the envelope with an ivory blade", ms_txt)
        # Ensure SCN-002 was not clobbered
        self.assertIn("## SCN-002: Karl", ms_txt)
        self.assertIn("Karl turned away.", ms_txt)

        # 6. Delete take
        code, del_res = self.json_cli("takes", "delete", "SCN-001", "default-third")
        self.assertEqual(code, 0)
        self.assertFalse(take_file.exists())


if __name__ == "__main__":
    unittest.main()
