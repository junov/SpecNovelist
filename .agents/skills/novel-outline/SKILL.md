---
name: novel-outline
description: >-
  Builds and revises the high-level outline of a SpecNovelist novel: the skeleton of the book in
  reading order (parts, chapters, scenes) with permanent IDs and [[ID]] cross-references to
  characters, places, plot elements, facts, world rules and timeline events. Use when the user
  wants to create the outline, restructure the plot, add/move/cut chapters or scenes, or check
  pacing and plot-thread coverage. Works in two passes (macro structure, then scene level),
  surfaces research gaps as RQ items and missing story-bible entries, and never writes prose.
---

# Novel-Outline

The outline is the novel's skeleton and the contract for every downstream layer: the abridged
draft must contain every outlined scene, in this order, and nothing that contradicts it.

* **Outline format**: [outline-format.md](references/outline-format.md)
* **KB format**: [kb-format.md](../novel-author/references/kb-format.md)
* **Helper**: `python <toolkit>/scripts/specnovel.py <command>`

## Preconditions
- `story/brief.md` is filled in and the KB is seeded (`novel-init`).
- High-priority `RQ` items are answered (`novel-research`), or the author explicitly accepts
  outlining with provisional assumptions (record each as an open `RQ`).

## Workflow

### 1. Load context
Read `story/synopsis.md`, `story/brief.md`, `story/style.md` (specifically `## Graphics Guidelines`), `kb/INDEX.md`
(run `specnovel.py index` first), all `PLT`, `CHR` (major), `TML`, `WLD`, and `GFX` entries, and the facts linked from them.

### 2. Pass 1: macro structure (approval gate)
Propose, in chat or as a draft in `outline/outline.md`:
- The structural model from the brief, with the main turning points mapped to chapters
  (inciting incident, first plot point, midpoint, crisis, climax, resolution - or the model's
  equivalents).
- Parts (optional) and chapters with a one-line purpose each, POV and approximate story date.
- A length budget: chapter targets that sum to the brief's `target_words`.
- Where each `PLT` thread starts, turns and resolves.
- **Serialization Strategy**: Identify parallel plot branches in the story DAG and propose how they
  should be interleaved to maximize dramatic tension, suspense, and thematic contrast in accordance
  with `story/style.md`.
- **Macro Visual Assets Plan**: In accordance with `story/style.md` > `## Graphics Guidelines`, determine
  macro graphics needs based on the configured `Intensity` and `Target Budget` (e.g. frontispiece / book cover,
  world/theater maps, or part opening plates).

Iterate with the author until the macro structure is approved. Allocate `PRT`/`CHP` IDs with
`next-id` only once the shape is stable, to avoid burning IDs.

### 3. Pass 2: scenes
For each chapter, write scenes per [outline-format.md](references/outline-format.md). Each scene
states prerequisites (`Prerequisites: [[...]]`), when, where, POV, cast, the plot elements it
advances, the facts and world rules it relies on, graphics (`Graphics: [[GFX-...]]` or `[GFX: ...]`),
goal/conflict/outcome, beats, must-keep dialogue (if any), the change it produces, target length,
and (for the resolving scene) `Denouement: true`.
Allocate `SCN` IDs with `next-id SCN`, saving between calls.

While outlining:
- **Deciding Graphics Placement & Visual Placeholders**:
  - `novel-outline` is responsible for evaluating where graphics should be used across the narrative.
  - Consult `story/style.md` > `## Graphics Guidelines` to audit scenes against visual triggers:
    - *Spatial & Geographic Transitions*: Enter a new city, archipelago, fortress, or tactical waterway where layout clarifies movement.
    - *Mechanical & Technical Complexity*: Physical apparatus, ship compartment cutaways, or machinery where prose explanation would stall pacing (the Friction Principle).
    - *Dramatic & Structural Pivots*: Major turning points or confrontation layouts.
    - *In-World Epistolary Artifacts*: Facsimiles of crucial letters, decoded telegrams, manifests, or clippings.
  - Enforce the style's negative rules (no decorative filler, no talking heads, no premature spoiler reveals).
  - Include asset references or functional placeholders:
    - If a KB asset exists, link it: `- **Graphics:** [[GFX-001]]`.
    - If an asset is needed but not yet cataloged, write a structured placeholder: `- **Graphics:** [GFX: <type> - <description>]` (e.g. `[GFX: Map - Harbor approach chart showing shoal hazards]`, `[GFX: Schematic - Wireless Marconi transmitter circuit]`, `[GFX: Document - Facsimile of unsigned letter with wax seal]`).
  - **Activating Graphics in the Story DAG**:
    Placing `[[GFX-xxx]]` or graphics placeholders in outline scenes explicitly attaches them to the **Story DAG**.
    This ensures that downstream `novel-sync` renders only active visual assets, skipping inactive KB entities
    to conserve AI tokens and enabling per-asset baseline drift tracking.
