# Outline format (canonical reference)

## Files and ordering
- The outline lives in `outline/`. A single `outline/outline.md` is fine; long novels may split
  into several files (`01-part-one.md`, `02-part-two.md`). Files are read in **name order**, and
  headings within a file in document order. That order is the novel's **reading order**.
- IDs never encode position. Chapter and part numbers in the compiled book are derived from order.

## Hierarchy
| Level | Heading | Prefix | Required |
|---|---|---|---|
| Part | `## PRT-001: Part title` | `PRT` | optional |
| Chapter | `### CHP-001: Chapter title` | `CHP` | yes |
| Scene | `#### SCN-001: Scene title` | `SCN` | yes |

Any heading levels work as long as scenes are **nested under** a chapter heading (deeper level)
and chapters under parts if parts are used. `check` fails on a scene that is not inside a chapter.
The chapter's own section (text between the chapter heading and its first scene) holds
chapter-level information; references there apply to all of its scenes (e.g. chapter-wide POV).

## Chapter fields
```markdown
### CHP-004: Night Crossing
- **Purpose:** what this chapter does for the novel (turning point, escalation, breather)
- **POV:** [[CHR-001]]
- **Span:** 1912-04-14 evening -> 1912-04-15 dawn
- **Target words:** 6000
```

## Scene fields
```markdown
#### SCN-014: The collision
- **When:** 1912-04-14, 23:40 ship's time ([[TML-004]])
- **Where:** [[PLC-007]]
- **POV:** [[CHR-001]]
- **Cast:** [[CHR-001]], [[CHR-003]], an unnamed steward
- **Plot:** escalates [[PLT-001]]; pays off [[PLT-005]] (setup in SCN-006)
- **Facts:** [[FCT-030]], [[FCT-031]]
- **World:** (futuristic or invented elements) [[WLD-002]]
- **Goal / conflict / outcome:** Elena wants to reach Karl's cabin; the steward bars E deck; she
  slips past but finds the cabin empty.
- **Beats:**
  1. A shudder, so slight that the card players don't look up.
  2. Elena notices the engines have stopped (per FCT-031 the engines were stopped soon after).
  3. Confrontation with the steward.
  4. Empty cabin; Karl's coat is gone, the letter is not.
- **Key dialogue:**
  - Steward: "Nothing to worry about, miss. Go back to bed."
  - Elena: "Then why are your hands shaking?"
- **Change:** Elena moves from irritation to fear; she now knows Karl left before the collision.
- **Reveals:** Karl's coat missing (clue for [[PLT-005]])
- **Target words:** 2500
- **Provisional:** (any assumption awaiting [[RQ-012]])
```

Guidance:
- **Beats** are terse, present-tense statements of what happens, in order. No prose.
- **Key dialogue** is optional; use it for lines that are plot-critical, thematically central or
  already loved by the author. Everything listed here must appear in the abridged draft.
- **Plot** uses verbs that show the thread's movement: *introduces, plants, advances, complicates,
  reverses, reveals, pays off, resolves*.
- **Facts** lists every researched fact the scene depends on, so a fact change flags the scene in
  `specnovel.py impact`.
- References in plain text (e.g. "setup in SCN-006") are fine for humans, but only `[[ID]]` links
  are tracked; link anything whose change should flag this scene.

## Parts (optional)
```markdown
## PRT-002: Part Two - The Water
- **Purpose:** ...
- **Span:** ...
```
