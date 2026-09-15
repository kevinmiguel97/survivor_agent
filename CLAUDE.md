# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An NFL survivor-pool assistant for a private/office pool. Pool rules: pick one team per week, each team usable only once all season, one loss eliminates you from the main prize; after elimination the user keeps picking every remaining week (no team reuse) to minimize total losses for a "fewest mistakes" consolation prize. See `README.md` for the full rules writeup.

The assistant is four Claude Code skills (`.claude/skills/`) backed by small Python scripts — there is no app server, build step, test suite, or linter in this repo.

## Commands

Dependencies live in a project-local venv, never installed globally:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install pandas numpy appdirs fastparquet
.venv\Scripts\python.exe -m pip install --no-deps nfl_data_py==0.3.3
```
(`nfl_data_py` pins `pandas<2.0`/`numpy<2.0`, which have no prebuilt wheels for modern Python — install modern pandas/numpy first, then add `nfl_data_py` with `--no-deps` so its broken pin doesn't force a source build.)

Initialize pool state once per season:
```powershell
.venv\Scripts\python.exe scripts\state_store.py init --season 2026
```

Manually inspect/drive state and data (normally the skills do this, but useful for debugging):
```powershell
.venv\Scripts\python.exe scripts\state_store.py show
.venv\Scripts\python.exe scripts\state_store.py record-pick --week <N> --team <ABBR> --opponent <ABBR> --home-away <home|away> [--win-prob <0-1>]
.venv\Scripts\python.exe scripts\state_store.py record-result --week <N> --result <win|loss>
.venv\Scripts\python.exe scripts\fetch_week_data.py --week <N> --season <YYYY>
.venv\Scripts\python.exe scripts\fetch_full_schedule.py --season <YYYY>
```
(`fetch_week_data.py`'s `matchups[]` entries include `status`/`home_score`/`away_score`/`winner`/`overtime` — null until a game is final, so re-running it for a past week also serves as the actual-results lookup.)

## Architecture

**Four skills drive the whole workflow** (triggered by natural language, not explicit invocation — see each `SKILL.md` for exact trigger phrasing):
- `survivor-pick` — recommends the week's pick. Purely advisory towards pool state: it never writes `data/state.json`. Before researching, it reads `data/calibration.json`'s `lessons_learned[]` (see "Calibration and the learning loop" below) and threads a condensed version through its own research and into the Skeptic/Arbiter subagent prompts. Research covers odds/injuries/weather *and* historic head-to-head (team, head coach, and starting QB, home-adjusted), stadium/city venue history, rest/prep differential (bye/short week/long week, plus 2nd+ consecutive road game), and an explicit trap-game screen (look-ahead spot, letdown spot, new-system uncertainty, get-right game for the opponent, etc.) — see the skill file for the full criteria list. It does write `data/week_analysis.json`, a display cache of its board/rationale for `survivor-grid` to render (not pool state), and archives the outgoing board to `data/history/` before overwriting it each time it moves on to a new week.

  **The pick isn't a single pass — it's an adversarial debate.** For the shortlisted teams (~top 8-10 by power score), the flow is: an **Advocate** stage (live research → initial probability + `positives`) → an independent **Skeptic** subagent (spawned via the Agent tool, fresh context, sees only the Advocate's case and tries to find real flaws → `negatives`) → an independent **Arbiter** subagent (fresh context, sees *only* positives+negatives, not the raw research trail, and returns a final `win_prob` + `summary`). Teams outside the shortlist skip the full debate and get a lighter single-pass positives/negatives note. This is a real architectural pattern, not a one-off — every `survivor-pick` run should spawn genuine Skeptic and Arbiter subagents, not simulate them inline in the same context (that would defeat the point of an independent counterweight).

  **No-lazy-favorite rule**: whichever shortlisted team has the single highest *raw* Vegas-implied probability (from the moneyline alone, before any debate) is never assigned as `recommendation`, even if it still tops the board after the Arbiter's verdict — it's recorded as `largest_vegas_favorite` in `week_analysis.json` with a `note` explaining the exclusion, and `recommendation` goes to the next-best team. This is a deliberate policy (see `survivor-pick/SKILL.md`'s "Core principle"), not a bug — don't "fix" it by picking the favorite when the numbers say it's best.

  **Trap games are scarce, and are also excluded from the recommendation.** `trap_flags` is capped at the 1-2 teams per week with the most credible, well-evidenced upset risk — not a checklist flag applied to every team with some negative. A team with real, serious `negatives` that isn't one of those 1-2 curated trap games still gets `trap_flags: []`; a real weakness already reflected in a modest probability is just a bad pick, not a "trap." Any team that does carry `trap_flags` is automatically excluded from `recommendation`, the same way the largest Vegas favorite is — the two exclusion sets often overlap (a trap game is usually one of the biggest favorites) but are independent checks, and both must be applied before picking `recommendation`.
- `survivor-record` — the *only* thing that writes `data/state.json`. Handles both "confirm this week's pick" (before kickoff) and "record the result" (after the game). It no longer relies on the user reporting win/loss verbally: it fetches the week's actual final scores itself via `fetch_week_data.py` and determines the result automatically (falling back to the user's explicit report only if the feed hasn't caught up yet, or surfacing a conflict if their report disagrees with the fetched outcome). Recording a result automatically chains into `survivor-review` — the user never has to invoke review by hand for the learning loop to run.
- `survivor-review` — grades a finished week's `survivor-pick` board (win probabilities, no-lazy-favorite calls, trap-flag calls) against actual results, and distills `lessons_learned` fed back into future `survivor-pick` runs. The only thing that writes `data/calibration.json`. Runs automatically (chained from `survivor-record`) or on demand ("review week N", "how did our picks do").
- `survivor-grid` — publishes/refreshes an Artifact with two parts: a "This Week's Outlook" panel (from `data/week_analysis.json`) and the teams-x-weeks schedule grid.

**Two data layers, deliberately split:**
- Structured/historical data (schedules, team records, point differentials) comes from `nfl_data_py` via `scripts/fetch_week_data.py` and `scripts/fetch_full_schedule.py`. This is the only programmatic data source. `fetch_week_data.py`'s `matchups[]` entries also carry `status` (`scheduled`/`final`), `home_score`, `away_score`, `winner`, and `overtime` — all `null` until a game is final, reusing the same score columns `team_stats` already relies on for prior-week records, so `survivor-record` and `survivor-review` don't need a separate script to look up actual results.
- Time-sensitive data (Vegas odds, injuries/suspensions, weather) is fetched live by Claude via WebSearch/WebFetch *inside the skill*, not scripted — there's no free reliable API for same-day odds/injuries, and it changes too often to cache.

**`data/state.json` is the single source of truth** for the pool: `season`, `current_week`, `status` (`alive`|`eliminated`), `mistake_count`, and a `picks[]` list (each with `week`, `team`, `opponent`, `home_away`, `result`, `win_prob_estimate`). Used teams are *derived* from `picks[].team` — there is no separate "used teams" list to keep in sync. `status` only ever moves `alive` → `eliminated` on a loss; it never reverts, even on a later win (per the consolation-prize rules). A pick with `result == "pending"` is the *current* week's confirmed-but-undecided pick, distinct from a decided (`win`/`loss`) pick from a past week — the grid Artifact displays these two states differently ("Your pick" vs "Used").

**`data/week_analysis.json`** is written by `survivor-pick` on every run (overwritten each time, not appended) and consumed by `survivor-grid`'s outlook panel. It's keyed by `season`/`week` — `survivor-grid` only displays it if those match the current week from `state.json`; otherwise it's stale and should be treated as absent. Each `board[]` entry carries `win_prob`, `summary`, `positives[]`, `negatives[]`, `trap_flags[]`, `is_largest_vegas_favorite`, and four step-6 research factors as their own fields — `weather` (null for dome/fixed-roof games, never a guessed value), `head_to_head`, `venue_history`, `rest_prep` — kept separate from the `positives`/`negatives` prose so the artifact can show them as distinct, scannable lines per team rather than burying them in a paragraph. There's also a top-level `largest_vegas_favorite` object naming the excluded favorite and why. Before each overwrite, `survivor-pick` archives the outgoing file to `data/history/week_analysis_<season>_wk<NN>.json` (see "Calibration and the learning loop" below) so it isn't lost once a new week's run replaces it.

**Strategy branches on `state.status`** (implemented as guidance inside `survivor-pick/SKILL.md`, not code): while `alive`, weigh this week's win probability against the opportunity cost of burning a strong team that has a much better matchup in a future week (using the full-season schedule from `fetch_full_schedule.py`/`data/full_schedule.json`). Once `eliminated`, skip that entirely and recommend whichever team has the highest win probability — there's no more future value to protect, and every remaining week counts equally toward `mistake_count`.

**`nfl_data_py` team-abbreviation quirk:** `nfl.import_team_desc()` returns 36 rows, not 32 — it includes retired/relocated abbreviations (`OAK`, `SD`, `STL`, and a duplicate `LAR` alongside `LA`) that never appear in a current-season schedule. Both fetch scripts derive the real 32-team set from the season's own schedule (`home_team`/`away_team` columns), not from `team_desc`, and only use `team_desc` for metadata (name/conference/division) lookups.

**`data/artifacts.json`** stores the published URL of the schedule-grid Artifact (`survivor_grid_url`) so `survivor-grid` updates the same page in place on each refresh instead of publishing a new one every time.

**Calibration and the learning loop.** `data/history/` holds one archived pregame board per past week (`week_analysis_<season>_wk<NN>.json`, written by `survivor-pick` right before each overwrite of the live `data/week_analysis.json`) — this is what lets a week be graded after the live file has moved on. `data/calibration.json` is owned solely by `survivor-review`: it accumulates a per-week grading of the *whole* board (not just the user's own pick) against actual results — a Brier-score-style calibration number, bucket calibration (e.g. "teams predicted 70-80% won X% of the time"), and an explicit grade of the no-lazy-favorite and trap-flag policies against real outcomes — plus an append-only `lessons_learned[]` array tagged by `criteria_area` (e.g. `vegas_favorite_bias`, `trap_flag_criteria`, `rest_prep`). This is a real feedback mechanism, not a report nobody reads: `survivor-pick` reads `lessons_learned[]` at the start of every run and threads a condensed version through its own research *and* — critically — verbatim into the Skeptic's and Arbiter's subagent prompts, since those spawn with fresh, isolated context and have no other way to see anything from a past week (the same "must be a genuine independent subagent, not simulated inline" principle that governs the debate itself applies here: the lessons only actually reach them if they're explicitly put in the prompt).

## Keeping this file updated

Update this CLAUDE.md whenever a change would make the sections above stale — e.g., adding/renaming a skill or script, changing the `state.json` schema, changing how/where data is fetched, or changing the alive/eliminated strategy split. Treat it as part of the change, not a follow-up: update it in the same commit/session as the code change, not after.
