# Analysis Guide: Metrics, Dimensions, and Editorial Interpretation

This guide provides the theoretical framework, metric definitions, craft thresholds, and diagnostic techniques used by `novel-analyze` to evaluate 9-stage SpecNovelist manuscripts.

---

## 1. Metric Classification Matrix

Metrics in SpecNovelist are categorized into two fundamental groups:

| Category | Primary Focus | Evaluated Against | Target Direction |
|---|---|---|---|
| **Raw Quality Indicators** | Narrative logic, plot coherence, syntax health, reader immersion | Objective storytelling rules & craft standards | Minimize flaws (target: 0 defects) |
| **Style-Reflective Metrics** | Voice, cadence, sensory depth, dialogue proportion, visual art | `setup/style.md` artistic mandate & novel consistency | Maintain alignment with aesthetic vision |

### Detailed Metric Breakdown

```
METRICS HIERARCHY
├── 1. Raw Quality Indicators
│   ├── Narrative Causality: Narrative DAG acyclicity, reachability to denouement (BET-NNN, ILL-NNN)
│   ├── Epistemic Integrity: Secrets revealed, learned by, kept hidden from
│   ├── Chekhov's Gun Matrix: Setup/payoff pairing, scene distance gap
│   ├── Pacing Momentum: Pacing sag sequences (consecutive low-progression scenes)
│   ├── Linguistic Hygiene: Passive voice ratio (≤ 5%), filter words, cliché count
│   └── Continuity Check: Physical traits, timeline travel, fact fidelity
│
└── 2. Style-Reflective Metrics
    ├── Sentence Cadence Entropy (H_cad): Variety in clause and sentence lengths
    ├── Average Sentence Length: Terse / staccato vs. balanced vs. periodic / lyrical
    ├── Dialogue Ratio: Percentage of dialogue words vs. total prose words
    ├── Sensory Palette Balance: Visual, Auditory, Tactile, Olfactory, Gustatory radar
    ├── Narrative Velocity (V_n): Narrative beats and arc turns per 1,000 words
    ├── Emotional Valence (E_v): Net emotional polarity score of scene beats
    └── Visual Illustration Intensity: Cataloged ILL-NNN assets vs. setup/style.md intensity guidelines
```

---

## 2. Style Alignment & Consistency Standards

### 2.1 Cadence Entropy ($H_{cad}$) & Sentence Rhythm
Prose rhythm is quantified using Shannon entropy across sentence length buckets:
- **Terse / Staccato**: 1–7 words (punchy, action, shock).
- **Short**: 8–15 words (direct statements, brisk dialogue beats).
- **Medium**: 16–28 words (standard narrative observation, exposition).
- **Periodic / Long**: $\ge 29$ words (atmospheric immersion, stream of consciousness, contemplative interiority).

Entropy formula:
$$H_{cad} = -\sum_{i} P(b_i) \log_2 P(b_i)$$
- **Diagnostic benchmarks**:
  - $H_{cad} < 1.8$ bits: **Monotone Cadence Risk**. Sentences cluster in a single length, creating a hypnotic, repetitive rhythm.
  - $1.8 \le H_{cad} \le 2.3$ bits: **Balanced / Calibrated Prose**. Healthy variation suitable for commercial and contemporary literary fiction.
  - $H_{cad} \ge 2.4$ bits: **Dynamic / Lyrical Prose**. High musicality, intercutting short dramatic beats with expansive lyrical sentences.

### 2.2 Cross-Chapter Style Consistency
An author's voice often fluctuates between writing sessions. The analysis engine detects cross-chapter drift by comparing:
- $\Delta \bar{L}_{sent}$: Average sentence length shift across chapters. Shifts greater than $\pm 5.0$ words suggest unconscious voice drift unless justified by POV change.
- $\Delta H_{cad}$: Cadence variety variance across chapters.
- $\Delta \text{Dlg}\%$: Dialogue ratio shifts. Large swings (e.g. Chapter 1 is 70% dialogue, Chapter 2 is 5% dialogue) flag potential pacing whiplash.

### 2.3 Sensory Palette Radar
Novels often succumb to "white-room syndrome" where characters speak in blank voids. The five sensory modalities must be calibrated to the setting:
- **Visual**: Sight, light, color, geometry.
- **Auditory**: Sound, rhythm, silence, resonance.
- **Tactile**: Texture, temperature, pressure, friction, pain.
- **Olfactory**: Scent, decay, perfume, smoke, damp.
- **Gustatory**: Taste, bitterness, salt, food, metal.

**Thresholds**:
- Any scene exceeding 300 words that records zero tactile or olfactory anchors is flagged with a **Sensory Grounding Alert**.
- Settings defined in `world/places/` (`PLC-NNN`) must have their sensory palette reflected in beats and scenes taking place there.

---

## 3. Multi-Level Zoom-In Protocols

When authoring or updating the analysis report, follow this zoom-in hierarchy:

### Level 1: Narrative Structure & Unified Narrative DAG (`narrative/`)
- Trace causal dependencies: does every beat (`BET-NNN`) advance towards the root denouement?
- Check for pacing sag sequences: any sequence of 2+ consecutive scenes exceeding 1,200 words without advancing a cataloged beat (`BET-NNN`) or story arc (`ARC-NNN`).

### Level 2: Physical Structure & Chapter Level (`structure/outline.md`)
- Compare chapter target word counts vs. actual word counts.
- Compare stylistic footprints across chapters to identify outliers in voice or tone.

### Level 3: Scene Level (`SCN-NNN`)
- Inspect Narrative Velocity ($V_n$):
  $$V_n = \frac{\text{Beat & Arc Advancements}}{\text{Scene Words} / 1000}$$
  - $V_n \ge 1.0$: High-velocity dramatic scene.
  - $V_n < 0.3$: Atmospheric breather, thematic mirror, or character reflection. Ensure an authorized `Function:` tag is present on the beat.
- Inspect Emotional Valence ($E_v$): Verify that emotional peaks and valleys produce a dynamic dramatic waveform rather than an emotionally flat narrative.

### Level 4: Paragraph & Sentence Level
- Zoom in on specific phrases using clickable file links (`[file#Lxx](file:///...)`).
- Clichés: Identify dead metaphors (e.g., "heart skipped a beat", "blood ran cold") and provide somatic alternatives that depict visceral physiological reactions.
- Passive constructions: Highlight passive sentence clusters and provide active transformations.

### Level 5: World Entities (`world/`)
- Screen-time distribution (`CHR-NNN`): Verify protagonist vs. secondary character representation.
- Place grounding (`PLC-NNN`): Cross-reference scene sensory details with location entries in `world/places/`.
- Researched facts (`FCT-NNN`): Verify historical and technical authenticity without data-dumping.

### Level 6: Illustrations & Directives (`narrative/illustrations.md`, `publishable/graphics/`, `directives/`)
- Verify that every illustration (`[[ILL-xxx]]`) placed in `structure/outline.md` adheres to the intensity level and visual trigger rules defined in `setup/style.md` > `## Graphics Guidelines`.
- Verify that all active `[[DIR-xxx]]` directives are honored in the prose.
