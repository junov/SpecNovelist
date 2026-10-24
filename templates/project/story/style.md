# Writing Style Guide

<!--
BINDING INPUT (human-owned). This file thoroughly describes how the final novel must read.
The novel-write skill reads ALL of it before rendering any scene of manuscript/ from abridged/,
and novel-verify audits the manuscript against it. Changing this file flags every rendered
scene for review (see `specnovel.py impact --stage manuscript`).

How to fill it in:
- Replace each "TBD" with concrete, checkable guidance. Prefer "Dialogue tags are 'said' or
  'asked'; no adverbs on tags" over "Dialogue should feel natural".
- Give examples: a short "do" and "don't" for each rule where possible.
- The novel-init interview can draft this file with you, or derive it from sample passages you
  admire (paste them under "Voice anchors").
- Optionally give important rules permanent IDs so audits can cite them, e.g. a heading
  "### STY-004: No adverbs on dialogue tags" (get IDs with `specnovel.py next-id STY`).
- Comments like this one are ignored when counting guidance words.
-->

## 1. Narrative stance

### Point of view
<!-- Person (first / second / third), distance (close, medium, distant, omniscient), single or
     rotating POV, rules for POV switches (only at scene breaks? chapter breaks?), head-hopping
     policy, whether the narrator knows the future. -->
TBD

### Tense
<!-- Past or present; handling of flashbacks (pluperfect for 1-2 sentences then simple past?);
     framing devices (letters, diary entries, transcripts). -->
TBD

### Narrator reliability and knowledge
<!-- Does the narrator ever lie, omit, or misread? How are dramatic irony and secrets handled? -->
TBD

## 2. Tone and mood
<!-- Overall tone (wry, elegiac, tense, warm...), how it varies by storyline or act, humor
     policy, how dark the book is allowed to get. -->
TBD

## 3. Prose rhythm and sentence craft
<!-- Typical sentence length and variation, use of fragments, long periodic sentences, paragraph
     length, white space, how action scenes vs reflective scenes differ in rhythm. Quantify where
     possible (e.g. "action paragraphs rarely exceed 3 sentences"). -->
TBD

## 4. Diction and vocabulary
<!-- Register (plain, lyrical, ornate, clipped), reading level, period-appropriate vocabulary and
     the anachronism policy (narration vs dialogue), technical jargon, invented terms for
     futuristic settings and how they are introduced, foreign-language words (italicized or not,
     translated or not), profanity level, words/phrases that are forbidden. -->
TBD

## 5. Dialogue
<!-- Tag policy ("said"/"asked" only? action beats instead of tags?), adverbs, punctuation of
     interruptions and trailing off, rendering of accent/dialect (light touch vs phonetic),
     period speech patterns and forms of address, how much small talk, subtext expectations,
     maximum length of a monologue, how phones/letters/telegrams/messages are formatted. -->
TBD

