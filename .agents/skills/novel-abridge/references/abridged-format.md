# Abridged Format and Style Guide

The abridged version of a SpecNovelist novel (`abridged/`) is an intermediate artifact designed to
verify plot execution, scene rhythm, dramatic tension, and dialogue before the prose is rendered
with full atmospheric depth.

---

## File and Heading Organization

1. **One file per chapter**:
   `abridged/CHP-001.md`, `abridged/CHP-002.md`, etc.
2. **Headings match the outline exactly**:
   ```markdown
   # CHP-001: The Letter

   ## SCN-001: Elena receives the letter
   prose of scene 1...

   ## SCN-002: Karl refuses
   prose of scene 2...
   ```
3. **No extra scenes or missing scenes**:
   `specnovel.py check` enforces that every scene defined in `outline/` appears under its assigned
   chapter in the exact reading order specified by the outline.

---

## What Belongs in an Abridged Scene

An abridged scene is **real fiction**, not a synopsis or a bulleted summary. A reader should be
able to read it from start to finish and experience the entire story.

| Element | In Abridged Version? | How it is Handled |
|---|---|---|
| **Plot events** | **Yes (100%)** | Every action, decision, obstacle, and revelation from the outline beats happens on the page in chronological order. |
| **Key dialogue** | **Yes (100%)** | All lines marked under `Key dialogue:` in the outline must be spoken verbatim. |
| **Supporting dialogue** | **Yes (80–100%)** | Conversations are written out with full subtext, conflict, and character voice. No summarizing dialogue (*"They talked about their childhood"*). |
| **Blocking & physical action** | **Yes (functional)** | Characters move through space clearly. Entrances, exits, physical confrontations, object hand-offs, and spatial movements are unambiguous. |
| **Emotional turns** | **Yes (essential)** | The psychological and emotional shift of the POV character is shown through action, speech, and direct reaction. |
| **Atmospheric description** | **Minimal (10–20%)** | Only the essential sensory details needed to anchor the reader and clarify the physical environment. No extended paragraphs describing wallpaper, weather, or distant scenery. |
| **Interiority / introspection** | **Lean (20–30%)** | Core thoughts, immediate dilemmas, and internal decisions are shown, but extended philosophical reflections or memory digressions are left for the manuscript stage. |
| **Historical / technical exposition** | **Functional** | Researched facts are present only in so far as characters interact with them or mention them. |

---

## Comparison: Outline vs. Abridged vs. Manuscript

To illustrate the difference in density and focus across the three artifacts:

### 1. Outline (`outline/outline.md`)
```markdown
#### SCN-001: Elena receives the letter
- **Where:** [[PLC-002]] (Hamburg pier)
- **POV:** [[CHR-001]] (Elena)
- **Cast:** [[CHR-001]], a courier boy
- **Facts:** [[FCT-004]] (HAPAG dock procedures)
- **Beats:**
  1. Elena waits in the rain at the HAPAG cargo gate.
  2. A courier arrives with a telegram envelope marked with Karl's seal.
  3. She tips the boy, tears open the envelope, and reads Karl's refusal.
- **Key dialogue:**
  - Elena: "Tell me he didn't give this to you in Altona."
  - Boy: "He said to run until my boots leaked, Fräulein."
- **Change:** Elena realizes Karl has already made arrangements to flee without her.
- **Target words:** 1800
```

### 2. Abridged Version (`abridged/CHP-001.md`)
*Length: ~450 words. Notice: complete narrative flow, all beats present, all key dialogue, clear conflict, but lean description.*

```markdown
## SCN-001: Elena receives the letter

The HAPAG cargo gate remained barred against the morning rain. Elena pulled her wool collar tight against the damp, watching the dockworkers haul crates toward the gangway. It was twenty past eight; the courier was late.

Splashing footsteps sounded from behind the freight shed. A boy in a soaked cap skidded to a halt on the cobblestones, clutching a yellow envelope.

"Fräulein Voss?" He gasped for breath, his fingers red with cold. "From the telegraph office on Große Elbstraße."

Elena snatched the envelope. In the corner, stamped in dried purple wax, was Karl’s merchant seal. Her stomach tightened. "Tell me he didn't give this to you in Altona."

"He said to run until my boots leaked, Fräulein."

She pressed a two-mark coin into his wet palm without taking her eyes off the wax. The boy vanished back toward the street.

Elena tore through the paper. Two lines, written in Karl's frantic, slanted hand:

*Do not board the Kaiserin. They were at the warehouse before dawn. I have taken the southern route through Bremen. If you value your life, burn the ledger and go home to Mother.*

The rain drummed against the parchment, smudging the ink. Southern route. He was not coming to the harbor at all. He had abandoned their berths, and by noon the police inspectors would be at the pier.

Elena crushed the note inside her glove. She wasn't going back to Mother.
```

### 3. Manuscript Version (`manuscript/CHP-001.md`)
*Length: ~1800 words. Rendered from the abridged draft + `story/style.md` + sensory details from `PLC-002` + period texture from `FCT-004`.*

*Contains full historical atmosphere: the smell of wet coal and horse manure, the hydraulic clatter of the steam winches, Elena's sensory reaction to the cold wind off the Elbe, interior thoughts on her family debt, the historical cadence of the boy's Low German phrasing, and complete stylistic depth.*

---

## Self-Check for Abridged Scenes

Before approving an abridged chapter:
1. Did any beat from the outline get skipped? (If yes, restore it).
2. Is every line of key dialogue present word-for-word?
3. Is dialogue written out instead of summarized?
4. Did extraneous subplots or invented characters creep in? (If so, strip them or update the outline first).
5. Does the scene end with the specified value change?
