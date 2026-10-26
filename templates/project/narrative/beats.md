# Narrative Beats (Beat DAG)

<!--
STAGE 4: NARRATIVE STRUCTURE (narrative/beats.md).
Narrative beats (BET-NNN) form a Directed Acyclic Graph (DAG):
1. Every beat MUST specify:
   - **Place:** [[PLC-NNN]] (where the beat occurs)
   - **Time:** <when the beat occurs> (e.g. 1912-04-10 morning, or [[TML-NNN]])
   - **Arcs:** [[ARC-NNN]] (must be associated with at least one Story Arc)
   - **Dependencies:** [[BET-NNN]], ... (or None; other beats that must be told earlier for causality, narrative coherence, or dramatic effect)
2. The root of the Beat DAG is the denouement beat (`- **Denouement:** true`).
3. Every beat in the DAG must have a directed path leading to the denouement beat.

Example:
## BET-001: Elena Receives the Unsigned Letter
- **Place:** [[PLC-001]]
- **Time:** 1912-04-10 08:00
- **Arcs:** [[ARC-001]]
- **Dependencies:** None
- **Characters:** [[CHR-001]]
- **Plants:** [[OBJ-001]]
- **Facts:** [[FCT-001]]
- **Summary:** Elena opens an unsigned letter warning that Karl is boarding the steamer under an alias.
- **Key Dialogue:** "If you wish to see him alive, meet the tender before noon."
- **Directives:** [[DIR-...]]
-->
