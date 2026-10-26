---
name: novel-analyze
description: >-
  Generates in-depth developmental editorial and style analysis reports focused on metrics across the
  9-stage SpecNovelist pipeline. Differentiates between raw quality indicators (Narrative DAG violations,
  pacing sags, Chekhov gun gaps, passive phrasing, clichés, epistemic leaks) and style-reflective metrics
  (sentence rhythm, cadence entropy, dialogue ratio, sensory palettes, visual illustration intensity).
  Evaluates alignment with setup/style.md and active directives (directives/DIR-NNN.md), audits
  cross-chapter style consistency, and zooms in across narrative structure (ARC, BET, ILL), physical
  structure (VOL, ACT, CHP, SCN), paragraphs/sentences, and world entities using [[ID]] wiki-links.
---

# `novel-analyze` — Developmental Editorial & Style Telemetry Engine

`novel-analyze` is the developmental editing, literary metrics, and stylistic telemetry engine of SpecNovelist. It synthesizes computational metrics and editorial craft analysis into structured, actionable reports to guide the author's creative revisions while maintaining full artistic control.

* **Analysis Guide**: [analysis-guide.md](references/analysis-guide.md)
* **Report Template**: [report-template.md](references/report-template.md)
* **Automated Telemetry CLI**: `uv run python scripts/specnovel.py audit --report`

---

## Core Philosophy: Raw Quality vs. Style-Reflective Metrics

1. **Raw Quality Indicators**:
   - Universal narrative and technical integrity criteria: Narrative DAG cycles or dead ends (`narrative/beats.md`, `narrative/illustrations.md`), topological serialization errors (`structure/outline.md`), epistemic leaks, unresolved Chekhov plants, pacing sags, clichés, and passive voice hotspots.
2. **Style-Reflective Metrics**:
   - Technical values reflecting conscious artistic choices declared in `setup/style.md` and `directives/DIR-NNN.md`: sentence length, cadence entropy ($H_{cad}$), dialogue ratio, sensory palette distribution, and illustration intensity (`ILL-NNN`).
   - Evaluated against **fidelity to `setup/style.md`** and **cross-chapter consistency throughout the novel**.

---

## Multi-Level Zoom-In Protocol

The analysis report zooms in systematically across all 9 project stages:
1. **Narrative Structure (`narrative/` — `ARC-NNN`, `BET-NNN`, `ILL-NNN`)**:
   - Evaluates Narrative DAG momentum, story arc density, turning point distribution, and Chekhov gun setup/payoff distance gaps.
2. **Physical Structure & Chapter Level (`structure/outline.md` — `VOL`, `ACT`, `CHP-NNN`)**:
   - Audits cross-chapter style variance ($\sigma_{sent}^2$, $H_{cad}$ shifts, dialogue ratio shifts).
3. **Scene Level (`SCN-NNN`)**:
   - Audits narrative velocity ($V_n$, beats/plot shifts per thousand words), emotional valence ($E_v$), cast agency, and sensory palette balance.
4. **Paragraph & Sentence Level (`file://...#Lxx`)**:
   - Pinpoints exact file paths and line numbers in `manuscript/<locale>/` or `abridged/` for passive clusters, clichés, and monotone rhythm runs.
5. **World Entities (`world/` — `CHR`, `PLC`, `ORG`, `OBJ`, `FCT`)**:
   - Audits character agency/screen-time distribution, setting sensory grounding, and organic fact integration.
6. **Illustrations & Directives (`narrative/illustrations.md`, `publishable/graphics/`, `directives/DIR-NNN.md`)**:
   - Audits `[[ILL-NNN]]` placement against `setup/style.md` > `## Graphics Guidelines` and verifies compliance with linked `[[DIR-NNN]]` directives.

---

## Step-by-Step Execution Workflow

1. **Run Automated Telemetry**:
   ```bash
   uv run python scripts/specnovel.py audit --report --output reports/analysis.md
   uv run python scripts/specnovel.py audit --compare baseline
   uv run python scripts/specnovel.py audit --scene SCN-001
   ```
2. **Ingest `setup/style.md` & `directives/`**:
   - Compare observed metrics against the target voice, rhythm, sensory modalities, and graphics guidelines in `setup/style.md`.
3. **Format Report with Wiki-Links**:
   - Reference all project entities using wiki-links (`[[ARC-001]]`, `[[BET-001]]`, `[[ILL-001]]`, `[[SCN-001]]`, `[[CHP-001]]`, `[[CHR-001]]`, `[[PLC-001]]`, `[[FCT-001]]`, `[[DIR-001]]`).
4. **Triage into Actionable Feedback**:
   - Route recommended changes to **`novel-feedback`** (to update upstream specs or factor new `DIR-NNN` directives in `directives/`).