- **Causality & Multiple Valid Serializations**:
  The story causality DAG defines a *partial order*, meaning there is **more than one valid serialization order**
  for the outline. Any sequence where every scene is preceded in reading order by all of its prerequisites is
  causally valid.
  The specific sequence chosen is a critical artistic decision governed by **`story/style.md`** and desired
  **dramatic effects**:
  - *Suspense & Dramatic Irony*: Placing an antagonist's setup beat before the protagonist's response creates dread;
    reversing independent beats creates surprise or mystery.
  - *Cross-Cutting & Cliffhangers*: Interweaving scenes across parallel subplots creates momentum and sharp chapter-end hooks.
  - *Pacing Cadence*: Alternating high-stakes confrontations with quieter, reflective scenes to control the wave form of tension.
  - *Thematic Juxtaposition*: Placing two causally independent scenes side-by-side to contrast themes, social classes, or philosophies.
- **Root Denouement & Essentiality**: The novel's final denouement is the root of the story DAG. Mark the
  resolving scene with `- **Denouement:** true` (or specify it in `story/brief.md`). Every element in the
  story must have a directed causal path to the root denouement; inessential dead-ends are forbidden.
- **Missing story-bible items** (a new minor character, a room, an object): create the KB entry
  per novel-author conventions so every reference resolves.
- **Missing facts**: never invent them. Add an `RQ` item linked to the scene (`Needed for:`), use a
  clearly marked provisional assumption in the scene, and continue.
- **Chronology**: keep `When:` consistent with `TML` entries, travel times, character ages and
  established facts. Add story events to the timeline when they anchor later scenes.

### 4. Audit the outline
Whenever the outline is created, restructured, or updated, execute the automated DAG tests and check:
1. `python <toolkit>/scripts/specnovel.py dag`: Verifies acyclicity (it is indeed a DAG), reading
   order coherence (each element in the outline is preceded by all its prerequisites), and
   essentiality (every element has a causal path to the root denouement, taking authorized scene functions into account).
2. `python <toolkit>/scripts/specnovel.py audit`: Developmental editorial telemetry auditing:
   - Pacing waveform: scene-by-scene word count, average sentence length, paragraph cadence.
   - Dialogue balance: dialogue percentage and warnings for white-room or monologue extremes.
   - Character agency: POV and Cast distribution across scenes.
   - Chekhov's gun tracking: setup vs payoff scene distance (flags immediate payoffs or long dormant setups).
   - Epistemic matrix: secrets revealed vs who learns vs who is kept in the dark.
   - Pacing sag detection: sequences of 2+ long scenes with no major plot progression.
3. `python <toolkit>/scripts/specnovel.py check`: Comprehensive validation (all references resolve,
   no dangling links, facts are sourced, scenes nested in chapters, DAG checks pass, epistemic consistency verified, zero orphan plants).

### 5. Non-Linear Exploration & Scenarios
- Authors can explore alternate outlines and divergent story trajectories using folder-based scenarios:
  - `python scripts/specnovel.py scenario create <name> -m "description"`: Spawns an isolated scenario branch under `story/scenarios/<name>/`.
  - `python scripts/specnovel.py scenario list`: Lists active exploratory scenarios.
  - `python scripts/specnovel.py scenario diff <name>`: Compares the scenario outline against the main outline.
  - `python scripts/specnovel.py scenario activate <name>`: Swaps the scenario outline into `outline/outline.md` for testing/compilation while backing up main.
  - `python scripts/specnovel.py scenario merge <name>`: Promotes the scenario outline to the main outline.

### 6. Reverse-Scaffolding & Ingestion (Prose Harvesting)
- When an author has drafted raw prose or written unstructured text bursts first:
  - `python scripts/specnovel.py harvest <draft-file>`: Parses characters, places, dialogues, and scene beats.
  - `python scripts/specnovel.py harvest <draft-file> --apply`: Automatically scaffolds provisional KB entries in `kb/characters/` and `kb/places/`, appends the structured scene into `outline/outline.md`, and places the raw prose into `abridged/`.

### 7. Approval and baseline
Present the outline summary (chapter list with one-liners, thread coverage, open `RQ`s, length
budget, DAG verification status). On approval: `specnovel.py index`, then
`specnovel.py accept --stage outline -m "Outline: <summary>"` (or `--stage plan`). Recommend `novel-abridge` next.

## Revising an existing outline
- To see upstream story bible changes that need outlining, inspect `specnovel.py delta --stage bible`
  or `specnovel.py delta --stage brief`.
- **Move** a scene or chapter by moving its whole block; IDs stay the same. Never renumber.
  *Note*: Reordering scenes must not violate reading order coherence with respect to prerequisites!
- **Cut** a scene by deleting its block (the ID is retired); its derived text is flagged for
  removal by `specnovel.py impact`. Ensure downstream scenes' prerequisites are adjusted so no broken
  dependencies or disconnected paths to root are created.
- **Split** a scene: keep the ID for the part that retains the original purpose; allocate a new ID
  for the other.
- **Always re-test**: Run `specnovel.py dag` and `specnovel.py check` immediately following any edit.
- After revisions, show which derived scenes are affected: `specnovel.py impact --stage abridged`,
  and hand off to `novel-sync` once the plan is accepted.

## Rules
- The story is a Directed Acyclic Graph (DAG) rooted at the final denouement.
- Heading order **is** reading order; every element must be preceded by all its prerequisites.
- Every scene and plot element must have a causal path to the root denouement (no dead-ends).
- Never write prose in the outline; beats are terse statements of what happens.
- Never contradict a sourced fact without the author choosing a documented `Liberty:`.
- Always run `specnovel.py dag` and `specnovel.py check` whenever the outline is touched.
