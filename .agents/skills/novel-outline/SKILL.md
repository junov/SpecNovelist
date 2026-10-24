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

Iterate with the author until the macro structure is approved. Allocate `PRT`/`CHP` IDs with
`next-id` only once the shape is stable, to avoid burning IDs.

### 3. Pass 2: scenes
For each chapter, write scenes per [outline-format.md](references/outline-format.md). Each scene
states when, where, POV, cast, the plot elements it advances, the facts and world rules it relies
on, goal/conflict/outcome, beats, must-keep dialogue (if any), the change it produces, and a
target length. Allocate `SCN` IDs with `next-id SCN`, saving between calls.

While outlining:
- **Missing story-bible items** (a new minor character, a room, an object): create the KB entry
  per novel-author conventions so every reference resolves.
- **Missing facts**: never invent them. Add an `RQ` item linked to the scene (`Needed for:`), use a
  clearly marked provisional assumption in the scene, and continue.
- **Chronology**: keep `When:` consistent with `TML` entries, travel times, character ages and
  established facts. Add story events to the timeline when they anchor later scenes.

### 4. Audit the outline
Run `specnovel.py check` (all references resolve; scenes are nested in chapters), then review:
- Every `PLT` element is set up, developed and paid off (`specnovel.py trace PLT-xxx` lists its
  scenes in reading order); every major character's arc has visible steps.
- Every scene changes something; flag scenes with no change or no conflict.
- POV rules from `style.md`/`brief.md` are respected (e.g. one POV per scene).
- Pacing: target lengths sum to the overall target (`specnovel.py stats`); turning points land
  near their intended proportions.
- Research-dependent scenes cite the facts they rely on.

### 5. Approval and baseline
Present the outline summary (chapter list with one-liners, thread coverage, open `RQ`s, length
budget). On approval: `specnovel.py index`, then
`specnovel.py accept --stage plan -m "Outline: <summary>"`. Recommend `novel-abridge` next.

## Revising an existing outline
- **Move** a scene or chapter by moving its whole block; IDs stay the same. Never renumber.
- **Cut** a scene by deleting its block (the ID is retired); its derived text is flagged for
  removal by `specnovel.py impact`.
- **Split** a scene: keep the ID for the part that retains the original purpose; allocate a new ID
  for the other.
- After revisions, show which derived scenes are affected: `specnovel.py impact --stage abridged`,
  and hand off to `novel-sync` once the plan is accepted.

## Rules
- Never write prose in the outline; beats are terse statements of what happens.
- Never contradict a sourced fact without the author choosing a documented `Liberty:`.
- Heading order **is** reading order; IDs never encode position.
