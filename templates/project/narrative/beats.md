# Narrative Beats (Narrative DAG)

<!--
STAGE 5: NARRATIVE STRUCTURE (narrative/beats.md).
Narrative beats (BET-NNN) and narrative illustrations (ILL-NNN) form a unified Directed Acyclic Graph (DAG):

1. Mandatory Fields (Every beat MUST specify):
   - **Place:** [[PLC-NNN]] (where the beat occurs; must reference a cataloged place in `world/places/`)
   - **Time:** <when the beat occurs> (e.g. `1912-04-10 08:00`, `Day 3 Morning`, or a timeline link `[[TML-NNN]]`)
   - **Arcs:** [[ARC-NNN]], ... (must be associated with at least one Story Arc in `narrative/arcs.md`)
   - **Dependencies:** [[BET-NNN]], [[ILL-NNN]], ... (or `None`; upstream beats or illustrations in the Narrative DAG that must precede this beat for causality, narrative coherence, or dramatic effect)

2. Optional Fields (and their roles in the data structure):
   - **Denouement:** `true` | `false` — Marks this beat as the root denouement of the Narrative DAG. Every node in the Narrative DAG must have a directed path leading to the denouement (unless exempted by `Function:`).
   - **Function:** `atmospheric-breather` | `thematic-mirror` | `comic-relief` | `character-reflection` | `epistolary-interlude` | `pacing-breather` — Declares a non-causal artistic/pacing role that exempts a leaf node from requiring a directed causal path to the denouement.
   - **Characters** (or **Cast**): [[CHR-NNN]], ... — Characters participating in or affected by this beat; used for traceability (`specnovel.py trace`), character agency/screen-time telemetry, and epistemic validation.
   - **POV:** [[CHR-NNN]] — Optional beat-level point-of-view character anchor when a beat requires a specific focal perspective.
   - **Facts:** [[FCT-NNN]], ... — Researched world facts (`world/facts/`) that ground this beat; drives automatic bibliography inclusion (`specnovel.py bibliography`) and downstream synchronization impact tracking when facts change.
   - **Objects:** [[OBJ-NNN]], ... — Key world objects or props involved in the beat.
   - **Rules:** [[WLD-NNN]], ... — World rules or systems (`world/rules/`) exercised in this beat.
   - **Plants:** [[OBJ-NNN]], [[FCT-NNN]], ... — Chekhov's gun setup: introduces a prop, clue, or plot element that must be paid off in a later beat/scene (`specnovel.py check` enforces that every plant has a downstream payoff and automatically adds a causal edge from plant to payoff).
   - **Pays off:** [[OBJ-NNN]], [[FCT-NNN]], ... — Chekhov's gun resolution: pays off an element planted in an earlier beat/scene (`specnovel.py check` blocks unearned payoffs that lack a prior plant).
   - **Reveals:** [[FCT-NNN]], [[OBJ-NNN]], [[ARC-NNN]], ... — Epistemic tracking: secrets, mysteries, or plot truths disclosed during this beat.
   - **Learns:** [[CHR-NNN]], ... — Epistemic tracking: characters who learn the `Reveals:` information during this beat.
   - **Hidden From:** [[CHR-NNN]], ... — Epistemic tracking / dramatic irony: characters explicitly kept ignorant of `Reveals:` (`specnovel.py check` blocks downstream beats/scenes where an excluded character acts on hidden information before learning it).
   - **Valence:** float (`-1.0` to `+1.0`) — Emotional charge / dramatic trajectory score for pacing and emotional-arc telemetry (`specnovel.py audit`).
   - **Summary:** <concise description> — Prose summary of the causal event, conflict turn, or dramatic action occurring in the beat.
   - **Key Dialogue:** <quoted lines> — Essential lines of dialogue or verbal turns that must be preserved in Stage 7 (`abridged/`) and Stage 8 (`manuscript/`).
   - **Directives:** [[DIR-NNN]], ... — Cross-stage directives (`directives/DIR-NNN.md`) locking in user feedback or DRY-factored instructions governing how this beat is generated and synchronized.

Example:
## BET-001: Elena Receives the Unsigned Letter
- **Place:** [[PLC-001]]
- **Time:** 1912-04-10 08:00
- **Arcs:** [[ARC-001]]
- **Dependencies:** None
- **Characters:** [[CHR-001]]
- **Facts:** [[FCT-001]]
- **Plants:** [[OBJ-001]]
- **Reveals:** [[FCT-001]]
- **Learns:** [[CHR-001]]
- **Hidden From:** [[CHR-002]]
- **Valence:** -0.4
- **Summary:** Elena opens an unsigned letter warning that Karl is boarding the steamer under an alias.
- **Key Dialogue:** "If you wish to see him alive, meet the tender before noon."
- **Directives:** [[DIR-001]]
-->
