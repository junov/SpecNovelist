# Stage Generation Reference & Record Schemas

## 1. Stage 1 — Initial (initial/)
### initial/synopsis.md
`markdown
# Synopsis: <Title>
## Premise
<High-concept core dramatic hook and narrative premise>

## Core Characters & Conflict
<Protagonist, antagonist, key relationships, central stakes>

## Plot Progression & Ending
<Beginning, inciting turn, midpoint reversal, climax, resolution>
`

### initial/config.md
`markdown
# Project Configuration
- **Title:** <Title>
- **Author:** <Author Name>
- **Primary Locale:** en-US
- **Target Locales:** [en-US]
- **Target Words:** 80000
- **Compilation:**
  - **Include Glossary:** true
  - **Include Foreword:** false
`

## 2. Stage 2 — Setup (setup/)
### setup/brief.md
`markdown
# Creative Brief: <Title>
## Premise
<Core narrative premise, high-concept elevator pitch, thematic hook>

## Genre & Target Audience
<Primary and secondary genres, age category, target readership>

## Scope & Target Length
<Word count target, volume structure, pacing milestones>

## Narrative Stance & Point of View
<POV format (e.g. third-person limited), narrative distance, tense>

## Setting Overview
<Primary era, geographic backdrop, sociopolitical backdrop, cultural atmosphere>

## Central Conflict & Stakes
<Central dramatic confrontation, personal vs societal stakes>

## Tone & Content Boundaries
<Dominant atmosphere, emotional palette, content boundaries>
`

### setup/themes.md
`markdown
# Thematic Pillars: <Title>
## THM-001: <Theme Title>
- **Central Question:** <Philosophical or dramatic dilemma>
- **Thesis / Antithesis:** <Thematic tension or opposing viewpoints>
- **Motifs & Symbols:** <Recurring imagery, metaphors, sensory elements>
- **Directives:** [[DIR-001]]
`

### setup/style.md
`markdown
# Style Guide: <Title>
## Core Aesthetic & Literary Stance
<Prose voice anchor, literary influences, sentence rhythm and syntax style>

## Perspective & Point of View Architecture
<Rules for interiority, psychic distance transitions, POV discipline>

## Sensory Palette & Textures
<Dominant sensory textures, color palette, lighting, acoustic motifs>

## Dialogue & Voice Conventions
<Cadence, subtext rules, vernacular, dialect constraints>

## Anti-Patterns & Prohibitions
<Banned tropes, cliches, stylistic habits to strictly avoid>

## Directives Preservation
(Explicitly integrate and preserve [[DIR-001]] and all linked directives)

## Publication & Book Design Guidelines
<Typography choices, scene break ornaments, section dividers>

## Graphics Guidelines
<Visual style, medium, composition and lighting rules for illustrations>

## Locale: en-US
`

## 3. Stage 3 — Research Questions (
esearch/questions.md)
`markdown
# Research Questions: <Title>
## RQ-001: <Question Title>
- **Status:** open
- **Priority:** high
- **Domain:** history | science | geography | law | culture | technology
- **Question:** <Detailed factual inquiry requiring verification>
- **Motivation:** <Why this question matters to narrative authenticity>
- **Context:** [[THM-001]], [[brief.md]]
`

## 4. Stage 4 — World (world/)
### world/sources/SRC-NNN.md
`markdown
# SRC-001: <Source Title>
- **Author:** <Author or Organization>
- **Publication / URL:** <Citation or link>
- **Access Date:** <Date>
- **Reliability:** primary | peer-reviewed | secondary | reference
- **Key Claims:** <Authoritative factual findings>
`

### world/facts/FCT-NNN.md
`markdown
# FCT-001: <Fact Title>
- **Statement:** <Verifiable factual statement>
- **Sources:** [[SRC-001]]
- **Answers:** [[RQ-001]]
- **Narrative Implications:** <Impact on story, world, or scenes>
`

### world/characters/CHR-NNN.md
`markdown
# CHR-001: <Character Name>
- **Role:** protagonist | antagonist | deuteragonist | supporting
- **Archetype:** <Dramatic archetype>
- **Traits:** <Core personality traits>
- **Internal Need vs External Want:** <Core psychological drive>
- **Voice & Register:** <Speech cadence, vocabulary, verbal quirks>
- **Relationships:** [[CHR-002]] (ally), [[CHR-003]] (rival)
- **Directives:** [[DIR-001]]
`

