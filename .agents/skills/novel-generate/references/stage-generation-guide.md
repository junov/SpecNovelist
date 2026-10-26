# Stage Generation Reference & Record Schemas

## 1. Stage 1 — Initial (`initial/`)
- `initial/synopsis.md`: Seed narrative synopsis.
- `initial/config.md`: Author identity, locales (`[primary]` marker), foreword path, glossary/bibliography toggles, publication metadata.

## 2. Stage 2 — Setup (`setup/`)
- `setup/brief.md`: Premise, genre, target length, POV, setting eras, research rigor.
- `setup/themes.md`:
  ```markdown
  ## THM-001: <Theme Title>
  - **Central Question:** <Dramatic question>
  - **Thesis / Antithesis:** <Tension>
  - **Directives:** [[DIR-001]]
  ```
- `setup/style.md`: Voice, POV, rhythm, dialogue, anti-patterns, `## Glossary Guidelines`, `## Graphics Guidelines`, `## Publication & Book Design Guidelines`, and `# Locale: <locale>` sections.

## 3. Stage 3 — Research Questions (`research/questions.md`)
```markdown
## RQ-001: <Question Title>
- **Status:** open
- **Priority:** high
- **Domain:** <history | science | geography | law | culture>
- **Question:** <Detailed question>
- **Context:** [[THM-001]]
```

## 4. Stage 4 — World (`world/`)
- `world/sources/SRC-NNN.md`: Author, Title, URL/Publication, Access Date, Reliability, Notes.
- `world/facts/FCT-NNN.md`: Claim, Sources (`[[SRC-NNN]]`), Answers (`[[RQ-NNN]]`), Narrative Implications.
- `world/characters/CHR-NNN.md`, `world/places/PLC-NNN.md`, `world/organizations/ORG-NNN.md`, `world/objects/OBJ-NNN.md`, `world/rules/WLD-NNN.md`, `world/timeline/TML-NNN.md`, `world/glossary/GLS-NNN.md`.

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

## 6. Directives (`directives/DIR-NNN.md`)
```markdown
# DIR-001: <Directive Title>

- **ID:** DIR-001
- **Status:** active
- **Locale:** all
- **Scope:** [[CHR-001]], [[ARC-001]]

## Instruction
<Single-source-of-truth instruction applied across all linked records during generation and synchronization.>
```
