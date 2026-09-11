---
name: survivor-record
description: This skill should be used when the user confirms which team they're actually picking this week ("I'm going with the Chiefs", "lock in Buffalo"), or reports a game result for a survivor pick ("the Chiefs won", "we lost, Denver blew it"). Updates the persistent pool state in data/state.json.
version: 1.0.0
---

# NFL Survivor — Record Pick / Result

Writes to `data/state.json`, the single source of truth for used teams, results, pool status (`alive`/`eliminated`), and `mistake_count`. `survivor-pick` never writes state itself — this skill is the only thing that does.

There are two distinct events this skill handles. Figure out which one the user means from context.

## 1. Recording a confirmed pick (before the game is played)

Use when the user tells you which team they're actually going with this week (which may differ from the `survivor-pick` recommendation). Confirm the week, opponent, and home/away if not already obvious from the current week's matchups (`scripts\fetch_week_data.py`).

```
.venv\Scripts\python.exe scripts\state_store.py record-pick --week <N> --team <ABBR> --opponent <ABBR> --home-away <home|away> [--win-prob <0-1>]
```

This sets that week's `result` to `pending`. Re-running it for the same week (e.g. the user changes their mind before kickoff) safely overwrites the prior entry for that week — it does not create a duplicate.

## 2. Recording a result (after the game finishes)

Use when the user reports whether their picked team won or lost.

```
.venv\Scripts\python.exe scripts\state_store.py record-result --week <N> --result <win|loss>
```

This will fail with a clear error if no pick was recorded for that week yet — record the pick first if that happens.

Effects of a `loss`:
- `mistake_count` increments by 1.
- If `status` was `alive`, it flips to `eliminated` (main-prize elimination). It never flips back to `alive` on a later win — once eliminated, the user is playing purely for the "fewest mistakes" consolation for the rest of the season, per the pool's rules.

Either way, `current_week` advances past the recorded week.

## After either operation

Show the user the resulting state (the CLI prints it), and briefly confirm what changed — e.g. "Recorded: Week 3 pick = BUF (home). Status: alive, 0 mistakes so far." or "Recorded: Week 5 loss (DEN). You're now eliminated from the main prize — mistake count is 2. I'll switch to picking for the fewest-mistakes strategy from here."