- Additional entity types follow equivalent catalog structures in world/places/PLC-NNN.md, world/organizations/ORG-NNN.md, world/objects/OBJ-NNN.md, world/rules/WLD-NNN.md, world/timeline/TML-NNN.md, world/glossary/GLS-NNN.md.

## 5. Stage 5 — Narrative Structure (`narrative/`)
### Story Arcs (`narrative/arcs.md`)
```markdown
## ARC-001: <Arc Title>
- **Type:** main | subplot | character
- **Themes:** [[THM-001]]
- **Characters:** [[CHR-001]]
- **Summary:** <Arc progression>
```

### Narrative Beats (`narrative/beats.md`)
```markdown
## BET-001: <Beat Title>
- **Place:** [[PLC-001]]
- **Time:** <Timestamp or relative period>
- **Arcs:** [[ARC-001]]
- **Dependencies:** none
- **Characters:** [[CHR-001]]
- **Facts:** [[FCT-001]]
- **Directives:** [[DIR-001]]
- **Summary:** <What happens and why it matters causally>

## BET-002: <Climax / Denouement Beat>
- **Place:** [[PLC-001]]
- **Time:** <Timestamp>
- **Arcs:** [[ARC-001]]
- **Dependencies:** [[BET-001]], [[ILL-001]]
- **Denouement:** true
- **Summary:** <Final causal resolution of the Narrative DAG>
```

### Illustrations (`narrative/illustrations.md`)
```markdown
## ILL-001: <Illustration Title>
- **Type:** scene-artwork | map | diagram | portrait | cover | front-matter | back-matter
- **Arcs:** [[ARC-001]]
- **Dependencies:** [[BET-001]]
- **Depicts:** [[CHR-001]], [[PLC-001]]
- **Caption:** <Caption text>
- **Description:** <Textual visual specification—no image files rendered in Stage 5>
```

## 6. Stage 6 — Physical Structure (`structure/outline.md`)
```markdown
# VOL-001: Volume I

## ACT-001: Act I

### CHP-001: <Chapter Title>

#### SCN-001: <Scene Title>
- **Chapter:** [[CHP-001]]
- **POV:** [[CHR-001]]
- **Place:** [[PLC-001]]
- **Time:** <Timestamp>
- **Beats:** [[BET-001]], [[BET-002]]
- **Illustrations:** [[ILL-001]]
- **Cast:** [[CHR-001]]
- **Facts:** [[FCT-001]]
- **Directives:** [[DIR-001]]
- **Target Words:** 1500
- **Goal / Conflict / Outcome:** <G/C/O summary>
- **Key Dialogue:**
  - [[CHR-001]]: "<Essential line>"
```

## 7. Stage 7 — Abridged Novel (`abridged/CHP-NNN.md`)
```markdown
# CHP-001: <Chapter Title>

## SCN-001: <Scene Title>
<!-- Directives: [[DIR-001]] -->
<Condensed chapter draft containing all sequenced beats ([[BET-001]], [[BET-002]]), causal turns, and essential dialogue, with lean descriptive texture.>
```

## 8. Stage 8 — Manuscript (`manuscript/<locale>/CHP-NNN.md`)
```markdown
# CHP-001: <Chapter Title>

## SCN-001: <Scene Title>
<!-- Directives: [[DIR-001]] -->
<Polished literary prose rendered in the target locale according to setup/style.md and linked directives. Zero visible [[ID]] metadata.>
```

## 9. Stage 9 — Publishable Material (`publishable/`)
- `publishable/graphics/ILL-NNN.png` (and localized `ILL-NNN.<locale>.png` when `Has Text: true`)
- `publishable/<locale>/manuscript.{md,epub,pdf,docx}` compiled via `uv run python scripts/specnovel.py compile`

## 10. Cross-Stage Directives (`directives/DIR-NNN.md`)
```markdown
# DIR-001: <Directive Title>
- **Stage:** all
- **Scope:** [[CHR-001]], [[ARC-001]]
- **Locale:** all
- **Status:** active
- **Instruction:** <Single-source-of-truth instruction applied across all linked records during generation and synchronization.>
```
