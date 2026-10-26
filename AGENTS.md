# SpecNovelist Agent Guidelines (Always Active)

This project operates on the **Spec-as-Source** paradigm adapted for fiction writing.
In this repository, **structured Markdown specifications across a 9-stage pipeline plus a cross-stage `directives/` repository are the source of truth**, while the narrative drafts in `abridged/`, `manuscript/`, and `publishable/` are derived stages generated and synchronized by AI writing agents.

---

## 1. The 9-Stage Project Architecture & Directives

Each of the 9 project stages lives in its own top-level subdirectory, accompanied by the cross-stage `directives/` subdirectory:

1. **`initial/` (Stage 1 — Initial)**:
   - `synopsis.md`: The seed synopsis.
   - `config.md`: **Project Configuration Specification.** Strict Markdown schema defining Author Identity, target locales (with one designated `[primary]`), optional foreword path, glossary and bibliography compilation toggles, and publication metadata.
2. **`setup/` (Stage 2 — Setup)**:
   - `brief.md`: Creative parameters: premise, genre, audience, length, POV, setting eras, research rigor.
   - `themes.md`: Core themes (`THM-NNN`).
   - `style.md`: **Binding writing-style guide** governing voice, rhythm, POV, diction, dialogue conventions, interiority, glossary guidelines (`## Glossary Guidelines`), illustration guidelines (`## Graphics Guidelines`), book design guidelines (`## Publication & Book Design Guidelines`), and locale-specific sections (`# Locale: <locale>`).
3. **`research/` (Stage 3 — Research Questions)**:
   - `questions.md`: Cataloged world-building and factual research questions (`RQ-NNN`).
4. **`world/` (Stage 4 — World)**:
   - `facts/` (`FCT-NNN`, answers to research questions citing verified sources in `sources/SRC-NNN.md`), `characters/` (`CHR-NNN`), `places/` (`PLC-NNN`), `organizations/` (`ORG-NNN`), `objects/` (`OBJ-NNN`), `rules/` (`WLD-NNN`), `timeline/` (`TML-NNN`), and `glossary/` (`GLS-NNN`).
5. **`narrative/` (Stage 5 — Narrative Structure)**:
   - `arcs.md`: Story arcs (`ARC-NNN`).
   - `beats.md`: Narrative beats (`BET-NNN`). Every beat **must** specify a `Place:` (`[[PLC-NNN]]`), a `Time:`, and at least one associated story arc in `Arcs:` (`[[ARC-NNN]]`).
   - `illustrations.md`: Textual descriptions of illustrations (`ILL-NNN`). At Stage 5, illustrations are purely textual specifications, not graphical files. Like beats, every illustration **must** be associated with at least one story arc in `Arcs:` (`[[ARC-NNN]]`), with the exception of illustrations used for covers (`Type: cover`) and front/back matter (`Type: front-matter` | `back-matter`).
   - **Unified Narrative DAG**: Beats (`BET-NNN`) and illustrations (`ILL-NNN`) are both nodes in the **Narrative DAG**, governed by `Dependencies:` (`[[BET-NNN]]`, `[[ILL-NNN]]`) referring to earlier nodes required for causality, narrative coherence, or dramatic effect. Do **not** use an "Associated Beats" field on illustrations—relations between beats and illustrations are governed strictly by DAG dependencies. The root of the Narrative DAG is the **denouement** (`Denouement: true`).
6. **`structure/` (Stage 6 — Physical Structure)**:
   - `outline.md`: The physical organization of the book in reading order: Volumes (`VOL-NNN`), Acts (`ACT-NNN`), Chapters (`CHP-NNN`), and Scenes (`SCN-NNN` — each containing an ordered sequence of beats `[[BET-NNN]]` and illustrations `[[ILL-NNN]]`, target word count, POV, setting, and key dialogue).
   - `front-matter/` and `back-matter/acknowledgements.md` (**Mandatory Verbatim Acknowledgements** disclosing all contributing AI models).
