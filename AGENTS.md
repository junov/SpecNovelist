# SpecNovelist Agent Guidelines (Always Active)

This project operates on the **Spec-as-Source** paradigm adapted for fiction writing.
In this repository, **specifications written in Markdown are the source of truth**, while the
narrative drafts in `abridged/` and `manuscript/` are derived artifacts maintained and compiled
by AI writing agents.

---

## 1. Top-Level Folder Roles

- **`story/`**: **Human-Owned Inputs & Style Mandate.**
  - `config.md`: **The Project Configuration Specification.** Follows a strict Markdown schema containing Author Identity,
    target languages (with designated primary), optional foreword path, bibliography and glossary compilation toggles,
    and publication metadata.
  - `synopsis.md`: The seed synopsis. Never rewritten by agents without explicit author approval.
  - `brief.md`: Interview decisions: premise, genre, audience, length, POV, setting eras, research rigor.
  - `style.md`: **Binding writing-style guide** for the manuscript. Dictates voice, rhythm, POV, diction,
    dialogue conventions, interiority, glossary guidelines, graphics guidelines (`## Graphics Guidelines`),
    publication guidelines (`## Publication & Book Design Guidelines`), and locale-specific sections (`# Locale: <locale>`).
  - `acknowledgements.md`: **Mandatory Verbatim Acknowledgements.** Preserves credits, tool attributions, and
    mandatory disclosures for all AI models utilized by contributing agents, injected verbatim into compiled books.
  - `editorial/`: **The Editorial Feedback Database (`EDT-NNN.md`).** Records situational, scene-specific, or
    prose-level feedback that does not promote to top-level style/KB, tagged by target locale (`Locale: all` vs `Locale: fr-FR`).
- **`kb/`**: **The Knowledge Base (Story Bible & Fact Repository).**
  - Characters (`CHR`), Places (`PLC`), Organizations (`ORG`), Objects (`OBJ`), Plot Elements (`PLT`),
    Themes (`THM`), World Rules (`WLD`), Timeline Events (`TML`), Graphics (`GFX`), Glossary Entries (`GLS`),
    Researched Facts (`FCT`), Sources (`SRC`), and Research Questions (`RQ`).
  - Plot elements (`PLT`) must carry valid time and place metadata to orient spatiotemporal transitions.
  - Cataloged with unique, permanent IDs (`PREFIX-NNN`) and cross-referenced with `[[ID]]` wiki-links.
- **`graphics/`**: **Rendered Graphical Assets.**
  - Stores rendered images, diagrams, charts, maps, artwork, and book covers rendered by the `graphics` sync stage
    and embedded in `abridged/` and `manuscript/`. Multilingual assets are tagged by locale suffix (`GFX-xxx.<locale>.png`),
    falling back to primary or unlocalized assets when no text labels exist.
- **`outline/`**: **The Skeleton of the Novel in Reading Order.**
  - Parts (`PRT`), Chapters (`CHP`), and Scenes (`SCN`).
  - Sets up when, where, cast, plot movement, sourced facts, graphics references/placeholders (`[[GFX-xxx]]` or `[GFX: ...]`),
    goal/conflict/outcome, beats, key dialogue, and target word counts.
- **`abridged/`**: **Derived Intermediate Artifact (Condensed Novel).**
  - Contains **all plot elements** and **all important dialogues**, but with less descriptive texture
    than the final novel. One file per chapter (`CHP-001.md`).
- **`manuscript/`**: **Derived Final Artifact (Polished Prose).**
  - The final novel, rendered from `abridged/` + `story/style.md` + `kb/`. Clean, immersive prose with
    zero visible metadata. Organized in subdirectories by locale (`manuscript/<locale>/CHP-001.md`).
- **`build/`**: **Compiled Books.**
  - Generated compiled output in markdown, docx, epub, or pdf via `specnovel.py compile`, with auto-generated
    bibliographies and glossaries.

---

## 2. Core Operational Rules for Agents

1. **The Spec is the Source of Truth**:
   Never edit `abridged/` or `manuscript/` to alter plot events, character decisions, or historical facts
   without updating `story/`, `kb/`, or `outline/` first. If the author asks to change what happens,
   guide the author to update the specification (using `novel-author` or `novel-outline`), then
   synchronize downstream (using `novel-sync`).
