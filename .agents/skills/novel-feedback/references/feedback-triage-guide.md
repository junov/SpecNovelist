# Feedback Triage & Directive Factoring Guide

## 1. Promote vs. Directive Decision Matrix

| Author Feedback Example | Upstream Edit | Directive (`DIR-NNN`) Created? |
|---|---|---|
| *"Make Dr. Vance left-handed and give her a scar on her wrist."* | Edit `world/characters/CHR-001.md` physical traits. | No (fits directly into `CHR-001` character spec). |
| *"Before the arrest happens, Elena has to discover the forged ledger at the harbor."* | Add `BET-005` in `narrative/beats.md` (`Place: [[PLC-002]]`, `Arcs: [[ARC-001]]`), add `[[BET-005]]` to `Dependencies:` of the arrest beat, and place `[[BET-005]]` in `structure/outline.md`. | No (pure Beat DAG + Physical Structure change). |
| *"In SCN-003, keep the pacing claustrophobic—use short fragments and never mention the sky."* | Link `[[DIR-001]]` on `SCN-003` in `structure/outline.md`. | **Yes**: Create `DIR-001` (`Scope: [[SCN-003]]`) so future `abridged` and `manuscript` syncs preserve this exact constraint. |
| *"Whenever members of the Harbor Syndicate (`ORG-002`) speak across the novel, they should use nautical idioms and avoid formal titles."* | Link `[[DIR-002]]` across `ORG-002` and all member `CHR-NNN` / `SCN-NNN` records. | **Yes (DRY Factoring)**: Run `specnovel.py directives factor --title "Harbor Syndicate Speech Register" --scope "[[ORG-002]]" --instruction "..." --targets ORG-002 CHR-004 CHR-005`. |
| *"In the French translation of Chapter 2, use 'tu' instead of 'vous' between the siblings."* | Link `[[DIR-003]]` on `CHP-002`. | **Yes**: Create `DIR-003` with `Locale: fr-FR` and `Scope: [[CHP-002]]`. |
