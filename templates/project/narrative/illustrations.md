# Narrative Illustrations

<!--
STAGE 5: NARRATIVE STRUCTURE (narrative/illustrations.md).
At the Narrative Structure stage, illustrations (ILL-NNN) are textual specifications of illustrations,
not graphical image files. Actual graphical image files are rendered in Stage 9 (`publishable/graphics/ILL-NNN.png`).

Narrative DAG & Arc Rules for Illustrations:
1. Illustration nodes are first-class nodes in the Narrative DAG alongside beats (`BET-NNN`).
   - Do NOT use an "Associated Beats" field. Instead, relations between beats and illustrations are governed
     by DAG `Dependencies:` (`[[BET-NNN]]`, `[[ILL-NNN]]`):
     * An illustration can list earlier beats or illustrations in its `- **Dependencies:**` (meaning those
       beats/illustrations must precede this illustration in reading order).
     * Downstream beats or illustrations can list `[[ILL-NNN]]` in their `- **Dependencies:**` (connecting
       the illustration into the causal path toward the root denouement).
2. Like beats, every narrative illustration MUST be associated with at least one story arc via
   `- **Arcs:** [[ARC-NNN]]`, WITH THE EXCEPTION of illustrations used for book covers (`Type: cover`)
   or front/back matter (`Type: front-matter` | `back-matter` | `frontispiece` | `endpaper` | `colophon`,
   or `- **Placement:** cover | front-matter | back-matter`).

Fields:
- **Type:** `scene` | `map` | `diagram` | `portrait` | `epistolary` | `emblem` | `cover` | `front-matter` | `back-matter`
- **Arcs:** [[ARC-NNN]], ... (mandatory for all narrative illustrations; optional only for cover and front/back matter illustrations)
- **Dependencies:** [[BET-NNN]], [[ILL-NNN]], ... (or `None`; upstream Narrative DAG nodes that must precede this illustration)
- **Description:** Detailed textual specification of subject, composition, lighting, focal point, and mood.
- **Style:** Artistic or technical rendering medium (must align with `setup/style.md` > `## Graphics Guidelines`).
- **Depicts:** [[CHR-NNN]], [[PLC-NNN]], [[OBJ-NNN]], [[FCT-NNN]], ... (world entities shown in the illustration; drives sync invalidation when depicted entities change)
- **Caption:** Optional reader-facing caption text.
- **Has Text:** `true` | `false` (whether the image contains in-image text labels requiring localized `.png` variants per target locale)
- **Target:** `publishable/graphics/ILL-NNN.png` (destination path when rendered in Stage 9)
- **Directives:** [[DIR-NNN]], ... (cross-stage directives governing this illustration)

Example:
## ILL-001: Southampton Pier Approach Map
- **Type:** map
- **Arcs:** [[ARC-001]]
- **Dependencies:** [[BET-001]]
- **Description:** Period hydrographic chart of Southampton Water showing the steamer berth, railway terminus, and tender route.
- **Style:** Admiralty hydrographic survey cartography with fine black ink hatching and compass rose.
- **Depicts:** [[PLC-001]]
- **Caption:** Chart of Southampton Water and Tender Approaches, April 1912.
- **Has Text:** true
- **Target:** publishable/graphics/ILL-001.png
- **Directives:** [[DIR-001]]
-->
