---
name: novel-research
description: >-
  Performs online research for a SpecNovelist novel and records the results in the knowledge base
  as sourced facts (FCT) with bibliographic source records (SRC), resolving research questions
  (RQ). Use when the user asks to research a topic, verify a historical, scientific, legal,
  geographic or current-events detail, answer the research backlog, ground a futuristic world rule
  in present-day facts, or fact-check a scene. Prefers primary and authoritative sources, reads
  the actual pages, corroborates, records URL/citation, access date and reliability, and never
  records a fact without a source.
---

# Novel-Research

Fiction may invent people and plots, but the world it stands on must be true unless the author
deliberately decides otherwise. This skill gathers that truth from authoritative sources and
catalogs it so every scene can cite it.

* **Protocol and source hierarchy**: [research-protocol.md](references/research-protocol.md)
* **Entry formats** (`FCT`, `SRC`, `RQ`, `WLD`, `TML`): [kb-format.md](../novel-author/references/kb-format.md)
* **Helper**: `python <toolkit>/scripts/specnovel.py <command>`

## Workflow

### 1. Select the questions
- Default queue: open `RQ` items in `kb/research/questions.md`, high priority first
  (`specnovel.py check` lists open questions).
- Ad hoc requests: first create an `RQ` entry (`next-id RQ`) so the research is traceable.
- Read the `Needed for:` items to learn *what the story needs*: the date, the procedure, the
  sensory texture, the vocabulary. Research to that need, not to the whole topic.

### 2. Search and read
Use your web search and page-retrieval tools (or browser) following
[research-protocol.md](references/research-protocol.md):
- Work down the **source hierarchy**: primary sources first, then scholarly secondary sources,
  then reputable reference works. Use Wikipedia and similar only to find leads; follow their
  citations and cite the underlying sources instead.
- **Open and read the actual page or document** before citing it. Never cite from a search
  snippet, an AI summary, or memory.
- **Corroborate**: a key fact needs one authoritative primary source or two independent reliable
  secondary sources. Record disagreements instead of hiding them.
- Capture locators (page, section, timestamp, table) and a short supporting quote.

### 3. Record sources and facts
For each source actually consulted and relied upon:
- Reuse the existing `SRC` entry if the same document is already catalogued (search `kb/sources/`
  by URL and title); otherwise create one with `next-id SRC`, including `Type:`, `URL:`,
  `Accessed:` (today's date), `Citation:` and `Reliability:`. Add an `Archived:` link only if you
  have confirmed one exists.

For each finding:
- Create one `FCT` per atomic, checkable claim (`next-id FCT`) in the matching topic file under
  `kb/facts/`, citing `[[SRC-...]]` with locators. Set `Confidence:` honestly; use `disputed`
  with a `Variants / conflicts:` note where sources disagree.
- Add `Story use:` notes: concrete sensory, procedural, linguistic or economic details the prose
  can use (prices, smells, uniforms, slang, what a process looked like from the inside).
- Contemporary facts: add `Applies to: as of <date>` and mark volatile facts so they can be
  re-verified before publication.
- Futuristic settings: research the present-day state of the art and credible projections
  (agencies, peer-reviewed studies, expert roadmaps) as `FCT`s, then create or update `WLD` rules
  whose `Basis:` cites them and whose `Extrapolation:` explains the leap.
- Dated events: add or update `TML` entries in chronological order, citing the facts.

### 4. Connect and close
- Link new facts from the KB items that depend on them (place `Facts:` lines, character
  background, world-rule basis).
- Update each `RQ`: `Status: answered` with `Answer: [[FCT-...]]`, or keep it open with notes on
  what was tried, or `dropped` with the reason.
- Run `specnovel.py check` (every fact must cite a source; every source must have a URL or
  citation) and `specnovel.py index`.

### 5. Report and flag story conflicts
Summarize for the author: questions answered, key facts (with confidence), sources by type
(primary/secondary/tertiary), and questions still open. **Explicitly flag any finding that
contradicts the synopsis, brief, KB or outline** and offer options: change the story, keep it as a
documented `Liberty:` (for the author's note), or reframe the scene. The author decides; then hand
off to `novel-author` / `novel-outline` as needed.

Planning changes from research are accepted together with the rest of the plan:
`specnovel.py accept --stage plan -m "Research: <topic>"`.

## Rules
- **No source, no fact.** Never write an `FCT` without at least one `[[SRC-...]]` you actually read.
- **Never fabricate** URLs, titles, authors, quotes, page numbers or archive links. If you could not
  retrieve a page, say so and leave the `RQ` open.
- Prefer the most authoritative source available; record why a weaker one was used.
- Keep quotes short (a sentence or two) and use them only as evidence; facts are paraphrased.
- Do not edit `abridged/` or `manuscript/`; impacted scenes are reported by
  `specnovel.py impact` and handled by `novel-sync`.
