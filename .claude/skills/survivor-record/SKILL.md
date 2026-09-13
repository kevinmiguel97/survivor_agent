---
name: survivor-record
description: This skill should be used when the user confirms which team they're actually picking this week ("I'm going with the Chiefs", "lock in Buffalo"), asks to record/check this week's result ("did we win", "record the result", "check this week's result"), or reports a game result for a survivor pick ("the Chiefs won", "we lost, Denver blew it"). It fetches final scores itself rather than requiring the user to report win/loss, and automatically triggers a postgame review. Updates the persistent pool state in data/state.json.
version: 1.1.0
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

Use when the user asks to record/check this week's result, or reports whether their picked team won or lost. This skill fetches the actual result itself rather than relying on the user to report win/loss — that report is only used as a fallback or a conflict check.

1. **Identify the pending pick.** From `state_store.py show`, find the `picks[]` entry with `result == "pending"` (normally the `current_week` entry). If none exists, tell the user there's nothing pending to record.
2. **Fetch the week's actual matchup data:**
   ```
   .venv\Scripts\python.exe scripts\fetch_week_data.py --week <N> --season <season>
   ```
   Find the pending pick's team in `matchups[]` — it's the `home_team` or `away_team` of exactly one entry.
3. **If that matchup's `status` is `"scheduled"`** (not final yet): don't record anything. Tell the user plainly the game hasn't finished ("DET @ NO hasn't finished yet — check back after it's final"). **Exception**: if the user's message this turn is itself a specific, confident report of a final result (names the opponent and/or final score, not just "I think we lost"), you may proceed on their report alone — but say explicitly you're recording it from their report, not fetched data, since the feed can lag a real final by some hours.
4. **If `status` is `"final"`:** determine the outcome from `winner` — `"win"` if `winner` equals the picked team, `"loss"` if `winner` equals the opponent. If `winner` is `null` on a final game (a tie), stop and ask the user how to record it — `state_store.py` only accepts `win`/`loss`, don't guess.
5. **Conflict check.** If the user's message this turn also stated a result and it disagrees with what step 3/4 just determined, stop and surface the conflict explicitly — ask which to trust. Don't silently override either way.
6. **Record it:**
   ```
   .venv\Scripts\python.exe scripts\state_store.py record-result --week <N> --result <win|loss>
   ```
   This will fail with a clear error if no pick was recorded for that week yet — record the pick first if that happens.

   Effects of a `loss`:
   - `mistake_count` increments by 1.
   - If `status` was `alive`, it flips to `eliminated` (main-prize elimination). It never flips back to `alive` on a later win — once eliminated, the user is playing purely for the "fewest mistakes" consolation for the rest of the season, per the pool's rules.

   Either way, `current_week` advances past the recorded week.
7. **Automatically chain into `survivor-review`.** Immediately after a successful `record-result` call — do not wait for the user to separately ask for a review — invoke the `survivor-review` skill for the same week/season, passing them explicitly so it doesn't have to re-derive which week to review. Skipping this defeats the point of the learning loop: the user should never have to ask for it to run.

## After either operation

Show the user the resulting state (the CLI prints it), and briefly confirm what changed — e.g. "Recorded: Week 3 pick = BUF (home). Status: alive, 0 mistakes so far." or "Recorded: Week 5 loss (DEN). You're now eliminated from the main prize — mistake count is 2. I'll switch to picking for the fewest-mistakes strategy from here." After a result recording, fold `survivor-review`'s headline finding (Brier score / policy grade / new lessons) into this same reply rather than sending it separately.
