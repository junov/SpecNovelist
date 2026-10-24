# Knowledge-base quality checklist

Run this whenever you draft or review KB entries. Report findings as concrete, quotable
suggestions and never silently change the author's intent.

## Per entry
- [ ] Has a valid, unique, never-used ID from `next-id`, and a specific title.
- [ ] Lives in the folder for its type (see the prefix registry).
- [ ] Every `[[ID]]` resolves (`specnovel.py check`).
- [ ] Contains no unsourced real-world claims. Each one is either a `[[FCT-...]]` link or an
      open `[[RQ-...]]`.
- [ ] Characters: goal, need, flaw and arc are present for major characters; fixed physical
      details are recorded under **Continuity**; names fit the culture and era.
- [ ] Places: real vs fictional is declared; the sensory palette is concrete (not "bustling").
- [ ] World rules: have a **Basis** (facts or "invented"), and limits/costs as well as powers.
- [ ] Timeline: dates are consistent with character ages, travel times, and other `TML` entries.
- [ ] Plot elements: carry explicit, valid **Time** and **Place** metadata (e.g. `[[TML-...]]` or date/span, `[[PLC-...]]` or locations) to guide prose transitions; state dramatic question, stakes, reveals, and causality prerequisites.
- [ ] No duplicated information that already lives in another entry (link it instead).

## Per change (before accepting the plan)
- [ ] For each MODIFIED item, is it still the same thing? If it became something different,
      retire it and allocate a new ID.
- [ ] Does a REMOVED item leave dangling references or orphaned plot threads?
- [ ] Do ripple effects reach outline scenes? List them with `specnovel.py trace`.
- [ ] Do new open `RQ` items block anything already outlined?
- [ ] Is the change small enough to review? Suggest splitting large edits.

## Severity
- **BLOCKER**: breaks continuity or traceability (dangling reference, duplicate ID,
  missing PLT time/place metadata, contradiction with an established fact, unsourced fact).
- **WARNING**: likely to cause drift or weak scenes (missing continuity details, vague palette,
  rule without limits).
- **NIT**: consistency and style.
