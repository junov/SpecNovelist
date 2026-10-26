# Analysis Report Template (Markdown Schema)

Use this schema when compiling or refining developmental editorial reports. Always format entity references as `[[ID]]` wiki-links.

---

```markdown
# Developmental Editorial & Style Analysis Report
**Work:** [[Title of Novel]]  
**Author:** Author Name  
**Locale:** `locale-tag`  
**Baseline Commit:** `commit-hash`  
**Generated:** YYYY-MM-DD HH:MM  

---

## 1. Executive Metrics Dashboard

| Metric | Dimension / Type | Observed Value | Standard / Style Target | Assessment |
|---|---|---|---|---|
| Total Word Count | Scope (Raw) | X wds | Y wds | On Budget / Review |
| Dialogue Ratio | Style-Reflective | X% | 25% – 45% (per `setup/style.md`) | Calibrated / Investigate |
| Cadence Entropy ($H_{cad}$) | Style-Reflective | X.X bits | ≥ 2.2 bits | Dynamic / Monotone |
| Avg Sentence Length | Style-Reflective | X.X words | per `setup/style.md` | Calibrated |
| Chekhov Guns Tracked | Dramatic (Raw) | X setups | 0 orphan setups | Healthy / Dormant |
| Pacing Sag Sequences | Dramatic (Raw) | X sequence(s) | 0 sags | Clean / Review Sags |
| Clichés / Dead Metaphors | Literary (Raw) | X detected | 0 clichés | Clean / Polish |
| Passive Voice Ratio | Linguistic (Raw) | X.X% | ≤ 5.0% | Punchy Active / Tighten |

---

## 2. Raw Quality Indicators Audit

Raw quality indicators measure objective storytelling integrity, narrative coherence, and technical craft faults that detract from immersion regardless of chosen style.

### 2.1 Narrative Causality & Epistemic Secrets
| Secret Element | Revelation Scene | Learned By | Kept Hidden From | Integrity |
|---|---|---|---|---|
| [[FCT-xxx]] / [[ARC-xxx]] | [[SCN-xxx]] | [[CHR-xxx]] | [[CHR-yyy]] | Preserved / Leaked |

### 2.2 Chekhov's Gun Setups & Payoffs
| Planted Entity | Setup Scene | Payoff Scene | Scene Gap | Diagnostic Assessment |
|---|---|---|---|---|
| [[OBJ-xxx]] | [[SCN-xxx]] | [[SCN-yyy]] | N scenes | Optimal / Dormant / Immediate |

### 2.3 Pacing Sags & Momentum Stalls
> [!WARNING]
> **Pacing Sag Detected in:** [[SCN-xxx]], [[SCN-yyy]]  
> Consecutive scenes exceeding target words without major beat or story arc movement.

### 2.4 Cliché & Passive Phrasing Hotspots
| Scene | Location | Flagged Cliché / Passive Phrase | Suggested Somatic Alternative |
|---|---|---|---|
| [[SCN-xxx]] | `file#Lxx` | *"phrase"* | Somatic suggestion |

---

## 3. Style-Reflective Metrics vs. `setup/style.md` Compliance

### 3.1 Sentence Rhythm & Prose Cadence (`setup/style.md` §3)
- **Observed Sentence Length:** X.X words per sentence.
- **Cadence Entropy ($H_{cad}$):** X.X bits.
- **Style Alignment:** Comparison against declared voice in `setup/style.md`.

### 3.2 Sensory Palette Grounding (`setup/style.md` §6)
| Sensory Modality | Occurrences | Percentage | Grounding Role |
|---|---|---|---|
| Visual | X | X% | Primary anchor |
| Auditory | X | X% | Atmosphere |
| Tactile | X | X% | Physical grounding |
| Olfactory | X | X% | Atmosphere / mood |
| Gustatory | X | X% | Flavor / texture |

### 3.3 Visual Illustration Intensity (`setup/style.md` ## Graphics Guidelines)
- **Cataloged Illustrations in Outline:** N assets ([[ILL-xxx]]).
- **Trigger Compliance:** Verification against spatial transitions, tactical diagrams, and cover art.

---

## 4. Cross-Chapter Style Consistency

| Chapter | Scenes | Words | Dialogue % | Avg Sentence | Cadence Entropy | Stylistic Footprint |
|---|---|---|---|---|---|---|
| [[CHP-001]] | N | X,XXX | X% | X.X wds | X.X bits | Balanced / Variance |

---

## 5. Multi-Level Zoom-In on Critical Areas

### 5.1 Scene Pacing Waveform & Emotional Arc
| Scene | Chapter | Words | Dlg % | Velocity ($V_n$) | Emotional Valence ($E_v$) | Focus |
|---|---|---|---|---|---|---|
| [[SCN-001]] | [[CHP-001]] | X,XXX | X% | X.X | +X.XX | Scene summary |

### 5.2 Character Agency & Screen-Time
| Character | POV Scenes | Cast Appearances | Novel Coverage | Agency Assessment |
|---|---|---|---|---|
| [[CHR-001]] (Name) | N | N | X% | Protagonist / Secondary |

---

## 6. Actionable Editorial Roadmap

1. **High Priority (Quality & Logic)**:
   - Specific Narrative DAG, epistemic, and pacing fixes.
2. **Medium Priority (Style & Sensory Polish)**:
   - Specific sensory enhancements and cliché replacements.
3. **Consistency & Rhythm**:
   - Cross-chapter cadence alignment and dialogue tuning.
```
