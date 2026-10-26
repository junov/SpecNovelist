---
name: novel-feedback
description: Category 3 (Feedback) skill for SpecNovelist. Processes freeform author or editor feedback to edit data at the appropriate project stage (initial, setup, research, world, narrative, structure, abridged, manuscript, publishable) and creates or updates persistent directives (DIR-NNN in directives/) so that user feedback is locked in and automatically preserved across future synchronization runs.
---

# `novel-feedback` — Freeform Feedback Triage & Directive Lock-In

This skill implements **Category 3: Feedback** in the SpecNovelist architecture. Whenever the user provides freeform editorial, structural, world-building, stylistic, or prose-level feedback, `novel-feedback` routes the edits to the authoritative upstream stage(s) and locks in recurring or situational instructions as cataloged directives (`directives/DIR-NNN.md`) so they are never lost when downstream stages are regenerated during synchronization.

---

## 1. The Role of Directives (`directives/DIR-NNN.md`)

Directives are instructions that do not fall cleanly into a single static data field or that must govern how one or more records are generated and synchronized across stages:
1. **Locking In User Feedback**:
   - If the author gives feedback on how a scene, beat, character interaction, illustration, or chapter should feel, read, or behave (e.g., *"Keep the dialogue in SCN-002 clipped and bureaucratic; neither character should use contractions"*), editing `manuscript/` or `abridged/` alone would be overwritten the next time `novel-sync` regenerates that scene.
   - Instead, `novel-feedback` creates a permanent directive `directives/DIR-NNN.md`, sets its `Scope:` to the target record(s) (e.g., `[[SCN-002]]`), links `- **Directives:** [[DIR-NNN]]` on the target record(s), and applies the revision.
2. **DRY Factoring (Single Source of Truth)**:
   - When feedback applies to multiple records (e.g., all scenes in `CHP-001`, all beats on `ARC-002`, or every appearance of `CHR-003`), factor the instruction into a single `DIR-NNN` and link `[[DIR-NNN]]` to all matching records via:
     ```bash
     uv run python scripts/specnovel.py directives factor --title "<Short Title>" --scope "<Scope/Tags>" --instruction "<Canonical Instruction>" --targets <ID1> <ID2> ...
     ```

---

## 2. Feedback Routing Workflow

### Step 1: Classify the Feedback & Identify the Authoritative Stage
Analyze the user's freeform feedback and map each part to the earliest stage where that truth belongs:

| Feedback Type | Target Stage & Files | Action |
|---|---|---|
| **Seed synopsis, author identity, target locales, compilation toggles** | **Stage 1 (`initial/`)**: `synopsis.md`, `config.md` | Edit `initial/synopsis.md` or `initial/config.md`. |
| **Creative brief, themes, global prose voice/cadence, global anti-patterns, graphics/book design rules** | **Stage 2 (`setup/`)**: `brief.md`, `themes.md` (`THM`), `style.md` | Edit the corresponding file in `setup/`. |
| **New world-building unknowns or factual gaps** | **Stage 3 (`research/`)**: `questions.md` (`RQ`) | Allocate `RQ-NNN` (or run `placeholders --create-rq`) in `research/questions.md`. |
| **Factual claims, character traits, locations, factions, objects, world rules, glossary** | **Stage 4 (`world/`)**: `facts/` (`FCT` + `SRC`), `characters/` (`CHR`), `places/` (`PLC`), `organizations/` (`ORG`), `objects/` (`OBJ`), `rules/` (`WLD`), `timeline/` (`TML`), `glossary/` (`GLS`) | Edit or create the cataloged `world/` record. Never add real-world claims without a verified `SRC-NNN`. |
| **Story arcs, causal plot events, beat/illustration dependencies, denouement, illustration specs** | **Stage 5 (`narrative/`)**: `arcs.md` (`ARC`), `beats.md` (`BET`), `illustrations.md` (`ILL`) | Edit or add `ARC`, `BET`, or `ILL` records. Verify Narrative DAG invariants (`Place:`, `Time:`, `Arcs:`, `Dependencies:`, `Denouement: true`) via `specnovel.py dag`. |
| **Chapter/scene division, reading order, scene beat/illustration sequence, word budgets, front/back matter** | **Stage 6 (`structure/`)**: `outline.md` (`VOL`, `ACT`, `CHP`, `SCN`), `front-matter/`, `back-matter/` | Edit `structure/outline.md` and verify topological serialization via `specnovel.py dag`. |
| **Unstructured creative prose bursts written directly by the author** | **Stage 4–7 (`world/`, `narrative/`, `structure/`, `abridged/`)** | Run `uv run python scripts/specnovel.py harvest <draft-file> --apply` to reverse-engineer new characters, places, dialogue, beats, and scenes into upstream specs. |
| **Situational, local, cross-cutting, or special instructions that must persist across regenerations** | **Directives (`directives/DIR-NNN.md`) + Target Stage Records** | Create or factor `DIR-NNN` via `specnovel.py directives factor` and link `[[DIR-NNN]]` to all target records. |

### Step 2: Create & Link Directives (`DIR-NNN`)
Whenever feedback includes instructions that do not fit into standard structural metadata—or that govern how downstream stages (`abridged`, `manuscript`, `publishable`) must render specific records:
1. Factor and link the directive in one step:
   ```bash
   uv run python scripts/specnovel.py directives factor \
     --title "<Concise Directive Title>" \
     --scope "<Target IDs, e.g. [[SCN-001]], [[CHR-001]]>" \
     --locale "<all or specific locale e.g. fr-FR>" \
     --instruction "<Detailed editorial/generation instruction>" \
     --targets <ID1> <ID2> ...
   ```
2. Or allocate an ID manually with `uv run python scripts/specnovel.py next-id DIR`, write `directives/DIR-NNN.md`, and run:
   ```bash
   uv run python scripts/specnovel.py directives link --apply
   ```

### Step 3: Validate & Propagate Downstream
1. Run integrity and DAG checks on the modified stage(s):
   ```bash
   uv run python scripts/specnovel.py check
   uv run python scripts/specnovel.py dag
   ```
2. Inspect downstream impact across generated stages:
   ```bash
   uv run python scripts/specnovel.py status
   ```
3. Hand off to **`novel-sync`** (or synchronize the impacted downstream stages directly if requested by the user) so that `abridged/`, `manuscript/`, and `publishable/` reflect the updated upstream specs and newly linked `[[DIR-NNN]]` directives.