## 6. Description and sensory detail
<!-- Density of description, which senses to favor, how settings are introduced (on arrival, in
     motion, through the POV character's concerns), metaphor and simile policy (frequency, and
     drawing figurative language from the POV character's own world and era), weather and
     landscape, how much physical description of characters and when. -->
TBD

## 7. Interiority
<!-- Free indirect discourse vs tagged thought, italics for direct thought or not, how emotions
     are conveyed (shown through body and action vs named), depth of introspection. -->
TBD

## 8. Scene and chapter construction
<!-- How scenes open (in medias res, establishing beat, line of dialogue), how they end (hook,
     resonant image, mid-action), transitions and time jumps, scene-break convention, chapter
     length range, chapter openings/endings, epigraphs, chapter titles (yes/no, style). -->
TBD

## 9. Exposition and research delivery
<!-- How researched facts enter the prose: filtered through what the POV character would notice
     and know; no lectures; maximum exposition per page; how to handle facts the character could
     not know; how technical or historical detail is balanced against momentum; how speculative
     world rules are revealed. -->
TBD

## 10. Content boundaries and sensitivity
<!-- On-page vs off-page violence and sex, language, depiction of real people, historical
     prejudice in dialogue vs narration, cultural representation and sensitivity-read notes. -->
TBD

## 11. Mechanics and typography
<!-- Spelling variant (US/UK/CA/AU), punctuation (Oxford comma, em dash spacing, quotation mark
     style, single vs double quotes), numbers (spelled out up to?), dates and times, italics usage,
     capitalization of titles/ranks, abbreviations, how emphasis is shown. -->
TBD

## 12. Per-POV or per-storyline variations
<!-- If the voice shifts by POV character or timeline, describe each variant's differences from
     the baseline above (vocabulary, rhythm, preoccupations, verbal tics). -->
TBD

## 13. Touchstones
<!-- Authors and books whose style this novel should evoke, and specifically WHAT to borrow from
     each (e.g. "Hilary Mantel: present-tense close third, wry interiority; NOT her sentence
     length"). -->
TBD

## 14. Anti-patterns (never do this)
<!-- Banned clichés and stock phrases, purple-prose tics, filter words to avoid ("she saw",
     "he felt"), overused gestures (sighing, nodding, eyebrow raising), generic AI-isms
     ("tapestry", "a testament to", "couldn't help but", "let out a breath she didn't know she
     was holding", "in that moment", tidy moralizing endings), modern idioms in historical
     dialogue. List them explicitly. -->
TBD

## 15. Voice anchors
<!-- 2-5 sample passages (yours or quoted with attribution, kept short) that exemplify the target
     voice, each followed by a note on which features to imitate. These are the strongest
     signal for the writing agent. -->
TBD

## Glossary Guidelines
<!-- Criteria for terms automatically candidate-selected for the glossary:
     - Specialized nautical, medical, military, or historical technical jargon
     - Dialect terms, colloquialisms, or foreign loanwords not translated inline
     - Invented world-building objects or cultural practices
     - Rules for definition length and style (concise, accessible, spoiler-free) -->
TBD

## Graphics Guidelines
<!-- 
Binding guidance for the novel-outline, novel-author, and graphics sync stages on when, where, 
and how graphical assets (GFX) should be used, rendered, and embedded.
-->

### Intensity and Frequency
<!-- 
Controls the overall density and frequency of graphics across the novel:
- Parameter choices:
  - 'none': Pure text only; zero graphics.
  - 'minimal': Sparingly (1–3 major assets book-wide, e.g. frontispiece / world map / climactic schematic).
  - 'selective' (recommended default): Moderate (e.g. 1 per part or major multi-chapter arc; key maps, pivotal schematics, or chapter opening vignettes).
  - 'rich' / 'frequent': Visual immersion (illustrated novel; maps for every journey, schematics for complex mechanisms, portraits for cast, chapter headers).
Target asset budget: e.g. 1 per Part, maximum 6-8 across book.
-->
- **Intensity:** selective
- **Target Budget:** 1 per part, maximum 6-8 across book

### Rendering Styles

#### Artistic Rendering Style
<!-- 
Governs emotional and narrative art: covers, character portraits, landscape vistas, chapter header vignettes, and dramatic scene illustrations:
- Medium / Technique: e.g. Pen-and-ink cross-hatching, woodcut / steel engraving, charcoal chiaroscuro, graphite sketch, watercolor wash, vintage lithograph, or cinematic concept art.
- Lighting & Tone: e.g. High-contrast chiaroscuro, stark industrial shadows, atmospheric fog, period-accurate Edwardian illustration aesthetic.
- Color & Palette: Monochromatic (black ink on off-white parchment / cream paper for print/e-reader fidelity) vs. muted sepia vs. full-color digital.
-->
- **Medium:** Pen-and-ink with fine cross-hatching and linework (period 1910s editorial engraving style)
- **Palette:** Monochromatic black ink on aged cream / off-white paper (e-ink and print friendly)
- **Tone:** Atmospheric, high shadow contrast, somber realism

#### Technical Rendering Style
<!-- 
Governs informative, spatial, and mechanical visualizations: maps, charts, architectural plans, ship cutaways, tactical battle plots, and schematics:
- Drafting Aesthetic: e.g. Admiralty hydrographic survey cartography, vintage cyanotype blueprint, patent application line drafting, or clean modern vector schematic.
- Linework & Precision: Crisp vector linework, hatching for landmasses/bulkheads, compass roses, scale bars with nautical miles/metric scales.
- Typography & Callouts: Period-appropriate typography (e.g. Caslon or Baskerville serif for maps; technical monospaced/drafting sans-serif for blueprints); callout leaders and numeric keys.
-->
- **Medium:** Admiralty hydrographic survey cartography and period engineering patent drafting
- **Palette:** Crisp black linework with subtle stippling and contour hatching
- **Typography:** Serif cartographic labels, compass rose, soundings in fathoms, scale bar in nautical miles

### Usage Rules and Triggers

#### When to Use Graphics (Triggers)
<!--
Rules governing WHEN the novel-outline skill must place graphics in chapters and scenes:
- Spatial & Geographic Transitions: When a new city, archipelago, harbor, fortress, or journey route is introduced where spatial layout clarifies plot movement.
- Mechanical / Technical Complexity (The Friction Principle): When prose explanation of a technical apparatus (e.g. wireless Marconi apparatus, engine room boiler routing, orbital tether airlock) would bog down narrative pacing or cause spatial confusion.
- Structural Pivots: Part openers, major chapter transitions, or pivotal tactical confrontations.
- In-World Epistolary Artifacts: Facsimiles of crucial letters, decoded telegrams, nautical manifests, or newspaper clippings.
-->
- Introduce a nautical chart or map whenever the POV enters a new navigational territory or tactical body of water.
- Introduce an architectural cutaway or schematic when physical deck layout or machinery operation is critical to scene stakes.
- Introduce an in-world document facsimile when an encrypted message or official document is examined as a primary plot clue.

#### When NOT to Use Graphics (Negative Rules)
<!--
- Decorative Clutter: Do not add illustrations purely for decorative filler that does not advance spatial or dramatic comprehension.
- Talking Heads: Never illustrate standard two-person dialogue scenes.
- Spoiler Prevention: Never place a graphic that visually reveals a plot twist, secret identity, or hidden room before the reader reaches the text reveal.
- Ambiguity Protection: Do not illustrate moments intended to remain ambiguous, interior, or psychologically subjective (e.g. supernatural dread or internal grief).
-->
- Avoid illustrating conversational dialogue or character emotional reactions (let the prose carry interiority).
- Never depict an object or location before the POV character discovers it.
- Never use modern digital UI styles or computer-generated 3D aesthetics in historical fiction.

### Additional Specifications

#### Placement and Layout
<!-- 
Conventions for where graphics sit relative to prose:
- Front / Back matter plates: Full-page overview map in front matter; glossary diagrams in back matter.
- Chapter headers: 16:9 banner or 1:1 vignette immediately below chapter title before opening prose.
- In-scene inline figures: Centered full-width break between scene beats with figure caption below.
-->
- **Placement:** Chapter opening header for geographic maps; inline between scene beats for tactical schematics and in-world artifacts.

#### Aspect Ratio and Dimensions
<!-- 
Standardized dimensions for visual consistency across rendering:
- Landscapes / Maps: 16:9 or 3:2 landscape orientation.
- Vignettes & Portraits: 1:1 square or 4:5 portrait.
- Full Plates: 2:3 book-page ratio (e.g. 1200x1800 px).
-->
- **Aspect Ratio:** 16:9 for cartography and landscape plates; 1:1 for chapter header vignettes.

#### Text Labeling and Localization Policy
<!-- 
Policy for handling text within graphics:
- Text-minimal preference: Favor numeric/alphabetical callout keys (e.g. 1, 2, 3) with full descriptions in prose captions, allowing graphics to be language-agnostic across locales.
- Localized variants: When graphics contain translated text labels (e.g. place names on maps), generate localized assets (GFX-xxx.<locale>.png) matching the language of each manuscript subdirectory.
-->
- **Policy:** Text-minimal where feasible. For cartographic maps with place names, provide localized assets with translated place names according to target locales.

#### Visual Continuity and Symbol Library
<!-- 
Ensures visual cohesion across multiple assets:
- Consistent cartographic symbols (depth soundings, lighthouses, anchorages, compass rose).
- Consistent character likeness and garment details matching CHR continuity specs across portrait or scene assets.
-->
- **Continuity:** Maintain identical nautical symbol keys, compass rose designs, and line-weight hierarchy across all map assets.

## Publication & Book Design Guidelines
<!-- 
Parameters, editorial conventions, and artistic choices governing the compilation and publishing
of the novel into EPUB, PDF, and print deliverables via the novel-publish skill.
-->

### Format and Delivery Targets
<!-- 
Deliverables to produce upon publication:
- Formats: epub, pdf (also docx, md)
- Cover Asset: Path to cover art image (e.g. graphics/cover.png or [[GFX-001]])
-->
- **Formats:** epub, pdf
- **Cover Asset:** graphics/cover.png

### Page Layout & Trim Size (PDF & Print)
<!-- 
Page geometry and margins for print-on-demand (POD) and reading editions:
- Trim Size:
  - 5in x 8in (compact novella / mass market)
  - 5.5in x 8.5in (recommended standard trade paperback)
  - 6in x 9in (popular trade paperback / hardcover)
  - A5 (148mm x 210mm international standard)
- Margins:
  - Inner / Gutter Margin: 0.75in (19mm) - accommodates page binding thickness
  - Outer Margin: 0.5in (12.7mm)
  - Top Margin: 0.75in (19mm)
  - Bottom Margin: 0.75in (19mm)
- Chapter Openings:
  - 'recto': Chapters always start on right-hand page (standard trade publishing)
  - 'next': Chapters start on next page regardless of left/right
- Running Headers:
  - 'recto-verso': Author on left/verso, book title or chapter on right/recto
  - 'none': Suppress running headers
-->
- **Trim Size:** 5.5in x 8.5in
- **Inner Margin:** 0.75in
- **Outer Margin:** 0.5in
- **Top Margin:** 0.75in
- **Bottom Margin:** 0.75in
- **Chapter Openings:** recto
- **Running Headers:** recto-verso

### Interior Typography & Typesetting
<!-- 
Typeface selection, hierarchy, and micro-typography:
- Body Font: Classical book serif (e.g. EB Garamond, Baskerville, Caslon, Minion Pro, Sabon)
- Heading Font: Elegant display serif or clean titling sans (e.g. Cinzel, Playfair Display, EB Garamond)
- Font Size: 10.5pt or 11pt (standard trade book reading density)
- Line Height: 1.35 to 1.4 ratio (14pt to 15pt leading)
- Paragraph Indent: 1.25em (first-line indent for narrative prose)
- Scene Break Ornament: Divider glyph between scene beats (e.g. '* * *', '❦', '✦', or '---')
- Drop Caps: true (2-line or 3-line initial cap at chapter opening)
- Justification: true (fully justified prose)
- Hyphenation: true (automatic hyphenation for even word spacing in print/PDF)
-->
- **Body Font:** EB Garamond
- **Heading Font:** Cinzel
- **Font Size:** 11pt
- **Line Height:** 1.35
- **Paragraph Indent:** 1.25em
- **Scene Break:** * * *
- **Drop Caps:** true
- **Justification:** true
- **Hyphenation:** true

### EPUB & E-Reader Specifications
<!-- 
Formatting parameters specific to digital reading devices (Kindle, Kobo, Apple Books):
- Reflowable: true (dynamic reflowable layout conforming to reader font sizing)
- TOC Depth: 2 (Parts + Chapters in navigation; scene headings omitted from reader TOC)
- Dark Mode Support: true (semantic CSS variables, no hardcoded background colors)
- Max Image Width: 1200px (balanced resolution vs distributor file size caps)
-->
- **Reflowable:** true
- **TOC Depth:** 2
- **Dark Mode Support:** true
- **Max Image Width:** 1200px

### Editorial Front & Back Matter Sequence
<!-- 
Canonical running order for the published volume:
Front Matter:
  1. Half-title page
  2. Frontispiece plate
  3. Title page
  4. Copyright page
  5. Dedication / Epigraph
  6. Table of Contents
  7. Foreword (if enabled)
Body:
  - Parts and Chapters in reading order
Back Matter:
  1. Historical Note / Author's Note
  2. Glossary (if enabled)
  3. Bibliography (DAG-filtered facts, if enabled)
  4. Acknowledgements (verbatim from acknowledgements.md)
  5. About the Author & Colophon
-->

# Locale: en-US
<!-- Specific conventions for en-US:
     - American English spelling and punctuation (serial commas, double quotes)
     - Dialogue conventions (em dashes, tag punctuation)
     - Handling of non-English terms in dialogue vs prose -->
TBD
