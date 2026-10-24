# SpecNovelist Agent Guidelines (Always Active)

This project operates on the **Spec-as-Source** paradigm adapted for fiction writing.
In this repository, **specifications written in Markdown are the source of truth**, while the
narrative drafts in `abridged/` and `manuscript/` are derived artifacts maintained and compiled
by AI writing agents.

---

## 1. Top-Level Folder Roles

- **`story/`**: **Human-Owned Inputs & Style Mandate.**
  - `synopsis.md`: The seed synopsis. Never rewritten by agents without explicit author approval.
  - `brief.md`: Interview decisions: premise, genre, audience, length, POV, setting eras, research rigor.
  - `style.md`: **Binding writing-style guide** for the manuscript. Dictates voice, rhythm, POV, diction,
    dialogue conventions, interiority, and anti-patterns.
  - `editorial/`: **The Editorial Feedback Database (`EDT-NNN.md`).** Records situational, scene-specific, or
    prose-level feedback that does not promote to top-level style/KB, ensuring it persists and is re-applied
    whenever artifacts are re-rendered.
- **`kb/`**: **The Knowledge Base (Story Bible & Fact Repository).**
  - Characters (`CHR`), Places (`PLC`), Organizations (`ORG`), Objects (`OBJ`), Plot Elements (`PLT`),
    Themes (`THM`), World Rules (`WLD`), Timeline Events (`TML`), Researched Facts (`FCT`), Sources (`SRC`),
    and Research Questions (`RQ`).
  - Plot elements (`PLT`) must carry valid time and place metadata to orient spatiotemporal transitions.
  - Cataloged with unique, permanent IDs (`PREFIX-NNN`) and cross-referenced with `[[ID]]` wiki-links.
- **`outline/`**: **The Skeleton of the Novel in Reading Order.**
  - Parts (`PRT`), Chapters (`CHP`), and Scenes (`SCN`).
  - Sets up when, where, cast, plot movement, sourced facts, goal/conflict/outcome, beats, key dialogue,
    and target word counts.
- **`abridged/`**: **Derived Intermediate Artifact (Condensed Novel).**
  - Contains **all plot elements** and **all important dialogues**, but with less descriptive texture
    than the final novel. One file per chapter (`CHP-001.md`).
- **`manuscript/`**: **Derived Final Artifact (Polished Prose).**
  - The final novel, rendered from `abridged/` + `story/style.md` + `kb/`. Clean, immersive prose with
    zero visible metadata. One file per chapter (`CHP-001.md`).
- **`build/`**: **Compiled Books.**
  - Generated compiled output in markdown, docx, epub, or pdf via `specnovel.py compile`.

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
6. **Git-Native Synchronization**:
   Project baselines are tracked using `Novel-Sync:` Git commit trailers. Use `specnovel.py`:
   - `python scripts/specnovel.py status`: Check catalog status, scene coverage, and un-synced drift.
   - `python scripts/specnovel.py check`: Automated integrity checks (fails on dangling links, unsourced facts, misordered scenes, or DAG violations).
   - `python scripts/specnovel.py dag`: Validates story causality DAG (acyclicity, reading order coherence, denouement essentiality).
   - `python scripts/specnovel.py placeholders --create-rq`: Automatically converts placeholders across story specs into cataloged research questions (RQ).
   - `python scripts/specnovel.py impact --stage <abridged|manuscript>`: Identify scenes that need (re)generation.
   - `python scripts/specnovel.py accept --stage <stage> -m "<msg>"`: Commit synchronized changes.
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

---

## 3. Skill Dispatch Guide

| Skill | Primary Role | When to Activate |
|---|---|---|
| **`novel-init`** | Project Bootstrapper & Discovery Interview | When starting a new novel from a synopsis, conducting the guided discovery interview, scaffolding the project, or drafting the initial brief, style guide, and KB baseline. |
| **`novel-author`** | Story Bible & KB Authoring | When creating, editing, or reviewing characters (`CHR`), places (`PLC`), plot elements (`PLT`), themes (`THM`), world rules (`WLD`), timeline events (`TML`), or brief details. Never touches prose drafts. |
| **`novel-research`** | Sourced Online Fact Gathering | When researching historical, scientific, or current-events topics, answering research questions (`RQ`), finding primary sources, or verifying factual accuracy. Never creates facts without sources. |
| **`novel-outline`** | Structural Skeleton Builder | When creating, restructuring, or revising the novel's skeleton in reading order (parts, chapters, scenes), auditing pacing, or checking plot thread coverage. Never writes prose. |
| **`novel-abridge`** | Intermediate Draft Synthesizer | When synthesizing or updating the lean, condensed version of chapters in `abridged/` containing all plot elements and key dialogues with minimal description. |
| **`novel-write`** | Final Prose Rendering | When rendering final literary prose in `manuscript/` from `abridged/` + `story/style.md` + `kb/`. Enforces style, sensory grounding, and anti-pattern bans. |
| **`novel-sync`** | Incremental Compilation Engine | When changes in `story/`, `kb/`, or `outline/` need to be compiled and synchronized into `abridged/` and `manuscript/`, running integrity checks and advancing git baselines. |
| **`novel-verify`** | Continuity & Quality Assurance | When auditing character physical continuity, timeline chronology, fact fidelity, or style guide compliance; triaging story defects; or detecting unauthorized draft drift. |
