<!--
CROSS-STAGE DIRECTIVES (directives/DIR-NNN.md).
Directives serve two essential roles:
1. Locking in freeform user feedback so that it continues to take effect whenever records are
   regenerated during synchronization.
2. DRY Factoring (Single Source of Truth): Factoring recurring special instructions, dialect rules,
   motif constraints, or formatting rules that apply across multiple records into a single directive
   referenced via [[DIR-NNN]].

Rules for Synchronization:
- All synchronization tasks, when updating records, MUST respect and preserve the directives
  associated with a given record (`- **Directives:** [[DIR-NNN]]`).
- When a synchronization task creates a new data record, it automatically links pre-existing
  directives that are specifically relevant to the new record (`specnovel.py directives link`).

Example:
# DIR-001: Telegram & Wireless Morse Formatting
- **Stage:** all
- **Scope:** [[OBJ-001]], prefix:SCN, prefix:BET
- **Locale:** all
- **Status:** active
- **Instruction:** Render all wireless telegrams in uppercase block quotes with "STOP" between clauses and omit quotation marks.
-->
