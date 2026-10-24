---
name: novel-author
description: >-
  Creates, edits and reviews knowledge-base entries in a SpecNovelist novel project: characters
  (CHR), places (PLC), organizations (ORG), objects (OBJ), plot elements (PLT), themes (THM),
  world rules (WLD), timeline events (TML), and graphics (GFX), plus edits to story/brief.md. Use when the user
  wants to add or change a character, location, graphic asset specification, subplot, secret, invented technology, or any
  story-bible detail, or to turn a "what if" idea into catalogued changes. Allocates permanent IDs,
  maintains [[ID]] cross-references, and reports which scenes are affected. Never edits
  abridged/ or manuscript/ (hand off to novel-sync) and never creates facts without research
  (hand off to novel-research).
---

# Novel-Author

The knowledge base is the novel's story bible and its single source of truth for continuity. You
help the author change it precisely. **The author owns the story: you propose, they approve.**

* Canonical format: [kb-format.md](references/kb-format.md) - read before writing entries.
* Review checklist: [kb-checklist.md](references/kb-checklist.md)
* Helper: `python <toolkit>/scripts/specnovel.py <command>`

## Modes

### A. Add or extend items
1. Read `story/brief.md` and the related KB entries (`specnovel.py trace <ID>` shows an item's
   neighborhood and the scenes that use it).
2. If the request is vague, ask **at most 3-5 focused questions** in one batch, each with a
   recommended default that fits the brief, the cast and the established facts.
3. Write entries per [kb-format.md](references/kb-format.md). Allocate each ID with
   `specnovel.py next-id <PREFIX>` and save the file before allocating the next ID.
4. Wire cross-references both ways where useful (e.g. relationship lines on both characters).
5. Any claim about the real world (history, science, law, geography, current events, real people)
   becomes an `RQ` item for `novel-research`; never write it as a fact from memory. When adding
   provisional entries with placeholders (`[...]`, `<...>`, or `TODO`), run
   `python scripts/specnovel.py placeholders --create-rq` to automatically register, prioritize,
   and link the research questions.
6. Run `specnovel.py check` and the checklist; fix your own errors.
7. Show the diff and your assumptions. Stop; do not touch the outline or derived layers.

### B. Change existing items ("what if")
1. Run `specnovel.py trace <ID>` for each affected item to see dependents and scenes.
2. Propose the edit and list the **ripple effects**: other KB entries that become inconsistent,
   outline scenes that reference the item, and timeline consequences.
3. After approval, apply the edit (and consistent edits to dependent KB entries).
4. If the outline must change, hand off to `novel-outline`. Tell the author that
   `specnovel.py impact --stage abridged` / `--stage manuscript` now lists the scenes to
   regenerate via `novel-sync`.

### C. Review the author's own edits
1. Run `specnovel.py delta --stage bible` (or `--stage brief`) to see ID-level and premise changes
   since the last baseline.
2. Apply [kb-checklist.md](references/kb-checklist.md); report findings as BLOCKER / WARNING /
   NIT with concrete replacement text.
3. Mechanical fixes (missing IDs via `next-id`, heading syntax, broken `[[ ]]` syntax) may be
   applied without asking, but must be reported.

### D. Accept the story bible or plan
When the author is satisfied with a batch of story bible changes:
`specnovel.py check`, `specnovel.py index`, then
`specnovel.py accept --stage bible -m "<summary>"` (or `--stage plan -m "<summary>"`).

### E. Triage editorial feedback
When the author provides direct feedback on draft scenes:
1. **Systemic Check**: If the note represents a recurring rule or canon change (e.g. character background,
   general voice tic, setting layout, historical fact), promote it to `kb/` (or propose an update to `story/style.md`).
2. **Local Directive**: If the note is scene-specific, local blocking, or prose-level texture that does not
   belong in global specs, record it in `story/editorial/EDT-NNN.md` (allocate with `next-id EDT`), setting
   `Target: [[SCN-...]]`, `Stage:`, and `Status: open`. This ensures it is automatically detected by
   `specnovel.py impact` and re-applied during rendering.

## Rules
* Never edit `abridged/` or `manuscript/` here; never create `FCT`/`SRC` entries here.
* Never renumber, reuse or "tidy" IDs. Deleted IDs stay retired.
* Never edit `story/synopsis.md` or `story/style.md` without explicit approval.
* Keep one concept per entry and one name per concept; record aliases in the entry.
* Store each piece of information once and reference it; do not copy facts into character or
  place entries (link `[[FCT-...]]` instead).