2. **Permanent IDs & Traceability**:
   Every cataloged entity has a permanent, unique identifier (`PREFIX-NNN`, e.g. `CHR-001`, `PLC-002`,
   `FCT-030`, `SCN-014`).
   - IDs are never renumbered or reused, even after deletion.
   - Allocate new IDs exclusively via `python scripts/specnovel.py next-id <PREFIX>`.
   - Cross-references use `[[ID]]` or `[[ID|display text]]`.
3. **No Researched Facts Without Sources & Automated Placeholder Conversion**:
   Never record real-world claims (history, science, medicine, law, geography, current events) from
   memory or hallucination. Every fact (`FCT`) must cite at least one verified source record (`SRC`)
   that was actually read, with primary and authoritative sources prioritized. Story placeholders
   (`[...]`, `<...>`) must be converted into research questions (`RQ`) using automated tooling
   (`python scripts/specnovel.py placeholders --create-rq`) rather than manual entry.
4. **Intermediate Artifact Fidelity**:
   Never jump directly from the outline to the final manuscript. The abridged version (`abridged/`)
   must always be synthesized first to lock in plot causality and key dialogue.
5. **Style Guide Compliance**:
   `story/style.md` is a binding contract for `manuscript/`. Never revert to generic "AI smooth prose".
   Adhere strictly to the POV, tense, rhythm, and anti-patterns defined in `style.md`.
6. **Git-Native Parallel Synchronization**:
   Project baselines are tracked using `Novel-Sync:` Git commit trailers across seven decoupled stages
   (`brief`, `research`, `bible`, `outline`, `graphics`, `abridged`, `manuscript`). Use `specnovel.py`:
   - `python scripts/specnovel.py status`: Check catalog status, baseline drift, and scene coverage.
   - `python scripts/specnovel.py delta --stage <stage>`: Isolate changes in a specific input layer (e.g. `brief` for premise changes).
   - `python scripts/specnovel.py check`: Automated integrity checks (fails on dangling links, unsourced facts, misordered scenes, or DAG violations).
   - `python scripts/specnovel.py dag`: Validates story causality DAG (acyclicity, reading order coherence, denouement essentiality).
   - `python scripts/specnovel.py placeholders --create-rq`: Automatically converts placeholders across story specs into cataloged research questions (RQ).
   - `python scripts/specnovel.py impact --stage <graphics|abridged|manuscript>`: Identify assets or scenes that need (re)generation.
   - `python scripts/specnovel.py accept --stage <stage> [-m "<msg>"]`: Commit synchronized changes and advance stage baselines.
7. **Story Causality as a DAG & Reading Order Coherence**:
   Story causality is modeled as a Directed Acyclic Graph (DAG) rooted at the novel's final denouement:
   - Every scene and plot element identifies its prerequisites (`Prerequisites: [[ID]]`).
   - The novel's outline is a strict serialization of this DAG: every element in the outline must be preceded
     in reading order by all of its prerequisites.
   - A story's DAG admits multiple valid serialization orders; the chosen sequence is an artistic decision
     shaped by `story/style.md` and desired dramatic effects (suspense, cross-cutting, pacing cadence, dramatic irony).
   - The root of the DAG is the novel's final denouement (`- **Denouement:** true` or specified in `story/brief.md`).
   - Every element in the story must have a causal path leading to the root denouement (no dead-ends or inessential scenes).
   - Automated DAG tests (`python scripts/specnovel.py dag`) must be executed whenever the outline is touched.
8. **Editorial Feedback Triage & Persistence**:
   Direct author/editor feedback on drafts must first be evaluated for promotion into source material
   (`story/style.md` for voice/anti-patterns, `kb/` for character traits/facts, `outline/` for beats/dialogue).
   Feedback that is local, situational, or prose-specific is recorded in the editorial feedback database
   (`story/editorial/EDT-NNN.md`). Whenever intermediate or final drafts are re-rendered, all active directives
   targeting that scope must be ingested and satisfied, preventing editorial regression.