7. **`abridged/` (Stage 7 — Abridged Novel)**:
   - Condensed chapter drafts (`abridged/CHP-NNN.md`) containing all beats, causal turns, and essential dialogues with lean descriptive texture.
8. **`manuscript/` (Stage 8 — Manuscript)**:
   - Polished literary prose organized by locale (`manuscript/<locale>/CHP-NNN.md`), rendered from `abridged/` + `setup/style.md` + `world/` + `directives/`. Zero visible metadata.
9. **`publishable/` (Stage 9 — Publishable Material)**:
   - `publishable/graphics/`: Rendered graphical assets (`ILL-NNN.png` and localized variants `ILL-NNN.<locale>.png`) generated from `narrative/illustrations.md` for active illustrations placed in `structure/outline.md`.
   - `publishable/<locale>/`: Compiled books in `.md`, `.docx`, `.epub`, and `.pdf` formats via `specnovel.py compile`, with auto-generated bibliographies and glossaries.
10. **`directives/` (Cross-Stage Directives Repository)**:
   - Stores cataloged directives (`directives/DIR-NNN.md`): instructions that do not fall into any other data category.
   - Data records at **any** stage may reference `[[DIR-NNN]]` via `- **Directives:** [[DIR-NNN]]`.
   - Directives serve two core purposes:
     1. **Locking in user feedback** so that freeform constraints continue to take effect when downstream content is regenerated during synchronization.
     2. **DRY Factoring (Single Source of Truth)**: Generation and synchronization skills must automatically use directives to factor special instructions that need to be applied across multiple records.

---

## 2. Core Operational Rules for Agents

1. **9-Stage Upstream Truth & Synchronization Generation Gate**:
   - Never edit downstream stages (`abridged/`, `manuscript/`, `publishable/`) to alter plot events, character decisions, or world facts without updating the upstream stage (`initial/`, `setup/`, `research/`, `world/`, `narrative/`, `structure/`, or `directives/`) first.
   - **Synchronization Generation Gate**: Synchronization (`novel-sync`, `specnovel.py delta --stage <stage>`, `specnovel.py impact --stage <stage>`) **cannot** be performed on a stage until initial generation (`novel-generate` + `specnovel.py accept --stage <stage>`) has been performed at least once for that stage.
2. **Permanent IDs & Traceability**:
   - Every cataloged entity has a permanent, unique identifier (`PREFIX-NNN`: `THM`, `RQ`, `FCT`, `SRC`, `CHR`, `PLC`, `ORG`, `OBJ`, `WLD`, `TML`, `GLS`, `ARC`, `BET`, `ILL`, `VOL`, `ACT`, `CHP`, `SCN`, `DIR`).
   - Allocate new IDs exclusively via `uv run python scripts/specnovel.py next-id <PREFIX>`.
   - Cross-references use `[[ID]]` or `[[ID|display text]]`.
3. **No Researched Facts Without Verified Sources**:
   - Every fact (`FCT` in `world/facts/`) must cite at least one verified source record (`SRC` in `world/sources/`) and link to the research question (`RQ` in `research/questions.md`) it resolves.
   - Convert `[...]` or `<...>` placeholders into `RQ-NNN` items via `uv run python scripts/specnovel.py placeholders --create-rq`.
4. **Stage 5 Narrative DAG & Stage 6 Topological Serialization**:
   - Every `BET-NNN` in `narrative/beats.md` must have `Place: [[PLC-NNN]]`, `Time:`, `Arcs: [[ARC-NNN]]`, and `Dependencies: [[BET-NNN]]` / `[[ILL-NNN]]` (or `none`).
   - Every `ILL-NNN` in `narrative/illustrations.md` is a node in the Narrative DAG with `Dependencies:` (`[[BET-NNN]]`, `[[ILL-NNN]]`, or `none`) and must have `Arcs: [[ARC-NNN]]` unless used for covers or front/back matter.
   - The Narrative DAG must be acyclic and rooted at the final denouement (`- **Denouement:** true`), with every beat having a directed path to the denouement.
   - In Stage 6 (`structure/outline.md`), scenes (`SCN-NNN`) sequence beats (`[[BET-NNN]]`) and illustrations (`[[ILL-NNN]]`). Every node's dependencies must precede it in the physical reading order of `structure/outline.md`.
   - Validate via `uv run python scripts/specnovel.py dag` and `uv run python scripts/specnovel.py check`.
