---
name: novel-generate
description: Category 1 (Generation) skill for SpecNovelist. Generates initial data for any of the 9 project stages (initial, setup, research, world, narrative, structure, abridged, manuscript, publishable) based on data from earlier stages and guided user interview questions. Automatically uses directives (DIR-NNN in directives/) as a DRY factoring single source of truth for instructions applied across multiple records, links relevant pre-existing directives to newly created records, and records the initial stage baseline via specnovel.py accept --stage <stage>.
---

# `novel-generate` — Stage Generation & Factoring Engine

This skill implements **Category 1: Generation** in the SpecNovelist 9-stage pipeline. It generates initial data for a target stage based on upstream stages and targeted author interview questions, factors recurring special instructions into cross-stage directives (`directives/DIR-NNN.md`), and establishes the stage's initial baseline commit so downstream synchronization (`novel-sync`) is unlocked.

---

## 1. The 9-Stage Architecture

| Stage # | Stage Name (`--stage`) | Directory | Entities & Artifacts Generated | Upstream Prerequisites |
|---|---|---|---|---|
| **1** | `initial` | `initial/` | `synopsis.md`, `config.md` | Seed idea / basic project config |
| **2** | `setup` | `setup/` | `brief.md`, `themes.md` (`THM-NNN`), `style.md` | `initial` |
| **3** | `research` | `research/` | `questions.md` (`RQ-NNN`) | `initial`, `setup` |
| **4** | `world` | `world/` | `facts/` (`FCT-NNN`), `sources/` (`SRC-NNN`), `characters/` (`CHR-NNN`), `places/` (`PLC-NNN`), `organizations/` (`ORG-NNN`), `objects/` (`OBJ-NNN`), `rules/` (`WLD-NNN`), `timeline/` (`TML-NNN`), `glossary/` (`GLS-NNN`) | `initial`, `setup`, `research` |
| **5** | `narrative` | `narrative/` | `arcs.md` (`ARC-NNN`), `beats.md` (`BET-NNN`) and `illustrations.md` (`ILL-NNN` textual specs) forming a unified Narrative DAG rooted at `Denouement: true` | `initial`, `setup`, `world` |
| **6** | `structure` | `structure/` | `outline.md` (`VOL-NNN`, `ACT-NNN`, `CHP-NNN`, `SCN-NNN` sequencing `BET-NNN` and `ILL-NNN`), `front-matter/`, `back-matter/acknowledgements.md` | `initial`, `setup`, `world`, `narrative` |
| **7** | `abridged` | `abridged/` | `CHP-NNN.md` (condensed chapter drafts with all beats, causal turns, and essential dialogue) | `initial`, `setup`, `world`, `narrative`, `structure` |
| **8** | `manuscript` | `manuscript/` | `<locale>/CHP-NNN.md` (full literary prose per configured locale) | `initial`, `setup`, `world`, `narrative`, `structure`, `abridged` |
| **9** | `publishable` | `publishable/` | `graphics/ILL-NNN[.<locale>].png` (rendered graphical assets) and `<locale>/manuscript.{epub,pdf,docx,md}` | All earlier stages (`1..8`) |

---

## 2. Core Generation Rules

1. **Sequential Upstream Foundation**:
   Always inspect `uv run python scripts/specnovel.py status` before generating a stage. Ensure upstream stages exist and pass validation (`uv run python scripts/specnovel.py check`). If the project is brand-new, initialize the folder skeleton first:
   ```bash
   uv run python scripts/specnovel.py init . --title "<Title>"
   ```
2. **Guided Author Interviews with Explicit Decline Paths**:
   Before generating a stage (especially `setup`, `research`, `world`, `narrative`, and `structure`), conduct a focused interview calibrated to the author's experience level (`novice`, `intermediate`, `experienced`).
   - **Mandatory Decline Path**: Every interview question must offer an explicit option allowing the author to decline to answer or delegate the creative decision to the agent (e.g., *"Delegate to agent / Decide for me based on the synopsis and themes"*).
3. **Permanent IDs Only via CLI**:
   Never invent entity IDs manually. Always allocate the next permanent ID using:
   ```bash
   uv run python scripts/specnovel.py next-id <PREFIX>
   ```
   Supported prefixes: `THM`, `RQ`, `FCT`, `SRC`, `CHR`, `PLC`, `ORG`, `OBJ`, `WLD`, `TML`, `GLS`, `ARC`, `BET`, `ILL`, `VOL`, `ACT`, `CHP`, `SCN`, `DIR`.
4. **Automatic Directive Factoring (Single Source of Truth)**:
   Generation skills must **automatically make use of directives (`DIR-NNN` in `directives/`) as a form of DRY factoring** whenever a special instruction, recurring constraint, voice/register rule, dialect convention, sensory motif, or illustration rule applies across multiple records (e.g., multiple beats, scenes, chapters, characters, or illustrations).
   - Instead of duplicating the instruction text across multiple records, factor it into a single `DIR-NNN` record and link `[[DIR-NNN]]` to every target entity using:
     ```bash
     uv run python scripts/specnovel.py directives factor --title "<Short Title>" --scope "<Scope/Tags>" --instruction "<Canonical Instruction>" --targets <ID1> <ID2> ...
     ```
   - Whenever new records are created in any stage, automatically link pre-existing relevant directives:
     ```bash
     uv run python scripts/specnovel.py directives link --apply
     ```
