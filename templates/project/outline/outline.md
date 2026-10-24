# Outline

<!--
The skeleton of the novel IN READING ORDER. Built by the novel-outline skill.
Reading order is the order of headings in this file (and of files in outline/, sorted by name,
if you split the outline into several files such as 01-part-one.md, 02-part-two.md).
IDs never encode position: moving a scene is done by moving its block.

Story Causality DAG & Reading Order Coherence:
- Every scene and plot element defines which earlier elements are its prerequisites via
  `- **Prerequisites:** [[SCN-...]], [[PLT-...]]`.
- The outline is a serialization of this causality DAG: every element in the outline must be preceded
  by all its prerequisites (`specnovel.py check` & `specnovel.py dag` enforce this).
- Multiple Valid Serializations: The story DAG admits multiple valid topological sorts. The chosen
  serialization order is an artistic instrument shaped by `story/style.md` and desired dramatic effects
  (e.g., suspense, dramatic irony, cross-cutting between subplots, pacing cadence, and thematic juxtaposition).
- The story DAG must be acyclic (no circular causality).
- The root of the DAG is the novel's final denouement (marked with `- **Denouement:** true` or designated
  in `story/brief.md`; defaults to the last scene).
- Every scene and plot element must have a directed causal path to the root denouement (no dead-end / inessential scenes).

Hierarchy (Parts are optional):

```markdown
## PRT-001: Part One - The Crossing

### CHP-001: The Letter
Purpose: What this chapter does for the novel.
POV: [[CHR-001]] | Time: [[TML-003]] | Setting: [[PLC-002]]
Graphics: [[GFX-001]] (optional chapter header asset or placeholder [GFX: Harbor map])

#### SCN-001: Elena receives the letter
- **Prerequisites:** None (or list [[SCN-...]], [[PLT-...]], [[FCT-...]])
- **When:** 1912-04-02, morning (after [[TML-002]])
- **Where:** [[PLC-002]]
- **POV:** [[CHR-001]]
- **Cast:** [[CHR-001]], [[CHR-004]]
- **Plot:** advances [[PLT-001]] (setup); plants [[PLT-007]]
- **Facts:** [[FCT-003]], [[FCT-011]]
- **World:** [[WLD-002]]
- **Graphics:** [[GFX-001]] (or placeholder [GFX: Facsimile of the unsigned letter with wax seal], or None)
- **Goal / conflict / outcome:** Elena wants...; blocked by...; ends with...
- **Beats:**
  1. ...
  2. ...
- **Key dialogue:** "..." (must survive into the abridged and final text)
- **Change:** what is different at the end of the scene (value shift, knowledge gained)
- **Target words:** 2500
- **Denouement:** true (optional; designate the root of the story DAG; defaults to the last scene)
```
-->