9. **Token-Optimized Graphics Asset Sync with Per-Asset Tracking**:
   Rendered graphics (maps, diagrams, character portraits, scene artwork, book covers) are generated
   from specifications in `kb/graphics/` (`GFX-NNN`) and stored in `/graphics`.
   - **Outline-Driven Graphic Placement**: The `novel-outline` skill is responsible for deciding where graphics
     are placed across chapters and scenes, guided by `story/style.md` > `## Graphics Guidelines` (intensity level,
     artistic and technical rendering styles, and visual triggers). Graphics placeholders (`[GFX: ...]`) and
     cataloged references (`[[GFX-xxx]]`) are embedded in the outline, explicitly linking them to the Story DAG.
   - **Story DAG Pruning (AI Token Saver)**: Only graphics entities referenced by the story DAG (in scenes
     or as story prerequisites) are rendered during sync. Inactive assets defined in KB are skipped with zero token consumption.
   - **Per-Asset Sync Tracking**: Sync baselines are recorded per asset via `Novel-GFX-Sync: GFX-NNN` trailers.
     When an asset is newly re-referenced in the story DAG, the engine inspects its per-asset baseline to report
     exactly how far out of sync it is (commits behind HEAD and which upstream prerequisites changed).

10. **Strict Project Configuration Compliance**:
    `story/config.md` is the project configuration source of truth and must conform to its strict schema.
    It defines Author Identity, target locales (with one designated primary), optional foreword file paths,
    compilation toggles (glossary, bibliography), and publication metadata. Any changes to supported
    locales or front/back matter must be declared in `config.md` and validated via `python scripts/specnovel.py check`.
11. **Multilingual Manuscript & Localized Graphics Compliance**:
    Manuscripts targeting multiple languages are organized in dedicated subdirectories: `manuscript/<locale>/CHP-NNN.md`.
    - Style guidelines provide locale-specific sections (`# Locale: <locale>`) for grammar, rhythm, and idioms.
    - Editorial feedback directives (`EDT-NNN.md`) specify their target locale (`Locale: all` or specific locale like `fr-FR`).
    - Graphics assets with text labels must provide localized versions suffixed with the locale (`GFX-NNN.<locale>.png`)
      or fallback cleanly to the primary/unlocalized version.
    - Automated checks (`python scripts/specnovel.py check`) enforce that manuscript files link to the correct localized
      graphics asset or valid fallback.
12. **DAG-Filtered Bibliography & Style-Guided Glossary**:
    - Bibliographical citations in compiled manuscripts are strictly generated from facts attached to the story DAG
      via `python scripts/specnovel.py bibliography`. Sources citing detached or pruned facts are excluded.
    - Glossary terms (`GLS`) are authored according to `## Glossary Guidelines` in `story/style.md`, refined
      via editorial directives, and automatically injected into compiled books when enabled in `story/config.md`.
13. **Mandatory AI Model Tracking & Verbatim Acknowledgements**:
    - An acknowledgements section is mandatory for every project and must be stored verbatim in `story/acknowledgements.md`.
    - Every AI model utilized by agents contributing to a work must be tracked via `Novel-Model:` Git commit trailers
      (recorded via `python scripts/specnovel.py accept --model <model>` or configured in `SPECNOVEL_MODEL` / `config.md`).
    - Automated checks (`python scripts/specnovel.py check` and `python scripts/specnovel.py models`) strictly verify that
      every contributing AI model is acknowledged in `story/acknowledgements.md`. Sync steps introducing unacknowledged models
      will fail validation until the acknowledgements file is updated.
    - During compilation (`python scripts/specnovel.py compile`), the text of `story/acknowledgements.md` is injected
      verbatim into the compiled deliverable book.
14. **Epistemic Integrity & Chekhov's Gun Setup/Payoff Engine**:
    - Scene specs track narrative knowledge (\Reveals:\, \Learns:\, \Hidden From:\) and Chekhov's guns (\Plants:\, \Pays off:\).
    - \python scripts/specnovel.py check\ enforces zero orphan plants, zero unearned payoffs, and blocks characters from acting on secrets hidden from them.
    - Scenes serving authorized artistic functions (\- **Function:** atmospheric-breather\, \	hematic-mirror\, \comic-relief\, \character-reflection\, \epistolary-interlude\, \pacing-breather\) satisfy causality without artificial mechanical plot prerequisite edges.