5. **Unlock Downstream Synchronization via `accept`**:
   Synchronization (`novel-sync`) is strictly blocked on any stage until initial generation has been completed and accepted at least once. At the end of generating a stage, validate and commit the stage baseline:
   ```bash
   uv run python scripts/specnovel.py check
   uv run python scripts/specnovel.py accept --stage <stage> --model "<AI Model Name>" -m "Generate initial <stage> stage"
   ```

---

## 3. Stage-by-Stage Generation Procedures

See [`references/stage-generation-guide.md`](references/stage-generation-guide.md) for detailed schemas and templates for every stage.

### Stage 1: `initial` (`initial/`)
1. Read or draft `initial/synopsis.md` based on the author's seed idea.
2. Interview the author (with explicit decline/delegate options) on Author Identity, target locales (and primary locale), and compilation options (`initial/config.md`).
3. Validate and run `accept --stage initial` when instructed.

### Stage 2: `setup` (`setup/`)
1. Read `initial/synopsis.md` and `initial/config.md`.
2. Interview the author (with explicit decline/delegate options) on:
   - Genre, audience, length budget, POV, setting eras, and research rigor (`setup/brief.md`).
   - Core themes (`THM-NNN` in `setup/themes.md`).
   - Prose voice, cadence, dialogue conventions, anti-patterns, illustration guidelines (`## Graphics Guidelines`), and book typography (`## Publication & Book Design Guidelines`) (`setup/style.md`).
3. Factor any recurring multi-entity constraints discovered during the interview into `directives/DIR-NNN.md`.
4. Run `uv run python scripts/specnovel.py placeholders --create-rq` if placeholders exist, validate, and run `accept --stage setup` when instructed.

### Stage 3: `research` (`research/`)
1. Scan `initial/` and `setup/` for `[...]` or `<...>` placeholders:
   ```bash
   uv run python scripts/specnovel.py placeholders --create-rq
   ```
2. Analyze `initial/synopsis.md`, `setup/brief.md`, and `setup/themes.md` to identify historical, scientific, technical, geographical, legal, or cultural world-building questions.
3. Interview the author on any domain-specific priorities (offering a decline/delegate option).
4. Record structured `RQ-NNN` entries in `research/questions.md` with priority, domain, and links to upstream elements.
5. Run `accept --stage research` when instructed.

### Stage 4: `world` (`world/`)
1. **Resolve Research Questions into Sourced Facts**:
   - For each open `RQ-NNN` in `research/questions.md`, perform verifiable research (or consult authoritative sources).
   - Create bibliographic source records (`SRC-NNN` in `world/sources/SRC-NNN.md`) and sourced facts (`FCT-NNN` in `world/facts/FCT-NNN.md`) citing `[[SRC-NNN]]`. Never create an `FCT` without at least one verified `SRC`.
   - Mark resolved questions `- **Status:** resolved ([[FCT-NNN]])` in `research/questions.md`.
2. **Generate World Entities**:
   - Interview the author on cast, key locations, factions, objects, and world rules (offering decline/delegate options).
   - Create cataloged files in `world/characters/` (`CHR-NNN`), `world/places/` (`PLC-NNN`), `world/organizations/` (`ORG-NNN`), `world/objects/` (`OBJ-NNN`), `world/rules/` (`WLD-NNN`), `world/timeline/` (`TML-NNN`), and `world/glossary/` (`GLS-NNN`).
3. **Factor Shared World/Character Instructions into Directives**:
   - If a group of characters, places, or factions shares a specific rendering instruction (e.g., speech register for a faction, architectural atmosphere across a region), factor it via `specnovel.py directives factor` and link `[[DIR-NNN]]`.
4. Run `specnovel.py directives link --apply`, `specnovel.py check`, and `accept --stage world` when instructed.

### Stage 5: `narrative` (`narrative/`)
1. **Story Arcs (`narrative/arcs.md`)**:
   - Define the main plot arc and subplots (`ARC-NNN`), linking relevant `THM-NNN` and `CHR-NNN`.
2. **Narrative Beats (`narrative/beats.md`)**:
   - Decompose the narrative into causal beats (`BET-NNN`).
   - **Mandatory Beat Invariants**:
     - Every beat **must** declare `- **Place:** [[PLC-NNN]]`.
     - Every beat **must** declare `- **Time:** <timestamp or relative period>`.
     - Every beat **must** be associated with at least one story arc: `- **Arcs:** [[ARC-NNN]]`.
     - Every beat **must** list its causal/dramatic prerequisites in `- **Dependencies:** [[BET-NNN]], [[ILL-NNN]], ...` (or `none` for initial beats).
     - The root of the Narrative DAG **must** be the final denouement beat marked with `- **Denouement:** true`. Every beat in `narrative/beats.md` must have a directed path leading to the denouement beat (or declare an authorized artistic `- **Function:**`).
   - Track epistemic flow (`Reveals:`, `Learns:`, `Hidden From:`) and Chekhov setups/payoffs (`Plants:`, `Pays off:`) on beats or scenes.
