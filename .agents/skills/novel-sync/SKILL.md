---
name: novel-sync
description: >-
  The incremental compilation and synchronization engine that translates changes in the plan
  (story/, kb/, outline/) into the derived layers (abridged/ and manuscript/). Use when the user has
  edited story specifications, updated knowledge base items, changed research facts, or altered the
  outline, and wants to update the novel drafts. Computes the impact delta against the git
  baselines, orchestrates abridged and manuscript updates, validates structural integrity and word
  count budgets, and commits synchronized baselines with structured Novel-Sync git trailers.
---

# Novel-Sync

`novel-sync` is the core execution engine of the SpecNovelist **Spec-as-Source** methodology.

In SpecNovelist:
- **`story/`**, **`kb/`**, and **`outline/`** represent the **specification (Source of Truth)**.
- **`abridged/`** and **`manuscript/`** represent the **derived artifacts (Generated/Compiled Text)**.

When you modify a character's secret, relocate a scene, revise a historical fact, or adjust the
outline, `novel-sync` calculates the exact impact radius, reconciles `abridged/`, renders
`manuscript/`, verifies continuity and integrity, and advances the project baselines.

* **Detailed synchronization protocol**: [sync-protocol.md](references/sync-protocol.md)
* **Helper script**: `python <toolkit>/scripts/specnovel.py <command>`

---

## The Synchronization Lifecycle

```mermaid
flowchart TD
    A["Author edits story/, kb/, or outline/"] --> B["1. Compute Impact (specnovel.py impact)"]
    B --> C{"Check Problems?"}
    C -- "Errors in Plan" --> D["Fix errors (novel-author / outline)"]
    C -- "Clean Delta" --> E["2. Update Abridged Draft (abridged/)"]
    E --> F["3. Author Review: Abridged Layer"]
    F -- "Approved" --> G["4. Advance Abridged Baseline (specnovel.py accept --stage abridged)"]
    G --> H["5. Render Manuscript (manuscript/)"]
    H --> I["6. Run Integrity Check (specnovel.py check)"]
    I -- "Fails" --> J["Fix prose or references"]
    J --> I
    I -- "Passes" --> K["7. Author Review: Manuscript Layer"]
    K -- "Approved" --> L["8. Advance Manuscript Baseline (specnovel.py accept --stage manuscript)"]
    L --> M["Git Commit with Novel-Sync trailers"]
```

---

## Workflow Steps

### 1. Inspect Delta and Impact
Always start by checking pending changes and impact against the last sync baselines:
```bash
python scripts/specnovel.py status
python scripts/specnovel.py impact --stage abridged
python scripts/specnovel.py impact --stage manuscript
```
- If duplicate IDs, dangling references, or unnested scenes exist, resolve them before proceeding.
- If code drift exists in `abridged/` or `manuscript/` from manual edits outside a sync, review those
  changes so intentional modifications are incorporated or preserved.

### 2. Formulate the Synchronization Plan
Present a clear, step-by-step plan to the author:
1. **Upstream changes**: List what changed in `story/`, `kb/`, or `outline/`.
2. **Impacted scenes in `abridged/`**: Which scenes must be newly created, re-abridged, or deleted.
3. **Impacted scenes in `manuscript/`**: Which scenes must be newly rendered or updated.
4. **Global notes**: Any cross-cutting changes (e.g. style guide revisions) that require global attention.

### 3. Synchronize the Abridged Layer (`abridged/`)
For each scene flagged under `impact --stage abridged`:
- Use the `novel-abridge` skill conventions.
- Update or draft the scene under `abridged/CHP-xxx.md`.
- Ensure all plot beats and key dialogue from the revised outline are present.
- If an outline scene was removed, prune it from `abridged/`.

### 4. Author Review Gate: Abridged Layer
Present a concise summary of the abridged changes to the author:
- Highlight the updated plot turns, character actions, and dialogue.
- Ask for confirmation to proceed.
- If the author provides feedback requiring changes to plot or character motivation, hand off to
  `novel-author` or `novel-outline` to adjust the spec first.
- If approved, commit the abridged baseline:
  ```bash
  python scripts/specnovel.py accept --stage abridged -m "Sync abridged: <summary>"
  ```

### 5. Synchronize the Manuscript Layer (`manuscript/`)
For each scene flagged under `impact --stage manuscript`:
- Use the `novel-write` skill conventions.
- Read the updated abridged scene, `story/style.md`, and referenced `kb/` entries (`PLC`, `FCT`, `CHR`, `WLD`).
- Render the full literary prose under `manuscript/CHP-xxx.md`.
- Match target word count budgets (`specnovel.py stats`).
- If an outline scene was removed, prune it from `manuscript/`.

### 6. Automated Validation and Integrity Check
Run:
```bash
python scripts/specnovel.py check
python scripts/specnovel.py stats
```
Verify that:
- Every scene in the outline exists in both `abridged/` and `manuscript/` in the correct reading order.
- No dangling references or orphan scenes exist.
- No raw `[[ID]]` tags appear in the visible manuscript prose.
- Fact citations and source records remain valid.

### 7. Author Review Gate: Manuscript Layer
Present the rendered manuscript scenes, word count pacing, and diffs to the author.
Ask the author to review and approve the text.
- If the author requests minor prose refinements, edit `manuscript/` to polish voice and rhythm.
- If the author requests changes to plot, character actions, or factual events, guide the author
  to adjust the spec first, then re-sync.

### 8. Accept the Synchronization
Once the author approves and all integrity checks pass:
```bash
python scripts/specnovel.py accept --stage manuscript -m "Sync manuscript: <summary>"
```
Or, if synchronizing both stages simultaneously:
```bash
python scripts/specnovel.py accept --stage all -m "Sync full novel: <summary>"
```
This stages `story/`, `kb/`, `outline/`, `abridged/`, `manuscript/` and records a Git commit with
structured `Novel-Sync:` trailers:
```git
novel-sync(abridged, manuscript): Update collision aftermath

Novel-Sync: abridged, manuscript
Novel-Modified: SCN-014, CHR-003
Novel-Abridged-Updated: SCN-014
Novel-Manuscript-Updated: SCN-014
```
This commit becomes the new baseline for future deltas.

---

## Rules

1. **Spec is Primary**: Never edit `abridged/` or `manuscript/` to alter plot events, character
   fates, or historical facts without updating `story/`, `kb/`, or `outline/` first.
2. **Sequential Compilation**: Always update and review `abridged/` before rendering `manuscript/`.
   Never skip the abridged layer.
3. **No Phantom Scenes**: Only scenes defined in `outline/` may exist in `abridged/` and `manuscript/`.
4. **Git Baseline Integrity**: Use `specnovel.py accept` to commit baselines so that future changes
   are accurately tracked and diffed.
