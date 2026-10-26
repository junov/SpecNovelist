<!--
STAGE 4: WORLD - Places & Settings (world/places/PLC-NNN.md).
Allocate IDs with `uv run python scripts/specnovel.py next-id PLC`.
Every narrative beat (`BET-NNN` in `narrative/beats.md`) MUST reference at least one `[[PLC-NNN]]` in its `Place:` field.

Fields:
- **Category:** `city` | `building` | `room` | `vessel` | `region` | `landmark`
- **Location / Parent:** Geographic coordinates or parent `[[PLC-NNN]]`.
- **Architecture & Layout:** Spatial geometry, entrances/exits, sightlines, and scale.
- **Sensory Palette:** Characteristic sights, sounds, smells, textures, and lighting conditions.
- **Facts:** [[FCT-NNN]] (optional historical/empirical grounding)
- **Directives:** [[DIR-NNN]] (optional)

Example:
# PLC-001: Southampton Berth 44 & White Star Dock
- **Category:** landmark
- **Architecture & Layout:** Covered passenger shed flanking the railway platform, gangways rising to the steamer's B-Deck doors.
- **Sensory Palette:** Coal smoke, salt brine, clatter of baggage trucks, gull cries, cold damp iron railings.
- **Facts:** [[FCT-001]]
-->
