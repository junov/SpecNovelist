# Book Design & Publication Reference Guide

This reference provides technical specifications, typographic principles, and distributor requirements
for compiling and publishing SpecNovelist manuscripts into **EPUB** and **PDF** formats.

---

## 1. Page Geometry & Trim Sizes (PDF & Print)

Choosing the correct trim size depends on word count, genre, and physical distribution targets:

| Trim Size | Dimensions (Width x Height) | Common Usage / Genres | Typical Page Count Range |
|---|---|---|---|
| **5.0" x 8.0"** | 127 x 203 mm | Mass market paperbacks, novellas, literary fiction (compact) | 150 – 280 pages |
| **5.5" x 8.5"** *(Recommended)* | 140 x 216 mm | Standard trade fiction, mysteries, historical fiction | 250 – 420 pages |
| **6.0" x 9.0"** | 152 x 229 mm | Epic fantasy, science fiction, thrillers, hardcover editions | 350 – 650 pages |
| **A5** | 148 x 210 mm | International standard trade paperback (UK, Europe, Australia) | 220 – 400 pages |

### Gutter (Inner Margin) Calculation
The **inner margin** (or *gutter*) must account for the page curve and binding glue inside the spine.
As page count increases, the gutter margin must expand to ensure text does not vanish into the crease:

| Page Count | Recommended Inner Margin (Gutter) | Outer Margin | Top & Bottom Margins |
|---|---|---|---|
| **Up to 200 pages** | `0.65 in` (16.5 mm) | `0.50 in` (12.7 mm) | `0.70 in` (18 mm) |
| **200 – 350 pages** | `0.75 in` (19.0 mm) | `0.50 in` (12.7 mm) | `0.75 in` (19 mm) |
| **350 – 500 pages** | `0.85 in` (21.5 mm) | `0.55 in` (14.0 mm) | `0.75 in` (19 mm) |
| **Over 500 pages** | `0.95 in` (24.0 mm) | `0.60 in` (15.2 mm) | `0.80 in` (20 mm) |

---

## 2. Classical Book Typography

### Body Typeface Selection
Fiction interiors demand classical book serifs engineered for optical balance and sustained reading comfort:
- **EB Garamond / Adobe Garamond**: Classical 16th-century humanist serif. Elegant, open counters, highly legible. Outstanding for historical fiction and literary works.
- **Baskerville (Libre Baskerville)**: Transitional serif with high stroke contrast and crisp serifs. Excellent for mysteries, maritime stories, and period drama.
- **Caslon**: English Baroque typeface. Warm, sturdy, and dignified. Often described as the classic workhorse of publishing.
- **Minion Pro**: Modern digital book serif designed by Robert Slimbach. Extremely versatile, balanced x-height, compact width for higher word counts.

### Micro-Typographic Rules
- **Font Size & Leading**:
  - `10.5pt` / `14pt` leading (for compact or high-page-count volumes)
  - `11pt` / `15pt` leading (ideal for standard 5.5" x 8.5" trade paperbacks)
- **First-Line Indentation**:
  - Standard indentation: `1.25em` to `1.5em` (18pt).
  - **Flush-Left Rule**: The very first paragraph of a chapter, or the first paragraph following a scene break divider, must **never be indented** (`text-indent: 0`).
- **Scene Break Glyphs**:
  - Use a clean centered ornament: `* * *` (asterisms), printer's fleurons (`❦`), or geometric accents (`✦`).
  - Avoid excessive blank vertical space that could be mistaken for an accidental print defect.

---

## 3. EPUB Architecture & E-Reader Compatibility

### Semantic Architecture
SpecNovelist generates semantic HTML5 markup for EPUB:
- `<section class="chapter" epub:type="chapter">`
- Clean semantic headings `<h1>` and `<h2>`
- Descriptive `<figure>` and `<figcaption>` tags for interior artwork

### Dark Mode & Contrast Compliance
Many readers use inverted or night mode settings on OLED devices (Kindle Paperwhite, Kobo Clara, Apple Books).
- **Rule**: Never declare hardcoded background colors (`background-color: white`) or static dark text (`color: #000`) in `build/epub.css`.
- Use relative styling (`color: inherit; background-color: transparent;`) so the reader's operating system manages color inversion smoothly.

### Image Optimization Guidelines
- **Cover Image**: 1600 x 2560 pixels (standard 1:1.6 aspect ratio), 72–300 DPI, RGB color space, saved as baseline JPEG or PNG under 2MB.
- **Interior Figures**: Maximum width 1200 pixels, compressed to remain under 600KB per image. This prevents digital delivery surcharge penalties on distribution platforms like Amazon KDP.

---

## 4. Distributor Specifications

### Amazon KDP (Kindle Direct Publishing)
- **E-Book**:
  - Deliverable: Valid EPUB format (recommended over legacy MOBI/KPF).
  - Maximum package size: 650MB (though files under 50MB avoid high delivery cost deductions).
  - Cover: Required, minimum 1000px on longest side, 1600x2560 recommended.
- **Paperback (Print on Demand)**:
  - Deliverable: PDF with embedded fonts.
  - Trim size must match KDP dashboard choice (e.g. 5.5" x 8.5").
  - Gutter margin enforced based on page count.

### IngramSpark / Lightning Source
- **Print Interior**:
  - Deliverable: PDF/X-1a:2001 or PDF/X-3:2002 compliant.
  - All fonts strictly embedded (100% or subsets).
  - Minimum 0.5" margin on all outer edges; inner gutter according to page count.
  - Barcode and spine thickness calculated using paper stock (white vs. crème/cream).

### Apple Books & Kobo Writing Life
- Standard EPUB 3.0 file validation via `epubcheck`.
- Multi-level Table of Contents (`toc.ncx` and `nav.xhtml`) with functional chapter jumps.

---

## 5. Pre-Publication Checklist

Before distributing compiled books:
1. [ ] **Integrity Checks**: `python scripts/specnovel.py check` passes with 0 errors.
2. [ ] **AI Model Attributions**: `python scripts/specnovel.py models` confirms all models are acknowledged.
3. [ ] **Foreword / Preface**: Verified resolved if enabled in `story/config.md`.
4. [ ] **Glossary & Bibliography**: Verified injected and cleanly formatted in back matter.
5. [ ] **Verbatim Acknowledgements**: Confirmed present in `build/manuscript.md` and compiled EPUB/PDF.
6. [ ] **Visual Assets**: Cover art and interior graphics rendered, localized, and displayed crisply.
7. [ ] **TOC Navigation**: Chapter titles click through accurately without broken anchors.
