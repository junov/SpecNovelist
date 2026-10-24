# Audit Checklists for Novel Verification

Use these structured checklists when conducting quality assurance across a SpecNovelist project.

---

## 1. Character & Continuity Checklist

- [ ] **Physical Integrity**: Hair color, eye color, scars, height, handedness, and physical mannerisms
      match `kb/characters/` across all chapters.
- [ ] **Wound & Recovery Pacing**: Injuries sustained in earlier scenes take believable time to heal
      and realistically impair the character in subsequent actions.
- [ ] **Knowledge State (Epistemic Hygiene)**:
  - Characters only act on facts they have directly witnessed, heard from others, or read.
  - Characters do not refer to events that haven't occurred yet or secrets they have not uncovered.
- [ ] **Forms of Address & Politeness**:
  - Social hierarchy, formality, and titles are observed consistently (e.g. *Herr Doktor*, *my lord*,
    military ranks, intimate vs formal pronouns in translated languages).
- [ ] **Relationships & Arc Progression**:
  - The emotional distance between characters reflects their most recent interactions.
  - Character emotional growth adheres to the arc specified in `PLT`.

---

## 2. Chronology & Geography Checklist

- [ ] **Timeline Consistency**:
  - Events follow the chronological sequence in `kb/timeline/timeline.md` (or intentional flashbacks
    are explicitly marked).
  - Dates, days of the week, and times of day match between scenes.
- [ ] **Travel Logistics**:
  - The duration of travel between locations (`PLC`) is realistic for the period and transport mode
    (sailing ships, steamships, stagecoaches, trains, walking).
  - Time zones and local vs ship's time are accounted for in maritime or international settings.
- [ ] **Environmental Continuity**:
  - Weather in a scene matches what was established earlier in that day or location.
  - Astronomical details (sun position, sunrise/sunset, moon phases, tides) match period records
    if specified in `FCT`.

---

## 3. Fact Fidelity & Historical Accuracy Checklist

- [ ] **Fact Citation**:
  - Every historical or scientific claim in the novel traces back to a cataloged `[[FCT-...]]` item.
  - Every fact has at least one authoritative, corroborated `[[SRC-...]]`.
- [ ] **Anachronism Review**:
  - No modern slang, idiom, or psychological jargon appears in historical dialogue or close-POV narration
    (e.g. *"closure", "trauma bonding", "prioritize", "reach out", "down to earth"*).
  - Technology, material culture, and weaponry mentioned in the scene were demonstrably available at the
    story's exact date.
- [ ] **Documented Liberties**:
  - Any intentional historical deviation (compressed timeline, composite historical figure, altered geography)
    carries a documented `Liberty:` note in its `FCT` or `WLD` entry.
- [ ] **Futuristic Consistency**:
  - Speculative rules in `WLD` operate consistently under their declared limits, energy costs, and consequences.

---

## 4. Writing Style & Prose Craft Checklist

- [ ] **POV Rigor**:
  - POV matches the person and psychic distance specified in `story/style.md`.
  - No accidental head-hopping (narrator slipping into another character's private thoughts within the same scene).
- [ ] **Tense Discipline**:
  - Tense matches `story/style.md` (past vs present) without accidental slippage.
  - Flashbacks follow the established pluperfect-to-simple-past convention.
- [ ] **Dialogue Conventions**:
  - Dialogue tags adhere to `style.md` (e.g. *said/asked only; no adverbs on tags*).
  - Accent/dialect is rendered with word choice and syntax rather than heavy phonetic eye-dialect.
- [ ] **Anti-Pattern Eradication**:
  - Prose is free of generic AI-isms (*"tapestry", "testament to", "dance of shadows", "couldn't help but"*).
  - Filter words (*"she saw", "he heard", "she noticed"*) are minimized.
  - Overused physical clichés (*eyebrow raising, constant sighing, nodding, breath-catching*) are removed.
- [ ] **Sensory Richness**:
  - Non-visual senses (sound, smell, touch, temperature) anchor the scene within the opening beats.
  - Descriptions are drawn from the POV character's perspective and vocabulary.

---

## 5. Traceability & Markdown Cleanliness Checklist

- [ ] `specnovel.py check` passes with 0 errors.
- [ ] All scene headings match the canonical `# CHP-xxx: Title` and `## SCN-xxx: Title` format.
- [ ] No visible raw `[[ID]]` tags remain in `manuscript/` prose.
- [ ] Word counts are within target bounds (`specnovel.py stats`).
