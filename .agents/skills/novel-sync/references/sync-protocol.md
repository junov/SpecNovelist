# Novel-Sync Protocol

This document defines the strict execution protocol for the `novel-sync` agent skill.
When the author modifies the plan (`story/`, `kb/`, `outline/`) and asks to compile, sync, or build
the novel, follow these stages sequentially.

---

## Detailed Step-by-Step Execution Guide

### 1. Delta and Drift Detection
Run:
```bash
python scripts/specnovel.py delta --stage plan
python scripts/specnovel.py status
```
Inspect the output:
- **Plan baseline**: Note the last accepted `plan` commit.
- **Modifications**: Check which `CHR`, `PLC`, `FCT`, `WLD`, `PLT`, or `SCN` items changed.
- **Drift check**: Check if any uncommitted or untracked changes exist in `abridged/` or `manuscript/`
  made outside of a sync. If manual edits occurred, ask the author whether those changes were intentional
  and should be backported into the outline/KB or overwritten by the sync.

### 2. Impact Calculation
Run:
```bash
python scripts/specnovel.py impact --stage abridged
python scripts/specnovel.py impact --stage manuscript
```
Analyze the dependency graph:
- **Direct Scene Edits**: If `SCN-014` itself changed in `outline/`, it must be re-synced in both layers.
- **Relocated Scenes**: If a scene moved to a new chapter, it must be relocated in the chapter files.
- **Upstream KB Ripple**: If `FCT-030` changed, every scene that references `[[FCT-030]]` directly
  or via its chapter is flagged.
- **Style Revisions**: If `story/style.md` changed, global notes are issued; all rendered scenes
  require stylistic review.

### 3. Abridged Layer Synthesis
Before touching final prose:
1. Open the chapter file in `abridged/CHP-xxx.md`.
2. For each impacted scene:
   - Rewrite or adjust the abridged scene to incorporate the updated beats, key dialogue, or facts.
   - Maintain the lean dramatic architecture (100% plot & key dialogue, minimal description).
3. If outline scenes were removed, delete them from the abridged file.
4. Verify the chapter:
   - Check that scene order matches the outline exactly.
   - Ensure scene headings use the exact `## SCN-xxx: Title` format.

### 4. Abridged Review Gate
Present the abridged diff to the author:
```bash
git diff abridged/
```
Highlight:
- How the revised beats, dialogue, or factual corrections were incorporated.
- Ask the author: *"Here is the updated abridged draft for the affected scenes. Do the events and dialogue work as intended?"*
- Wait for author confirmation.
- Once approved, record the abridged baseline:
  ```bash
  python scripts/specnovel.py accept --stage abridged -m "<Brief description of changes>"
  ```

### 5. Manuscript Layer Synthesis
Once the abridged draft is approved and baselined:
1. Open the chapter file in `manuscript/CHP-xxx.md`.
2. For each impacted scene:
   - Read the approved text in `abridged/CHP-xxx.md`.
   - Read `story/style.md` and the referenced `kb/` entries (`PLC` sensory palette, `CHR` mannerisms,
     `FCT` authentic details).
   - Render the scene in full literary prose.
   - Strip all raw `[[ID]]` tags from visible text.
   - Check word count against the outline's `Target words:` budget.
3. If outline scenes were removed, delete them from the manuscript file.

### 6. Validation and Check
Run:
```bash
python scripts/specnovel.py check
python scripts/specnovel.py stats
```
This verifies:
- No duplicate IDs.
- All scenes in the outline exist in `abridged/` and `manuscript/`.
- Scenes appear in strict outline order.
- No dangling references or orphan scenes exist.
- No raw `[[ID]]` markup is left in manuscript prose.
- Word count totals match overall target pacing.

### 7. Manuscript Review Gate
Present a concise summary to the author:
- Show excerpts of the newly rendered or updated prose.
- Provide a summary of words added/changed and chapter word count totals.
- Ask the author to review the prose for voice, tone, and character fidelity.
- If the author provides feedback:
  - If feedback relates purely to prose polish (sentence rhythm, word choice), edit `manuscript/` directly.
  - If feedback changes plot events, character decisions, or historical facts, hand off to
    `novel-author` / `novel-outline` to update the spec first, then re-sync.

### 8. Advance the Baseline
Once all checks pass and the author approves:
```bash
python scripts/specnovel.py accept --stage manuscript -m "<Brief description of prose changes>"
```
Or to advance all stages:
```bash
python scripts/specnovel.py accept --stage all -m "<Brief description of changes>"
```
This commits the synchronized state with `Novel-Sync:` trailers, establishing the clean new baseline.