15. **Developmental Editorial Telemetry**:
    - \python scripts/specnovel.py audit\ analyzes whole-manuscript pacing waveforms, dialogue density, character agency/screen-time distribution, Chekhov gun distance gaps, and pacing sag sequences.
16. **Creative Flow, Scenario Exploration, and Versioned Scene Takes**:
    - **Prose Harvesting**: Authors can write unstructured prose bursts first; \python scripts/specnovel.py harvest <draft-file> --apply\ reverse-engineers characters, places, dialogue, and beats into KB, outline, and abridged drafts.
    - **Folder-Based Scenarios**: Exploratory what-if branches are stored under \story/scenarios/<name>/\ via \python scripts/specnovel.py scenario\.
    - **Versioned Scene Takes**: Multiple prose takes can be saved, diffed, and activated via \python scripts/specnovel.py takes\.

---

17. **Manual Pipeline Progression & Stage Isolation**:
    - Agents execute only the specific skill requested by the author.
    - Once a skill completes its task, the agent must conclude its turn without chaining into subsequent pipeline stages, without invoking next-stage skills, and without prompting or asking the author whether they want to proceed or advance to the next stage.
    - Pipeline and Journey Rail stage progression is strictly and manually controlled by the author in the UI.

## 3. Skill Dispatch Guide

| Skill | Primary Role | When to Activate |
|---|---|---|
| **`novel-init`** | Project Bootstrapper & Discovery Interview | When starting a new novel from a synopsis, conducting the guided discovery interview (calibrated to novice/intermediate/experienced writers), scaffolding the project, or generating the validated config, brief, style guide, and KB baseline. |
| **`novel-author`** | Story Bible & KB Authoring | When creating, editing, or reviewing characters (`CHR`), places (`PLC`), plot elements (`PLT`), themes (`THM`), world rules (`WLD`), timeline events (`TML`), graphics (`GFX`), or brief details. Never touches prose drafts. |
| **`novel-research`** | Sourced Online Fact Gathering | When researching historical, scientific, or current-events topics, answering research questions (`RQ`), finding primary sources, or verifying factual accuracy. Never creates facts without sources. |
| **`novel-outline`** | Structural Skeleton Builder | When creating, restructuring, or revising the novel's skeleton in reading order (parts, chapters, scenes), deciding graphics placement and embedding GFX references/placeholders, auditing pacing, or checking plot thread coverage. Never writes prose. |
| **`novel-abridge`** | Intermediate Draft Synthesizer | When synthesizing or updating the lean, condensed version of chapters in `abridged/` containing all plot elements and key dialogues with minimal description, embedding active graphics. |
| **`novel-write`** | Final Prose Rendering | When rendering final literary prose in `manuscript/` from `abridged/` + `story/style.md` + `kb/`. Enforces style, sensory grounding, graphics embedding, and anti-pattern bans. |
| **`novel-sync`** | Incremental Compilation Engine | When changes in `story/`, `kb/`, or `outline/` need to be compiled and synchronized into `graphics/`, `abridged/`, and `manuscript/`, running integrity checks and advancing git baselines. |
| **`novel-verify`** | Continuity & Quality Assurance | When auditing character physical continuity, timeline chronology, fact fidelity, or style guide compliance; triaging story defects; or detecting unauthorized draft drift. |
| **`novel-analyze`** | Developmental Editorial & Style Telemetry | When generating comprehensive analysis reports on literary, linguistic, and structural metrics; differentiating raw quality indicators from style-reflective metrics; auditing cross-chapter style consistency; and zooming in on plot, scene, paragraph, sentence, and KB elements with wiki-links. |
| **`novel-publish`** | Deliverable Book Publishing | When compiling, styling, and publishing the completed manuscript to distribution-ready EPUB, PDF, DOCX, or Markdown formats, applying interior book typography, cover artwork, and page geometry. |
