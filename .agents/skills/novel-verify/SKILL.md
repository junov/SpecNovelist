---
name: novel-verify
description: >-
  Audits continuity, fact fidelity, Beat DAG causality, topological physical serialization, directive
  preservation, and style compliance across the 8-stage SpecNovelist project (setup/, research/, world/,
  narrative/, structure/, abridged/, manuscript/, publishable/, and directives/). Detects manual drift
  in derived drafts and triages defects to the authoritative stage.
---

# `novel-verify` — 8-Stage Continuity, Causality & Quality Assurance

`novel-verify` is the diagnostic and quality-assurance engine of the SpecNovelist methodology. It audits alignment across all 8 project stages (`setup/`, `research/`, `world/`, `narrative/`, `structure/`, `abridged/`, `manuscript/`, `publishable/`) and the cross-stage `directives/` repository.

* **Verification checklists**: [audit-checklists.md](references/audit-checklists.md)
* **Helper**: `uv run python scripts/specnovel.py <command>`

---

## 1. Structural, Traceability, Beat DAG & Directive Audit
Run the automated integrity suite:
```bash
uv run python scripts/specnovel.py check
uv run python scripts/specnovel.py dag
```
Verifies:
- **Stage 4 Narrative Beat DAG (`narrative/`)**:
  - Every beat (`BET-NNN` in `narrative/beats.md`) has a valid `Place: [[PLC-NNN]]`, `Time:`, and at least one story arc `Arcs: [[ARC-NNN]]`.
  - **Acyclicity**: Beat dependencies (`Dependencies: [[BET-NNN]]`) form a strict DAG with zero cycles.
  - **Denouement Root**: The Beat DAG has a root marked `Denouement: true`, and every beat has a directed causal path leading to the denouement (no dead-end beats).
- **Stage 5 Physical Structure Serialization (`structure/outline.md`)**:
  - Every beat `BET-B` that depends on `BET-A` in Stage 4 appears *after* `BET-A` in the physical reading order of scenes (`SCN-NNN`) in `structure/outline.md`.
- **Directives Integrity (`directives/DIR-NNN.md`)**:
  - Every `DIR-NNN` has valid `Status:`, `Locale:`, and `Scope:` metadata.
  - **Directive Preservation**: No updated record in any stage has dropped a `[[DIR-NNN]]` link that was present in its baseline commit.
- **Stage 1–3 & 6–8 Integrity**:
  - `setup/config.md` conforms strictly to the schema (author identity, target locales with `[primary]`, foreword path if enabled, compilation flags).
  - `structure/back-matter/acknowledgements.md` exists, is non-empty, and discloses all contributing AI models (`uv run python scripts/specnovel.py models`).
  - All cataloged IDs are unique (`THM`, `RQ`, `FCT`, `SRC`, `CHR`, `PLC`, `ORG`, `OBJ`, `WLD`, `TML`, `GLS`, `ARC`, `BET`, `ILL`, `VOL`, `ACT`, `CHP`, `SCN`, `DIR`).
  - No dangling wiki-links (`[[ID]]`) exist.
  - All researched facts (`FCT` in `world/facts/`) cite valid source records (`SRC` in `world/sources/`).
  - Derived chapters and scenes in `abridged/` and `manuscript/<locale>/` match `structure/outline.md` in order and hierarchy.
  - Localized illustration assets in `publishable/graphics/` (`ILL-NNN.<locale>.png`) match manuscript links or fall back cleanly to `ILL-NNN.png`.
  - No raw `[[ID]]` markup leaks into final `manuscript/` prose.

To inspect the traceability and usage matrix for any entity across all 8 stages:
```bash
uv run python scripts/specnovel.py trace CHR-001
uv run python scripts/specnovel.py trace BET-001
uv run python scripts/specnovel.py trace DIR-001
```

---

## 2. Continuity & Epistemic Audit

### A. Character & Timeline Continuity (`world/`)
- **Physical Traits**: Audit `manuscript/` and `abridged/` against `world/characters/CHR-NNN.md`.
- **Timeline & Travel**: Audit Beat `Time:` and `Place:` transitions against `world/timeline/` and `world/places/`.

### B. Information & Epistemic Audit
- Track secrets and reveals via `Reveals:`, `Learns:`, and `Hidden From:` on scenes/beats.
- `specnovel.py check` enforces that characters never act on information before learning it or while listed under `Hidden From:`.

### C. Chekhov's Gun Setup & Payoff Audit
- Every entity planted via `- **Plants:** [[OBJ-NNN]]` must have a matching `- **Pays off:** [[OBJ-NNN]]` later in reading order.

---

## 3. Fact & Style Compliance Audit
- **Fact Fidelity**: Verify that scenes referencing `[[FCT-NNN]]` honor the claim and sources in `world/facts/` and `world/sources/`.
- **Style & Directive Compliance**: Audit `manuscript/<locale>/` against `setup/style.md` (`# Locale: <locale>`) and all active `directives/DIR-NNN.md` linked to each chapter, scene, beat, or character.

---

## 4. Defect Triage & Routing
When a defect is found:
1. Identify the earliest stage (`1..8` or `directives/`) where the defect originates.
2. Route fixes through **`novel-feedback`** (to update upstream specs and lock in a `DIR-NNN` directive if needed) followed by **`novel-sync`** to propagate the fix downstream.
