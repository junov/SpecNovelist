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
- **Graphics:** [[GFX-001]] (optional chapter-level header asset or placeholder [GFX: North Atlantic ice field map])
- **Target words:** 6000
```

## Scene fields
```markdown
#### SCN-014: The collision
- **Prerequisites:** [[SCN-006]], [[PLT-001]]
- **Function:** causal-progression (or atmospheric-breather, thematic-mirror, comic-relief, character-reflection, epistolary-interlude, pacing-breather)
- **When:** 1912-04-14, 23:40 ship's time ([[TML-004]])
- **Where:** [[PLC-007]]
- **POV:** [[CHR-001]]
- **Cast:** [[CHR-001]], [[CHR-003]], an unnamed steward
- **Plot:** escalates [[PLT-001]]; pays off [[PLT-005]] (setup in SCN-006)
- **Plants:** [[OBJ-003]] (Chekhov gun setup; must eventually be paid off)
- **Pays off:** [[OBJ-001]] (Chekhov gun payoff; verifies earlier plant)
- **Reveals:** [[PLT-005]] (secret or plot clue revealed)
- **Learns:** [[CHR-001]] (characters who acquire this knowledge)
- **Hidden From:** [[CHR-003]] (characters forbidden from possessing or acting on this knowledge)
- **Facts:** [[FCT-030]], [[FCT-031]]
- **World:** (futuristic or invented elements) [[WLD-002]]
- **Graphics:** [[GFX-002]] (or placeholder [GFX: Transverse watertight bulkhead cutaway schematic showing boiler room 6])
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
- **Target words:** 2500
- **Provisional:** (any assumption awaiting [[RQ-012]])
- **Denouement:** true (optional; only on the final resolving scene / root of the DAG)
```

Guidance:
- **Graphics**: Governed by `story/style.md` > `## Graphics Guidelines`. `novel-outline` decides where visual
  assets are needed based on the style's `Intensity`, `Rendering Styles` (artistic vs technical), and `Usage Rules`.
  - Link cataloged assets using `[[GFX-xxx]]`.
  - Specify uncataloged visual needs using functional placeholders: `[GFX: <type> - <description>]`.
  - Referencing a graphic in the outline binds it to the **Story DAG**, activating it so that `specnovel.py impact --stage graphics`
    renders it during synchronization while skipping inactive KB assets to conserve AI tokens.
- **Prerequisites**: Explicitly lists every earlier scene, plot element, or fact that must causally
  occur or be established before this scene can happen. Must precede this scene in the outline.
- **Denouement**: Designates the final resolving scene as the root of the story DAG. If omitted,
  the last scene in reading order is assumed to be the denouement root.
- **Beats** are terse, present-tense statements of what happens, in order. No prose.
- **Key dialogue** is optional; use it for lines that are plot-critical, thematically central or
  already loved by the author. Everything listed here must appear in the abridged draft.
- **Plot** uses verbs that show the thread's movement: *introduces, plants, advances, complicates,
  reverses, reveals, pays off, resolves*.
- **Facts** lists every researched fact the scene depends on, so a fact change flags the scene in
  `specnovel.py impact`.
- References in plain text (e.g. "setup in SCN-006") are fine for humans, but only `[[ID]]` links
  are tracked; link anything whose change should flag this scene.

## Story Causality DAG Rules
The outline is a serialization of a Directed Acyclic Graph (DAG) representing narrative causality:
1. **Acyclicity**: Causality cannot loop ($A \to B \to \dots \to A$ is forbidden).
2. **Reading Order Coherence**: For every prerequisite dependency $u \to v$ ($v$ requires $u$),
   $u$ must appear before $v$ in the outline reading order ($pos(u) < pos(v)$).
3. **Denouement Path Essentiality**: The novel's final denouement is the DAG root. Every element in the
   story must have a directed path to the denouement. Unconnected dead-ends or extraneous subplots with
   no causal impact on the novel's outcome are rejected.
4. **Automated Verification**: Run `specnovel.py dag` and `specnovel.py check` to validate all 3 invariants.

### Multiple Valid Serializations & Dramatic Effects
A DAG represents a **partial order**, not a single rigid sequence. Consequently, there is almost always
**more than one valid serialization order** for a story's DAG. Any linear extension where every node is
preceded by its prerequisites satisfies causal integrity.

The selection among multiple valid serialization orders is an essential creative choice governed by
**`story/style.md`** and the desire to achieve specific dramatic effects:

1. **Suspense vs. Mystery (Dramatic Irony)**:
   - If Branch A (the conspiracy prepares an ambush) and Branch B (the protagonist buys an ocean ticket)
     are mutually independent paths converging on Branch C (the departure), ordering $A \to B \to C$ creates
     **suspense** (the reader sees the trap closing).
   - Ordering $B \to A \to C$ creates a **mystery / ticking clock** feeling.
2. **Cross-Cutting & Cliffhangers**:
   - In novels with parallel character POVs or multi-threaded subplots, interleaving scenes across branches
     ($Thread1\_Scene1 \to Thread2\_Scene1 \to Thread1\_Scene2 \dots$) allows chapter breaks to land on
     unresolved turns, maintaining dramatic tension.
3. **Pacing & Tension Modulation**:
   - `story/style.md` defines the novel's cadence. Causally independent character beats, atmospheric pauses,
     or epistolary interludes can be sequenced between intense plot escalations to regulate emotional rhythm.
4. **Thematic Juxtaposition**:
   - Placing two independent scenes consecutively creates an implicit dialogue between them (e.g. juxtaposing
     a luxurious first-class salon conversation with the grueling boiler room shift below), letting thematic
     meaning emerge through montage without editorializing.
5. **Information Economy & Clue Seeding**:
   - Clues (`FCT` or `PLT` revelations) can be placed early in reading order to invite reader speculation,
     or delayed until just before their dramatic payoff for sudden impact.

## Parts (optional)
```markdown
## PRT-002: Part Two - The Water
- **Purpose:** ...
- **Span:** ...
```
