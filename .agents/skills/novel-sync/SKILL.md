---
name: novel-sync
description: Category 2 (Synchronization) skill for SpecNovelist. Incrementally updates data for any of the 9 project stages (initial, setup, research, world, narrative, structure, abridged, manuscript, publishable) based on edits made to earlier stages. Enforces the Synchronization Generation Gate (cannot run until initial generation has been performed at least once for the target stage), respects and preserves existing [[DIR-NNN]] directives on updated records, automatically links relevant pre-existing directives to newly created records, and uses directives as a DRY factoring single source of truth.
---

# `novel-sync` — Incremental Stage Synchronization Engine

This skill implements **Category 2: Synchronization** across the 9-stage SpecNovelist pipeline. When upstream stages (`initial`, `setup`, `research`, `world`, `narrative`, `structure`, `abridged`, `manuscript`) are edited, `novel-sync` computes the exact impact delta and incrementally updates the target stage while enforcing directive preservation, automatic directive linking on new records, and DRY directive factoring.

---

## 1. Core Synchronization Invariants

1. **The Synchronization Generation Gate**:
   - Synchronization **cannot** be performed on a stage until initial generation (`novel-generate`) has been performed and committed (`accept --stage <stage>`) at least once for that stage.
   - Running `uv run python scripts/specnovel.py delta --stage <stage>` or `uv run python scripts/specnovel.py impact --stage <stage>` on an ungenerated stage will fail with a Generation Gate error. If a stage has no baseline yet, hand off to `novel-generate` first.
2. **Directive Preservation on Updated Records**:
   - Every record in any stage may carry references to `[[DIR-NNN]]` directives in `directives/`.
   - When updating an existing record during synchronization, you **must**:
     1. Read every active `DIR-NNN` referenced by that record (or by its upstream entities).
     2. Apply the directive's instructions when regenerating or revising the record's content.
     3. **Preserve all existing `[[DIR-NNN]]` links** on the record (`uv run python scripts/specnovel.py check` verifies that no `[[DIR-NNN]]` links were dropped against the stage's baseline commit).
3. **Automatic Directive Linking on Newly Created Records**:
   - Whenever synchronization creates a new record (e.g., a new beat `BET-NNN`, scene `SCN-NNN`, world entity, or chapter draft), it must automatically link pre-existing `DIR-NNN` directives whose `Scope:` matches the new record or its referenced entities (`CHR`, `PLC`, `ARC`, `CHP`, etc.):
     ```bash
     uv run python scripts/specnovel.py directives link --apply
     ```
   - `specnovel.py accept --stage <stage>` also runs automatic directive linking on newly added records before committing.
4. **Automatic Directive Factoring (Single Source of Truth)**:
   - When an upstream change introduces a special instruction, rule, or stylistic constraint that needs to be applied across multiple downstream records during synchronization, factor it into a single `DIR-NNN` in `directives/` rather than duplicating prose instructions across records:
     ```bash
     uv run python scripts/specnovel.py directives factor --title "<Title>" --scope "<Scope>" --instruction "<Instruction>" --targets <ID1> <ID2> ...
     ```

---

## 2. Incremental Synchronization Workflow

### Step 1: Inspect Project Status & Verify Generation Gate
Run status and delta checks for the target stage:
```bash
uv run python scripts/specnovel.py status
uv run python scripts/specnovel.py delta --stage <stage>
```
- If `delta --stage <stage>` reports that `<stage>` has not been generated yet (`Novel-Sync: <stage>` baseline is `None`), stop and invoke `novel-generate` for `<stage>`.

### Step 2: Compute Downstream Impact
For stages with fine-grained dependency tracking (`narrative`, `structure`, `abridged`, `manuscript`, `publishable`):
```bash
uv run python scripts/specnovel.py impact --stage <stage>
```
This identifies:
- Modified upstream files since the target stage's last `Novel-Sync: <stage>` commit.
- Specific scenes (`SCN-NNN`), chapters (`CHP-NNN`), or illustrations (`ILL-NNN`) impacted by changes to `setup/`, `research/`, `world/`, `narrative/`, `structure/`, or `directives/`.

### Step 3: Incrementally Update Target Stage Records
Update **only** the affected records in `<stage>`:

- **Synchronizing `research` (Stage 2) from `setup`**:
  - Run `uv run python scripts/specnovel.py placeholders --create-rq` and add/update `RQ-NNN` items in `research/questions.md` for new themes or brief changes.
- **Synchronizing `world` (Stage 3) from `setup` / `research`**:
  - Answer newly added `RQ-NNN` questions with sourced `FCT-NNN` + `SRC-NNN` records, and update affected `CHR`, `PLC`, `ORG`, `OBJ`, `WLD`, `TML`, or `GLS` files while preserving `[[DIR-NNN]]` links.
- **Synchronizing `narrative` (Stage 4) from `setup` / `world`**:
  - Update affected story arcs (`ARC-NNN`), narrative beats (`BET-NNN`), and textual illustration specs (`ILL-NNN`).
  - Ensure every new or updated beat has `Place:`, `Time:`, `Arcs:`, and valid `Dependencies:` in the Beat DAG rooted at `Denouement: true`.
  - Run `uv run python scripts/specnovel.py dag`.
- **Synchronizing `structure` (Stage 5) from `narrative`**:
  - Update `structure/outline.md` (`VOL`, `ACT`, `CHP`, `SCN`) so newly added or re-ordered beats (`BET-NNN`) and illustrations (`ILL-NNN`) are serialized in valid topological order.
  - Run `uv run python scripts/specnovel.py dag`.
- **Synchronizing `abridged` (Stage 6) from `setup` / `world` / `narrative` / `structure` / `directives`**:
  - Re-synthesize only the impacted `SCN-NNN` sections inside `abridged/CHP-NNN.md`, honoring all linked `[[DIR-NNN]]` directives.
- **Synchronizing `manuscript` (Stage 7) from `abridged` / `setup` / `world` / `directives`**:
  - Re-render only the impacted scenes in `manuscript/<locale>/CHP-NNN.md` across all configured locales, honoring `setup/style.md` and all active `DIR-NNN` directives.
- **Synchronizing `publishable` (Stage 8) from `narrative` / `structure` / `manuscript` / `directives`**:
  - Re-render only impacted active illustrations in `publishable/graphics/ILL-NNN[.<locale>].png` and recompile deliverables in `publishable/<locale>/` via `uv run python scripts/specnovel.py compile`.

### Step 4: Auto-Link Directives, Validate, and Advance Stage Baseline
1. Auto-link pre-existing directives to any newly created records:
   ```bash
   uv run python scripts/specnovel.py directives link --apply
   ```
2. Run full project integrity and directive-preservation checks:
   ```bash
   uv run python scripts/specnovel.py check
   ```
3. Commit and advance the stage's synchronization baseline:
   ```bash
   uv run python scripts/specnovel.py accept --stage <stage> --model "<AI Model Name>" -m "Synchronize <stage> with upstream changes"
   ```
   *(When syncing rendered illustrations in `publishable`, include `--gfx ILL-NNN` to record per-asset sync baselines.)*