5. **Directives: Preservation, Auto-Linking, and DRY Factoring**:
   - **Preservation**: Synchronization tasks updating an existing record must respect and preserve all `[[DIR-NNN]]` references attached to that record (`specnovel.py check` blocks dropped directives).
   - **Auto-Linking**: When a generation or synchronization task creates a new data record, it must automatically link pre-existing `DIR-NNN` directives whose `Scope:` is relevant to the new record (`uv run python scripts/specnovel.py directives link --apply`, also invoked automatically during `accept`).
   - **Automatic Factoring**: Generation and synchronization skills must automatically use `uv run python scripts/specnovel.py directives factor` to factor special instructions that apply in multiple places into a single `DIR-NNN` record.
6. **Mandatory AI Model Tracking & Verbatim Acknowledgements**:
   - Every AI model utilized by contributing agents must be recorded via `Novel-Model:` Git trailers (`specnovel.py accept --stage <stage> --model <model>`) and acknowledged verbatim in `structure/back-matter/acknowledgements.md` (verified by `specnovel.py check` and `specnovel.py models`).
7. **Epistemic Integrity, Chekhov's Guns & Telemetry**:
   - `specnovel.py check` enforces epistemic rules (`Reveals:`, `Learns:`, `Hidden From:`) and Chekhov setups/payoffs (`Plants:`, `Pays off:`).
   - `specnovel.py audit` (and `audit --report`) computes developmental and style-reflective telemetry across the project.
8. **Manual Pipeline Progression, Stage Isolation & UI Review**:
   - Agents execute only the specific skill and target stage requested by the author.
   - Once a skill completes its task for the target stage, the agent must conclude its turn without chaining into subsequent pipeline stages, without invoking next-stage skills, and without prompting or asking the author whether they want to proceed or advance to the next stage.
   - Leave modified and generated files unstaged in Git for author review in the UI unless explicitly instructed to run `specnovel.py accept`.

---

## 3. Skill Categories & Dispatch Guide

The creation and maintenance process uses **3 core operational skill categories** plus **2 diagnostic skills**:

| Category / Skill | Primary Role | When to Activate |
|---|---|---|
| **1. Generation (`novel-generate`)** | Initial Stage Data Generation & Directive Factoring | When generating data for any of the 9 stages (`initial`, `setup`, `research`, `world`, `narrative`, `structure`, `abridged`, `manuscript`, `publishable`) for the first time based on earlier stages and author interview questions. Automatically factors shared instructions into `DIR-NNN` directives and commits the initial stage baseline. |
| **2. Synchronization (`novel-sync`)** | Incremental Stage Synchronization | When incrementally updating a stage based on edits made to earlier stages. Requires initial generation to have been completed at least once for the target stage. Respects and preserves existing `[[DIR-NNN]]` directives, auto-links relevant directives to newly created records, and factors shared instructions into directives. |
| **3. Feedback (`novel-feedback`)** | Freeform Feedback Triage & Directive Lock-In | When editing project data across stages in response to freeform author/editor feedback, and creating or factoring `DIR-NNN` directives in `directives/` to lock in user feedback across future synchronizations. |
| **Diagnostic: `novel-verify`** | Continuity, Narrative DAG & Quality Assurance | When auditing Narrative DAG causality, topological physical serialization, fact fidelity, directive preservation, style compliance, or triaging defects. |
| **Diagnostic: `novel-analyze`** | Developmental Editorial & Style Telemetry | When generating metrics-driven analysis reports (`specnovel.py audit --report`), comparing style-reflective metrics against `setup/style.md`, auditing cross-chapter consistency, and zooming in on structural or prose hotspots with `[[ID]]` wiki-links. |
