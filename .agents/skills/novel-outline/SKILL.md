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
Read `story/synopsis.md`, `story/brief.md`, `kb/INDEX.md` (run `specnovel.py index` first), all
`PLT`, `CHR` (major), `TML` and `WLD` entries, and the facts linked from them.

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

Iterate with the author until the macro structure is approved. Allocate `PRT`/`CHP` IDs with
`next-id` only once the shape is stable, to avoid burning IDs.

### 3. Pass 2: scenes
For each chapter, write scenes per [outline-format.md](references/outline-format.md). Each scene
states prerequisites (`Prerequisites: [[...]]`), when, where, POV, cast, the plot elements it
advances, the facts and world rules it relies on, goal/conflict/outcome, beats, must-keep dialogue
(if any), the change it produces, target length, and (for the resolving scene) `Denouement: true`.
Allocate `SCN` IDs with `next-id SCN`, saving between calls.

While outlining:
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
   essentiality (every element has a causal path to the root denouement).
2. `python <toolkit>/scripts/specnovel.py check`: Comprehensive validation (all references resolve,
   no dangling links, facts are sourced, scenes nested in chapters, DAG checks pass).

Then review:
- Every `PLT` element is set up, developed and paid off (`specnovel.py trace PLT-xxx` lists its
  scenes in reading order); every major character's arc has visible steps.
- Every scene changes something; flag scenes with no change or no conflict.
- POV rules from `style.md`/`brief.md` are respected (e.g. one POV per scene).
- Pacing: target lengths sum to the overall target (`specnovel.py stats`); turning points land
  near their intended proportions.
- Research-dependent scenes cite the facts they rely on.

### 5. Approval and baseline
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
