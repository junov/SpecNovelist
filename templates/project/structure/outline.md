# Physical Structure

<!--
STAGE 6: PHYSICAL STRUCTURE (structure/outline.md).
Defines the physical architecture of the book in reading order:
- Volumes (VOL-NNN, optional)
- Acts (ACT-NNN, optional)
- Chapters (CHP-NNN)
- Scenes (SCN-NNN): Each scene is an ordered sequence of Beats ([[BET-NNN]]) and Illustrations ([[ILL-NNN]])
  from Stage 5 (narrative/).

Reading Order Coherence:
Every node's dependencies (`Dependencies:` in narrative/beats.md or narrative/illustrations.md) MUST appear
earlier in the physical reading order (either in an earlier scene or earlier in the same scene's sequence).
If a scene uses separate `- **Beats:**` and `- **Illustrations:**` fields instead of `- **Sequence:**`,
SpecNovelist automatically respects intra-scene DAG dependencies between them.

Example:
# VOL-001: Volume I

## ACT-001: Act I - Departure

### CHP-001: The Letter
- **POV:** [[CHR-001]]

#### SCN-001: Morning at the Pier
- **POV:** [[CHR-001]]
- **Where:** [[PLC-001]]
- **When:** 1912-04-10 morning
- **Cast:** [[CHR-001]]
- **Sequence:** [[BET-001]], [[ILL-001]], [[BET-002]]
- **Target words:** 2000
- **Directives:** [[DIR-...]]
-->
