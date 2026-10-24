# SpecNovelist knowledge-base format (canonical reference)

Every SpecNovelist skill depends on this format, and `scripts/specnovel.py` parses it. The
**structural rules** are mandatory; the **field templates** are strong guidance.

## Project layout

```text
<novel>/
├── story/                      # HUMAN-OWNED INPUTS
│   ├── synopsis.md             # seed synopsis (never rewritten by agents without approval)
│   ├── brief.md                # interview decisions: premise, genre, length, POV, settings, rigor
│   └── style.md                # BINDING writing-style guide for the manuscript
├── kb/                         # KNOWLEDGE BASE (cataloged, cross-referenced)
│   ├── characters/             # CHR  one file per character:   CHR-001-elena-voss.md
│   ├── places/                 # PLC  one file per place:       PLC-002-hamburg-harbor.md
│   ├── organizations/          # ORG  one file per organization
│   ├── objects/                # OBJ  one file per significant object
│   ├── plot/                   # PLT  one file per plot element (thread, arc, mystery, secret)
│   ├── themes/                 # THM  themes.md (several entries per file is fine)
│   ├── world/                  # WLD  world rules for invented/speculative elements, by topic
│   ├── timeline/               # TML  timeline.md, entries in chronological order
│   ├── facts/                  # FCT  researched facts, grouped by topic: aviation-1910s.md
│   ├── sources/                # SRC  bibliography, grouped by topic or one bibliography.md
│   ├── research/               # RQ   questions.md - the research backlog
│   └── INDEX.md                # GENERATED catalog (specnovel.py index) - never edit
├── outline/                    # SKELETON in reading order (PRT > CHP > SCN)
├── abridged/                   # DERIVED condensed novel, one file per chapter: CHP-001.md
├── manuscript/                 # DERIVED final prose, one file per chapter: CHP-001.md
└── build/                      # compiled output (git-ignored)
```

## Structural rules

* **Definition = heading that starts with an ID**: `# CHR-001: Elena Voss`. Format `PREFIX-NNN`
  (uppercase prefix, dash, 3+ digits); separator `:`, `.`, `-`, `–` or `—`. Any heading level.
* **Extent**: an item's section runs until the next heading of the same or higher level, or the
  next ID heading of any level. Non-ID sub-headings (`## Background`) belong to the item.
* **Uniqueness and permanence**: IDs are unique across `story/`, `kb/` and `outline/`, are never
  renumbered, and are never reused, even after deletion (every ID in git history is retired).
  Always allocate with `python <toolkit>/scripts/specnovel.py next-id PREFIX`, and write the file
  before allocating the next one.
* **Identity = the same thing**: renaming a character keeps the ID (MODIFIED). Splitting one
  character into two keeps the ID for one and allocates a new ID for the other.
* **Cross-references**: `[[ID]]` or `[[ID|display text]]` (Obsidian-compatible). Every reference
  must resolve to a definition (`check` fails on dangling references). References inside fenced
  code blocks are ignored, so examples can live in fences.
* **Plain text elsewhere**: text that merely mentions an ID without `[[ ]]` is not a reference.
* **Derived layers** (`abridged/`, `manuscript/`) only define `CHP` and `SCN` headings that mirror
  the outline. They never define KB items.

## Prefix registry

| Prefix | Type | Lives in | Purpose |
|---|---|---|---|
| `CHR` | character | `kb/characters/` | People and other characters, fictional or real |
| `PLC` | place | `kb/places/` | Locations at any scale (city, house, ship, room) |
| `ORG` | organization | `kb/organizations/` | Institutions, factions, families, companies |
| `OBJ` | object | `kb/objects/` | Significant objects, documents, vehicles, technologies-as-props |
| `PLT` | plot element | `kb/plot/` | Main plot, subplots, character arcs, mysteries, secrets, setups/payoffs |
| `THM` | theme | `kb/themes/` | Themes and motifs |
| `WLD` | world rule | `kb/world/` | Invented or extrapolated rules (futuristic tech, alt-history premises, magic) |
| `TML` | timeline event | `kb/timeline/` | Dated events, historical and fictional, in chronological order |
| `FCT` | fact | `kb/facts/` | Researched, sourced facts (history, science, current events, daily life) |
| `SRC` | source | `kb/sources/` | Bibliographic records for every source consulted |
| `RQ`  | research question | `kb/research/` | Research backlog |
| `STY` | style rule | `story/style.md` | Optional IDs for important style rules |
| `PRT` / `CHP` / `SCN` | part / chapter / scene | `outline/` | Novel skeleton; see outline-format.md |

