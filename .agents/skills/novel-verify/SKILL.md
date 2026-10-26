---
name: novel-verify
description: >-
  Audits continuity, fact fidelity, Narrative DAG causality, topological physical serialization, directive
  preservation, and style compliance across the 9-stage SpecNovelist project (initial/, setup/, research/,
  world/, narrative/, structure/, abridged/, manuscript/, publishable/, and directives/). Detects manual drift
  in derived drafts and triages defects to the authoritative stage.
---

# `novel-verify` — 9-Stage Continuity, Causality & Quality Assurance

`novel-verify` is the diagnostic and quality-assurance engine of the SpecNovelist methodology. It audits alignment across all 9 project stages (`initial/`, `setup/`, `research/`, `world/`, `narrative/`, `structure/`, `abridged/`, `manuscript/`, `publishable/`) and the cross-stage `directives/` repository.

* **Verification checklists**: [audit-checklists.md](references/audit-checklists.md)
* **Helper**: `uv run python scripts/specnovel.py <command>`

---

## 1. Structural, Traceability, Narrative DAG & Directive Audit
Run the automated integrity suite:
```bash
uv run python scripts/specnovel.py check
uv run python scripts/specnovel.py dag
```
Verifies:
- **Stage 5 Unified Narrative DAG (`narrative/`)**:
  - Every beat (`BET-NNN` in `narrative/beats.md`) has a valid `Place: [[PLC-NNN]]`, `Time:`, and at least one story arc `Arcs: [[ARC-NNN]]`.
  - Every narrative illustration (`ILL-NNN` in `narrative/illustrations.md`) is a first-class node in the Narrative DAG governed by `Dependencies:` (`[[BET-NNN]]`, `[[ILL-NNN]]`), and is associated with at least one story arc `Arcs: [[ARC-NNN]]` (with the exception of cover and front/back matter illustrations).
  - **Acyclicity**: Narrative DAG dependencies (`Dependencies: [[BET-NNN]]`, `[[ILL-NNN]]`) form a strict DAG with zero cycles.
  - **Denouement Root**: The Narrative DAG has a root marked `Denouement: true`, and every beat has a directed causal path leading to the denouement (no dead-end beats unless exempted by `Function:`).
- **Stage 6 Physical Structure Serialization (`structure/outline.md`)**:
  - Every node (`BET-NNN` or `ILL-NNN`) that depends on an earlier node in Stage 5 appears *after* its dependency in the physical reading order of scenes (`SCN-NNN`) in `structure/outline.md`.
  - No beat is accidentally scheduled in multiple scenes (`duplicate beat scheduling`).
- **Directives Integrity (`directives/DIR-NNN.md`)**:
  - Every `DIR-NNN` has valid `Status:`, `Locale:`, `Stage:`, and `Scope:` metadata.
  - **Directive Preservation**: No updated record in any stage has dropped a `[[DIR-NNN]]` link that was present in its baseline commit.
- **Stage 1–4 & 7–9 Integrity**:
  - `initial/config.md` conforms strictly to the schema (author identity, target locales with `[primary]`, foreword path if enabled, compilation flags), and `initial/synopsis.md` is present.
  - `setup/style.md` includes `# Locale: <locale>` for every configured locale, `## Glossary Guidelines`, `## Graphics Guidelines`, and `## Publication & Book Design Guidelines`.
  - `structure/back-matter/acknowledgements.md` exists, is non-empty, and discloses all contributing AI models (`uv run python scripts/specnovel.py models`).
  - All cataloged IDs are unique (`THM`, `RQ`, `FCT`, `SRC`, `CHR`, `PLC`, `ORG`, `OBJ`, `WLD`, `TML`, `GLS`, `ARC`, `BET`, `ILL`, `VOL`, `ACT`, `CHP`, `SCN`, `DIR`).
  - No dangling wiki-links (`[[ID]]`) exist.
  - All researched facts (`FCT` in `world/facts/`) cite valid source records (`SRC` in `world/sources/`).
  - Derived chapters and scenes in `abridged/` and `manuscript/<locale>/` match `structure/outline.md` in order and hierarchy across all target locales.
  - Localized illustration assets in `publishable/graphics/` (`ILL-NNN.<locale>.png`) match manuscript links or fall back cleanly to `ILL-NNN.png`.
  - No raw `[[ID]]` markup or unresolved `[...]` placeholders leak into final `manuscript/` prose.

To inspect the traceability and usage matrix for any entity across all 9 stages:
```bash
uv run python scripts/specnovel.py trace CHR-001
uv run python scripts/specnovel.py trace BET-001
uv run python scripts/specnovel.py trace ILL-001
uv run python scripts/specnovel.py trace DIR-001
```

---

## 2. Continuity & Epistemic Audit

### A. Character & Timeline Continuity (`world/`)
- **Physical Traits**: Audit `manuscript/` and `abridged/` against `world/characters/CHR-NNN.md`.
- **Timeline & Travel**: Audit Beat `Time:` and `Place:` transitions against `world/timeline/` and `world/places/`, and verify that scene `Where:` settings align with their sequenced beats' `Place:`.

### B. Information & Epistemic Audit
- Track secrets and reveals via `Reveals:`, `Learns:`, and `Hidden From:` on scenes/beats.
- `specnovel.py check` enforces that characters never act on information before learning it or while listed under `Hidden From:`.

### C. Chekhov's Gun Setup & Payoff Audit
- Every entity planted via `- **Plants:** [[OBJ-NNN]]` must have a matching `- **Pays off:** [[OBJ-NNN]]` later in reading order.

---

## 3. Fact & Style Compliance Audit
- **Fact Fidelity**: Verify that scenes and beats referencing `[[FCT-NNN]]` honor the claim and sources in `world/facts/` and `world/sources/`.
- **Style & Directive Compliance**: Audit `manuscript/<locale>/` against `setup/style.md` (`# Locale: <locale>`) and all active `directives/DIR-NNN.md` linked to each chapter, scene, beat, or character.

---

## 4. Defect Triage & Routing
When a defect is found:
1. Identify the earliest stage (`1..9` or `directives/`) where the defect originates.
2. Route fixes through **`novel-feedback`** (to update upstream specs and lock in a `DIR-NNN` directive if needed) followed by **`novel-sync`** to propagate the fix downstream.