3. **Textual Illustration Specs (`narrative/illustrations.md`)**:
   - Guided by `setup/style.md` (`## Graphics Guidelines`), define textual illustration descriptions (`ILL-NNN` in `narrative/illustrations.md`).
   - **Narrative DAG & Arc Rules for Illustrations**:
     - Illustration nodes are part of the Narrative DAG just like beats. Relations between beats and illustrations are governed by `- **Dependencies:** [[BET-NNN]], [[ILL-NNN]]` (never use an `Associated Beats` field).
     - Like beats, every illustration **must** be associated with at least one story arc (`- **Arcs:** [[ARC-NNN]]`), **except** for illustrations used for covers (`Type: cover`) or front/back matter (`Type: front-matter` | `back-matter`).
   - At Stage 5, illustrations are **purely textual specifications**—do **not** generate image files yet.
4. **Factor Shared Narrative Instructions**:
   - Factor recurring dramatic or visual instructions across multiple beats/illustrations into `DIR-NNN` via `specnovel.py directives factor`.
5. Validate the Narrative DAG via `uv run python scripts/specnovel.py dag` and `check`, then run `accept --stage narrative` when instructed.

### Stage 6: `structure` (`structure/`)
1. **Physical Serialization (`structure/outline.md`)**:
   - Organize the novel's physical reading order into Volumes (`VOL-NNN`), Acts (`ACT-NNN`), Chapters (`CHP-NNN`), and Scenes (`SCN-NNN`).
   - Each Scene (`SCN-NNN`) sequences an ordered list of Beats (`[[BET-NNN]]`) and Illustrations (`[[ILL-NNN]]`), plus target word counts, POV (`[[CHR-NNN]]`), Place (`[[PLC-NNN]]`), Time, Goal/Conflict/Outcome, and Key Dialogue.
   - **Topological Serialization Rule**: Every node (`BET-NNN` or `ILL-NNN`) that depends on an earlier node in the Narrative DAG **must** appear after its dependencies in the physical scene reading order of `structure/outline.md`.
2. **Front and Back Matter (`structure/front-matter/`, `structure/back-matter/`)**:
   - Ensure `structure/back-matter/acknowledgements.md` exists and lists every AI model used in the project.
3. Validate topological coherence via `uv run python scripts/specnovel.py dag` and `check`, factor any chapter/scene-spanning directives, and run `accept --stage structure` when instructed.

### Stage 7: `abridged` (`abridged/`)
1. For each chapter `CHP-NNN` in `structure/outline.md`, synthesize `abridged/CHP-NNN.md` with `### SCN-NNN: <Title>` sections.
2. Include **all narrative beats** (`[[BET-NNN]]`), causal turns, and **all essential dialogues**, plus embedded Markdown links for active illustrations (`![Caption](../publishable/graphics/ILL-NNN.png)`).
3. Strictly obey all `[[DIR-NNN]]` directives attached to the chapter, its scenes, its beats, or its participating world entities.
4. Run `specnovel.py check` and `accept --stage abridged` when instructed.

### Stage 8: `manuscript` (`manuscript/`)
1. For each target locale configured in `initial/config.md`, render polished literary prose in `manuscript/<locale>/CHP-NNN.md` from `abridged/CHP-NNN.md`, `setup/style.md`, `world/`, and all linked `directives/DIR-NNN.md`.
2. Maintain 100% causal and dialogue fidelity to `abridged/` while expanding sensory texture, interiority, and cadence according to `setup/style.md` (including `# Locale: <locale>` sections).
3. Embed localized illustration links (`../../publishable/graphics/ILL-NNN.<locale>.png` or fallback `../../publishable/graphics/ILL-NNN.png`) and ensure zero raw `[[ID]]` metadata leaks into manuscript prose.
4. Run `specnovel.py check` and `accept --stage manuscript` when instructed.

### Stage 9: `publishable` (`publishable/`)
1. **Render Graphical Assets (`publishable/graphics/`)**:
   - For every active `ILL-NNN` placed in `structure/outline.md` (plus cover/matter illustrations), render the actual graphical asset in `publishable/graphics/ILL-NNN.png` (and localized variants `ILL-NNN.<locale>.png` when text labels exist) adhering to `narrative/illustrations.md`, `setup/style.md` (`## Graphics Guidelines`), and any linked `[[DIR-NNN]]`.
2. **Compile Deliverable Books (`publishable/<locale>/`)**:
   - Compile clean Markdown, EPUB, PDF, or DOCX deliverables into `publishable/<locale>/` via:
     ```bash
     uv run python scripts/specnovel.py compile --format all --locale <locale>
     ```
3. Run `specnovel.py check` and `accept --stage publishable` when instructed.
