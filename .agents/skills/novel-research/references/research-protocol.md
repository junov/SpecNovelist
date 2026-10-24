# Research protocol

## Source hierarchy

Work from the top down. Use the highest tier that can answer the question, and record the tier
in each source's `Type:` field.

| Tier | `Type:` | Examples | Use |
|---|---|---|---|
| 1 | `primary` | Original documents and records: government and court records, legislation, censuses, ship manifests, official inquiry transcripts, contemporaneous newspapers, letters, diaries, memoirs and oral histories by participants, photographs and film, maps and plans of the period, museum objects and catalogues, patents, original scientific papers and datasets, official statistics, standards documents, company filings | Preferred for what happened, when, where, who, and what things looked like |
| 2 | `secondary` | Peer-reviewed scholarship, university-press books, review articles, museum and archive curatorial essays, official histories, reputable investigative journalism | Context, interpretation, synthesis; corroboration of primary material |
| 3 | `tertiary` | Established encyclopedias (Britannica, national biographies), textbooks, reputable reference sites | Orientation and quick corroboration only, never the sole source for a key fact |
| - | (lead only) | Wikipedia, fan wikis, blogs, forums, social media, AI-generated text, content farms | Never cited as evidence; mine their references for real sources |

### Where to look (non-exhaustive)
- **Digitized newspapers**: Library of Congress *Chronicling America*, Trove (National Library of
  Australia), Gallica (BnF), British Newspaper Archive, Delpher, Papers Past, Europeana Newspapers,
  Google News Archive.
- **Archives and libraries**: national archives (NARA, The National Archives UK, Library and
  Archives Canada, Bundesarchiv), HathiTrust, Internet Archive, Project Gutenberg (period texts),
  Europeana, Digital Public Library of America, university special collections.
- **Science and medicine**: peer-reviewed journals (via DOI), PubMed, arXiv (preprint, note
  status), NASA/ESA/NOAA/USGS and other agency sites, national academies' reports, IPCC reports.
- **Law and government**: official legislation databases, court opinions, parliamentary records
  (Hansard), government statistical agencies.
- **Language and daily life**: Oxford English Dictionary / Merriam-Webster first-use dates (for
  anachronism checks), period etiquette books, catalogues (e.g. mail-order catalogues), menus,
  price lists, timetables, period maps (David Rumsey Map Collection), weather records and almanacs
  (sunrise, moon phase, tides for exact dates).
- **Current events**: official statements and data first, then wire services and newspapers of
  record; note the date of every claim.

## Procedure per question

1. **Frame**: restate the question as the scene needs it, including place, date and precision
   ("What would a second-class passenger's cabin on a 1912 transatlantic liner contain?").
2. **Search** with several phrasings, including period terminology and other languages where the
   setting requires it.
3. **Retrieve and read** each candidate. Check: who created it, when, how close to the events,
   for what purpose, and whether it cites evidence.
4. **Extract** the claim with a precise locator and a short quote.
5. **Corroborate** (one authoritative primary source, or two independent reliable secondary
   sources) and note disagreements with their likely explanation (time zone, calendar,
   later revision, propaganda, faulty memory).
6. **Record** `SRC` then `FCT` entries per kb-format.md. One claim per fact.
7. **Mine texture**: note concrete details that bring scenes to life even if not asked for, as
   `Story use:` lines or extra low-priority facts.

## Special cases

- **Disputed history**: record each version as a variant with its sources; mark `Confidence:
  disputed`; the author chooses which version the novel follows (and it may become a `Liberty:`).
- **Real people**: be scrupulous; separate documented facts from inference; note privacy and
  defamation sensitivities for living people in the fact's `Story use:`.
- **Dates and calendars**: note Julian/Gregorian differences, time zones, and ship's time vs.
  local time where relevant.
- **Units and money**: record period units and values; add a modern equivalent only with a
  sourced conversion method.
- **Futuristic extrapolation**: cite current measurements and published projections (with their
  year and assumptions). The leap beyond them belongs in a `WLD` rule, not in an `FCT`.
- **Contemporary volatility**: facts about ongoing events, prices, laws or technology get
  `Applies to: as of <date>` and should be re-verified before the manuscript is final.
- **Paywalled or offline sources**: you may record a print source from a reliable bibliographic
  record (library catalogue, DOI landing page), but only cite claims you could actually verify; mark
  others as leads in the `RQ` notes.

## Report template (to the author)

```markdown
### Research report: <topic>
- Answered: RQ-007 -> FCT-030 (high), FCT-031 (medium)
- Still open: RQ-009 (no primary source found yet; tried X, Y)
- Sources added: SRC-011 (primary), SRC-014 (secondary)
- Story conflicts: FCT-030 says the ship sailed on the 10th; outline SCN-004 assumes the 12th.
  Options: (a) move SCN-004, (b) keep as documented liberty, (c) rewrite the beat.
- Texture highlights: ...
```