Additional prefixes are allowed (e.g. `LNG` for an invented language's lexicon); `check` reports
them as info so you notice typos.

## Field templates

Fields are bold-labelled bullet lines (`- **Field:** value`). Omit fields that don't apply; add
sub-headings for long content. Keep entries factual and reusable: they are what the writing
agents consult for continuity.

### Character (`CHR`)
```markdown
# CHR-001: Elena Voss
- **Role:** Protagonist; POV character
- **Historical:** fictional | real (claims about real people need [[FCT-...]] citations)
- **Aliases / forms of address:** "Lena" (family); "Dr. Voss"; "Fräulein Doktor" (staff)
- **Born / age:** 1884, Hamburg; 28 at story start ([[TML-001]])
- **Appearance:** height, build, hair, distinguishing marks, typical clothing
- **Voice:** speech patterns, vocabulary, verbal tics, languages and accents
- **Background:** education, family, formative events
- **Wants (external goal):**
- **Needs (internal):**
- **Flaw / wound:**
- **Arc:** from -> to; see [[PLT-002]]
- **Relationships:**
  - [[CHR-002]]: older brother; resentful protectiveness
- **Knowledge & secrets:** what they know, when they learn it, what they hide
- **Affiliations:** [[ORG-001]]
- **Continuity:** fixed details that must never drift (eye color, scars, injuries over time)
```

### Place (`PLC`)
```markdown
# PLC-002: Hamburg-America Line pier, Hamburg
- **Kind:** real | fictional | fictionalized (based on [[PLC-...]] / [[FCT-...]])
- **Within:** [[PLC-001]]
- **Period:** the era(s) in which the story uses it
- **Layout:** spatial facts that blocking depends on
- **Sensory palette:** sight, sound, smell, texture, temperature, light at different times
- **People typically present:**
- **Significance:** why it matters to the story
- **Facts:** [[FCT-004]], [[FCT-009]]
```

### Organization (`ORG`) and Object (`OBJ`)
```markdown
# ORG-001: Hamburg-Amerikanische Packetfahrt-Actien-Gesellschaft (HAPAG)
- **Kind:** real | fictional
- **Purpose / activity:**
- **Structure & key members:** [[CHR-005]]
- **Period details:** [[FCT-012]]
- **Role in story:**

# OBJ-001: The unsigned letter
- **Description:** physical details
- **Owner / location over time:** [[CHR-001]] until [[TML-006]], then [[CHR-003]]
- **Significance:** [[PLT-004]]
```

### Plot element (`PLT`)
```markdown
# PLT-001: Elena's search for her brother (main plot)
- **Time:** [[TML-002]] (1912-04-02 morning -> 1912-04-15 dawn)
- **Place:** [[PLC-001]], [[PLC-002]] (Hamburg harbor -> North Atlantic)
- **Prerequisites:** [[PLT-002]], [[FCT-001]] (causal requirements or conditions; checked in story DAG)
- **Kind:** main plot | subplot | character arc | mystery | secret | romance | setup/payoff
- **Dramatic question:** Will Elena find Karl before the ship sails?
- **Involves:** [[CHR-001]], [[CHR-002]], [[OBJ-001]]
- **Stakes:**
- **Movement:** setup -> complications -> crisis -> climax -> resolution (story-level summary)
- **Reveals / payoffs:** what the reader must learn, and roughly when
- **Themes:** [[THM-001]]
```
Where each beat lands is **not** stored here: `specnovel.py trace PLT-001` lists the scenes that
reference it in reading order. This avoids duplicated, drifting information.

> [!IMPORTANT]
> **Mandatory Time & Place Metadata**: Every `PLT` item MUST carry explicit `Time:` (or `When:`, `Span:`)
> and `Place:` (or `Where:`, `Setting:`) metadata. This is strictly verified by `specnovel.py check`.
> This metadata directly informs the `novel-write` skill so it can craft smooth, clear spatiotemporal
> transitions (establishing elapsed time, travel distances, setting shifts, and sensory grounding) to
> help the reader follow the flow of the story.

> [!IMPORTANT]
> **Story Causality**: When a `PLT` element specifies `Prerequisites:`, `specnovel.py dag` ensures that
> every scene advancing this plot element is preceded in the outline reading order by all of the plot
> element's prerequisites, and that the plot element has a causal path to the novel's root denouement.

### Theme (`THM`)
```markdown
## THM-001: Duty versus self-determination
- **Question explored:**
- **Motifs / symbols:** ships' bells, ledgers
- **Carried by:** [[CHR-001]], [[PLT-003]]
```

### World rule (`WLD`) - futuristic, alternate-history or invented elements
```markdown
## WLD-003: Orbital tethers carry freight, not people
- **Rule:** statement of how the world works
- **Scope:** where/when it applies
- **Basis:** [[FCT-021]], [[FCT-022]] (extrapolated) | invented (deliberate departure from fact)
- **Extrapolation:** how the present-day facts lead here (years, steps, assumptions)
- **Limits & costs:** what it cannot do; who pays
- **Consequences:** social, economic and sensory implications the prose can show
```
`check` warns when a world rule has no `Basis:` line.

### Timeline event (`TML`)
```markdown
## TML-004: 1912-04-14 23:40 - Titanic strikes an iceberg
- **Kind:** historical | story
- **Date precision:** exact | day | month | approximate
- **Involves:** [[CHR-003]]
- **Facts:** [[FCT-030]]
```
Keep `kb/timeline/timeline.md` in chronological order; the heading carries the date so the file
reads as a chronology.

### Fact (`FCT`) - created only by `novel-research`
```markdown
## FCT-030: Collision time
- **Statement:** One precise, checkable claim, in your own words.
- **Applies to:** period / place / scope; "as of 2026-10" for contemporary facts
- **Confidence:** high | medium | low | disputed
- **Sources:**
  - [[SRC-011]], p. 34: "short supporting quote or precise locator"
  - [[SRC-014]], §3
- **Variants / conflicts:** what other sources say and which one we follow, and why
- **Story use:** how the fact can surface in scenes (sensory, procedural, dialogue)
- **Liberty:** none | describe a deliberate deviation in the novel (feeds the author's note)
- **Answers:** [[RQ-007]]
```
`check` **fails** if a fact cites no `[[SRC-...]]`.

### Source (`SRC`)
```markdown
## SRC-011: United States Senate inquiry into the loss of the Titanic (1912)
- **Type:** primary | secondary | tertiary
- **Creator:** author / agency / witness
- **Publisher / repository:** archive, journal, publisher, website owner
- **Date:** publication or creation date
- **URL:** https://... (the exact page consulted)
- **Archived:** https://web.archive.org/... (if available)
- **Accessed:** 2026-10-23
- **Citation:** full Chicago-style citation (required when there is no URL, e.g. print books)
- **Reliability:** authority, proximity to events, known biases, corroboration
```
`check` fails if a source has neither a URL nor a Citation, and warns if a URL has no
`Accessed:` date or the `Type:` is missing.

### Research question (`RQ`)
```markdown
## RQ-007: When exactly did the collision happen, ship's time?
- **Status:** open | answered | dropped
- **Priority:** high (blocks outline) | medium (blocks drafting of a scene) | low (texture)
- **Needed for:** [[SCN-014]], [[CHR-003]]
- **Answer:** [[FCT-030]]
- **Notes:** search leads, archives to try
```
