# Audit Checklists for Novel Verification

Use these structured checklists when conducting quality assurance across a 9-stage SpecNovelist project.

---

## 1. Character & Continuity Checklist (`world/characters/` & `narrative/`)

- [ ] **Physical Integrity**: Hair color, eye color, scars, height, handedness, and physical mannerisms
      match `world/characters/CHR-NNN.md` across all chapters.
- [ ] **Wound & Recovery Pacing**: Injuries sustained in earlier beats/scenes take believable time to heal
      and realistically impair the character in subsequent actions.
- [ ] **Knowledge State (Epistemic Hygiene)**:
  - Characters only act on facts they have directly witnessed, heard from others, or read (`Reveals:`, `Learns:`).
  - Characters do not refer to events that haven't occurred yet or secrets listed under `Hidden From:`.
- [ ] **Forms of Address & Politeness**:
  - Social hierarchy, formality, and titles are observed consistently (e.g. *Herr Doktor*, *my lord*,
    military ranks, intimate vs formal pronouns in translated languages).
- [ ] **Relationships & Arc Progression**:
  - The emotional distance between characters reflects their most recent interactions.
  - Character emotional growth adheres to the story arcs (`ARC-NNN`) and beats (`BET-NNN`) in `narrative/`.

---

## 2. Chronology & Geography Checklist (`world/timeline/` & `world/places/`)

- [ ] **Timeline Consistency**:
  - Beats (`BET-NNN`) and scenes (`SCN-NNN`) follow the chronological sequence in `world/timeline/timeline.md`
    (or intentional flashbacks/non-linear sequences are explicitly structured in `structure/outline.md` while preserving Narrative DAG causality).
  - Dates, days of the week, and times of day match between consecutive beats and scenes.
- [ ] **Travel Logistics**:
  - The duration of travel between locations (`PLC-NNN` in `world/places/`) is realistic for the period and transport mode
    (sailing ships, steamships, stagecoaches, trains, walking).
  - Time zones and local vs ship's time are accounted for in maritime or international settings.
- [ ] **Environmental Continuity**:
  - Weather in a scene matches what was established earlier in that day or location.
  - Astronomical details (sun position, sunrise/sunset, moon phases, tides) match period records
    if specified in `FCT-NNN`.

---

## 3. Fact Fidelity & Historical Accuracy Checklist (`research/` & `world/facts/`)

- [ ] **Fact Citation**:
  - Every historical or scientific claim in the novel traces back to a cataloged `[[FCT-...]]` item in `world/facts/`.
  - Every fact has at least one authoritative, corroborated `[[SRC-...]]` in `world/sources/` and links to the `[[RQ-...]]` in `research/questions.md` it resolves.
- [ ] **Anachronism Review**:
  - No modern slang, idiom, or psychological jargon appears in historical dialogue or close-POV narration
    (e.g. *"closure", "trauma bonding", "prioritize", "reach out", "down to earth"*).
  - Technology, material culture, and weaponry mentioned in the scene were demonstrably available at the
    story's exact date.
- [ ] **Documented Liberties**:
  - Any intentional historical deviation (compressed timeline, composite historical figure, altered geography)
    carries a documented `Liberty:` note in its `FCT` or `WLD` entry.
- [ ] **Speculative / World Rule Consistency**:
  - Speculative or technical rules in `world/rules/WLD-NNN.md` operate consistently under their declared limits, costs, and consequences.

---

## 4. Writing Style & Prose Craft Checklist (`setup/style.md` & `directives/`)

- [ ] **POV Rigor**:
  - POV matches the person and psychic distance specified in `setup/style.md` and the scene's `POV:` field.
  - No accidental head-hopping (narrator slipping into another character's private thoughts within the same scene).
- [ ] **Tense Discipline**:
  - Tense matches `setup/style.md` (past vs present) without accidental slippage.
  - Flashbacks follow the established pluperfect-to-simple-past convention.
- [ ] **Dialogue Conventions**:
  - Dialogue tags adhere to `setup/style.md` (e.g. *said/asked only; no adverbs on tags*).
  - Accent/dialect is rendered with word choice and syntax rather than heavy phonetic eye-dialect.
- [ ] **Anti-Pattern Eradication**:
  - Prose is free of generic AI-isms (*"tapestry", "testament to", "dance of shadows", "couldn't help but"*).
  - Filter words (*"she saw", "he heard", "she noticed"*) are minimized.
  - Overused physical clichés (*eyebrow raising, constant sighing, nodding, breath-catching*) are removed.
- [ ] **Sensory Richness**:
  - Non-visual senses (sound, smell, touch, temperature) anchor the scene within the opening beats.
  - Descriptions are drawn from the POV character's perspective and vocabulary.
- [ ] **Directive Adherence**:
  - Every `[[DIR-NNN]]` directive attached to the chapter, scene, sequenced beats, or participating characters is honored and preserved.

---

## 5. Traceability & Markdown Cleanliness Checklist

- [ ] `uv run python scripts/specnovel.py check` passes with 0 errors.
- [ ] `uv run python scripts/specnovel.py dag` passes with 0 cycle, reading-order, or essentiality errors.
- [ ] All chapter and scene headings match the canonical `# CHP-xxx: Title` and `## SCN-xxx: Title` format in `abridged/` and `manuscript/<locale>/`.
- [ ] No visible raw `[[ID]]` tags or `[...]` placeholders remain in `manuscript/` prose.
- [ ] Word counts are within target bounds (`uv run python scripts/specnovel.py stats`).
