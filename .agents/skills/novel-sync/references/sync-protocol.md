# 9-Stage Synchronization Protocol Reference

## 1. Stage Dependency Order & Upstream Baselines

| Stage (`--stage`) | Directory | Upstream Stages Monitored | Git Trailer Recorded |
|---|---|---|---|
| `initial` | `initial/` | — (root stage) | `Novel-Sync: initial` |
| `setup` | `setup/` | `initial`, `directives` | `Novel-Sync: setup` |
| `research` | `research/` | `initial`, `setup`, `directives` | `Novel-Sync: research` |
| `world` | `world/` | `initial`, `setup`, `research`, `directives` | `Novel-Sync: world` |
| `narrative` | `narrative/` | `initial`, `setup`, `research`, `world`, `directives` | `Novel-Sync: narrative` |
| `structure` | `structure/` | `initial`, `setup`, `research`, `world`, `narrative`, `directives` | `Novel-Sync: structure` |
| `abridged` | `abridged/` | `initial`, `setup`, `research`, `world`, `narrative`, `structure`, `directives` | `Novel-Sync: abridged` |
| `manuscript` | `manuscript/` | `initial`, `setup`, `research`, `world`, `narrative`, `structure`, `abridged`, `directives` | `Novel-Sync: manuscript` |
| `publishable` | `publishable/` | All stages (`1..8`) + `directives` | `Novel-Sync: publishable` (+ `Novel-ILL-Sync: ILL-NNN`) |

## 2. Generation Gate Rule
`specnovel.py delta --stage <stage>` and `specnovel.py impact --stage <stage>` inspect Git history for `Novel-Sync: <stage>`. If no commit carries `Novel-Sync: <stage>`, synchronization is rejected with a Generation Gate error. Always run `novel-generate` for `<stage>` before running `novel-sync`.

## 3. Directives Lifecycle During Sync
1. **Preservation**: When updating a record, never remove `[[DIR-NNN]]` references that existed in the stage baseline. `specnovel.py check` compares current `[[DIR-NNN]]` references against the stage baseline and flags any dropped directives.
2. **Auto-Linking**: When a sync creates a new record (`CHR`, `PLC`, `BET`, `SCN`, etc.), `specnovel.py directives link --apply` (and `accept --stage <stage>`) inspects all active `directives/DIR-NNN.md` files and automatically appends `- **Directives:** [[DIR-NNN]]` whenever the new record's ID or referenced entities overlap the directive's `Scope:`.
3. **DRY Factoring**: Use `specnovel.py directives factor --title "..." --scope "..." --instruction "..." --targets <ID1> <ID2>` whenever a single instruction needs to govern multiple records across one or more stages.
