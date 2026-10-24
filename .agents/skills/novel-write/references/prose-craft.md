# Prose Craft & Manuscript Rendering Reference

This guide provides practical craft techniques for translating abridged scenes into full literary
manuscript prose while adhering to `story/style.md` and `kb/`.

---

## 1. Expanding Abridged Scenes into Full Prose

The abridged draft provides the **what**: the events, the turns, the dialogue, the blocking.
The manuscript provides the **how it feels**: the texture, the atmosphere, the interior psychology,
and the narrative voice.

### Techniques of Expansion

1. **Beats to Micro-actions**:
   - In abridged: *"Elena signed the ledger and looked at the captain."*
   - In manuscript: Show the physical reality: the dip-pen scratching the rough paper, the ink
     blotting on the damp page, the pause before signing, the lift of her chin.
2. **Dialogue Expansion (Subtext and Silence)**:
   - Keep the spoken words intact.
   - Expand the **space between words**: physical business, missed eye contact, changes in breathing,
     what the characters choose *not* to say, and how their bodies betray their composure.
3. **Sensory Grounding from `PLC`**:
   - Every scene has a temperature, a smell, a quality of light, a background noise.
   - Anchor the scene in at least two non-visual senses (smell, hearing, touch, taste) within the
     first three paragraphs.
4. **Deep Interiority**:
   - Reveal the character's immediate perception and value judgments.
   - Filter all sensory information through their personality, background, and current stakes.
     A sailor and an art collector do not see the same harbor.

---

## 2. Clarifying Time and Space Transitions from `PLT` Metadata

A primary cause of reader disorientation in multi-thread fiction is ambiguous spatio-temporal transitions:
jumping between scenes without clearly establishing **how much time has elapsed** or **where the character is now**.

Each plot element (`PLT`) in SpecNovelist is required to carry explicit **Time** and **Place** metadata
(e.g., `Time: 1912-04-02 to 1912-04-14`, `Place: [[PLC-001]] to [[PLC-002]]`). When rendering prose for scenes
advancing these threads, `novel-write` utilizes this metadata to construct immediate, seamless reader orientation.

### Techniques for Spatiotemporal Transitions

1. **Concrete Temporal Markers in Scene Openings**:
   - Establish elapsed time within the first two sentences using concrete sensory or environmental indicators
     rather than abstract dates:
     - *Weak / Disorienting*: "Elena was in the telegraph office. She tapped her fingers on the counter."
     - *Oriented*: "By Thursday evening, three days after Karl’s courier slipped out of Hamburg, the telegraph
       office smelled of damp greatcoats and stale tobacco."
   - Employ physiological time markers: stiffness from travel, stubble, fading bruises, cooling stoves, candle stubs,
     or the chiming of specific city bells.

2. **Crossing Spatial Thresholds**:
   - When transitioning to a new `Place:` (`PLC`), show the physical arrival or movement across the boundary:
     - Describe the acoustic shift (the roar of the harbor basin giving way to the muffled ticking of an inner office).
     - Ground the temperature and air quality immediately (the sharp, salt-rimed wind off the Elbe vs. coal fumes).
     - Show the physical toll of distance: grit in clothes, sea legs, horse lather, railway soot on linen cuffs.

3. **Bridging Thread Continuity**:
   - Remind the reader of the active `PLT` thread's progression through time and space.
   - Filter the time/place shift through the viewpoint character's urgent calculation:
     *"Twelve hours left before the tide turned in Cuxhaven, and Karl was still three leagues upriver."*

---

## 3. Weaving Researched Facts (`FCT`) Seamlessly

A fatal flaw in historical, scientific, or contemporary fiction is the **infodump** (characters
explaining history or science to each other, or the narrator stopping the story to deliver a mini-essay).

### The Three Rules of Fact Integration

1. **The Friction Principle**:
   Facts enter the story only when they cause friction, cost money, pose physical obstacles, or
   force decisions.
   - *Bad (lecture)*: "The HAPAG line was founded in 1847 and operated sixty-four steamers, which
     required coal from Wales because domestic coal burned too dirty."
   - *Good (friction)*: "The bunkering gangs had been loading Welsh coal since midnight, and the
     fine black grit settled into Elena’s eyelashes every time the wind shifted off the basin."
2. **The POV Filter**:
   Only describe what the POV character would notice or care about in that moment. A doctor notices
   the wheeze in a porter's chest; an engineer notices the vibration in the floor plates.
3. **Tactile Vocabulary**:
   Use period-accurate or technical terms naturally as everyday tools, without italicizing or
   defining them for the reader. Let context convey meaning.

---

## 4. Banishing Generic AI Prose Habits

`story/style.md` lists forbidden anti-patterns. AI writing agents tend to fall into recurring
stylistic ruts unless actively checked. Guard against these universal pitfalls:

### Banned Clichés and Structural Habits

| AI Rut | Problem | Fix |
|---|---|---|
| *"A testament to..." / "A tapestry of..."* | Generic, hollow abstraction. | Name the specific concrete object and its physical condition. |
| *"She couldn't help but feel..."* | Filter words; weakens immediacy. | State the feeling or physical sensation directly. |
| *"In that moment, he realized..."* | Melodramatic announcement. | Show the thought landing or the physical reaction. |
| *"Let out a breath she didn't know she was holding"* | Overused cliché. | Describe the real physiological reaction: tightness in the ribs, shallow breath. |
| *Constant sighing, nodding, swallowing, eyebrow-raising* | Repetitive placeholder gestures. | Give characters distinctive, purposeful physical actions rooted in their `CHR` entry. |
| *Neat, moralizing concluding paragraphs* | Wraps up scenes in an essayistic summary. | End on a sharp physical image, a lingering question, or mid-movement. |
| *Over-explaining metaphors* | "The ship was like a leviathan, huge and terrifying." | Trust the image: "The iron hull rose five stories above the slip." |

---

## 5. Voice Anchors & Style Compliance

Before rendering any scene:
1. Open `story/style.md` to `## 15. Voice anchors`.
2. Read the quoted sample passages aloud (or analyze their sentence structures).
3. Check:
   - What is the average sentence length?
   - How frequently are fragments or semicolons used?
   - Is dialogue clipped or expansive?
   - What is the ratio of sensory detail to interior thought?
4. Match that exact register.

---

## 6. Clean Prose Checklist

Before saving to `manuscript/CHP-xxx.md`:
- [ ] Are all plot events from `abridged/` present without deviation?
- [ ] Is all key dialogue preserved word-for-word?
- [ ] Are time elapsed and setting shifts immediately clear from the opening sentences (informed by `PLT` time/place)?
- [ ] Are all raw `[[ID]]` tags removed from the narrative text?
- [ ] Is the scene within ±15% of its target word count?
- [ ] Are period details grounded in sourced `FCT`s?
- [ ] Does the ending beat land with the exact value shift specified in the outline?
