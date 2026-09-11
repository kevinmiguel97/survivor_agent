# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An NFL survivor-pool assistant for a private/office pool. Pool rules: pick one team per week, each team usable only once all season, one loss eliminates you from the main prize; after elimination the user keeps picking every remaining week (no team reuse) to minimize total losses for a "fewest mistakes" consolation prize. See `README.md` for the full rules writeup.

The assistant is three Claude Code skills (`.claude/skills/`) backed by small Python scripts — there is no app server, build step, test suite, or linter in this repo.

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

## Architecture

**Three skills drive the whole workflow** (triggered by natural language, not explicit invocation — see each `SKILL.md` for exact trigger phrasing):
- `survivor-pick` — recommends the week's pick. Purely advisory towards pool state: it never writes `data/state.json`. Research covers odds/injuries/weather *and* historic head-to-head (team, head coach, and starting QB, home-adjusted), stadium/city venue history, rest/prep differential (bye/short week/long week), and an explicit trap-game screen (look-ahead spot, letdown spot, new-system uncertainty, get-right game for the opponent, etc.) — see the skill file for the full criteria list. It does write `data/week_analysis.json`, a display cache of its board/rationale for `survivor-grid` to render (not pool state).
- `survivor-record` — the *only* thing that writes `data/state.json`. Handles both "confirm this week's pick" (before kickoff) and "record the result" (after the game).
- `survivor-grid` — publishes/refreshes an Artifact with two parts: a "This Week's Outlook" panel (from `data/week_analysis.json`) and the teams-x-weeks schedule grid.

**Two data layers, deliberately split:**
- Structured/historical data (schedules, team records, point differentials) comes from `nfl_data_py` via `scripts/fetch_week_data.py` and `scripts/fetch_full_schedule.py`. This is the only programmatic data source.
- Time-sensitive data (Vegas odds, injuries/suspensions, weather) is fetched live by Claude via WebSearch/WebFetch *inside the skill*, not scripted — there's no free reliable API for same-day odds/injuries, and it changes too often to cache.

**`data/state.json` is the single source of truth** for the pool: `season`, `current_week`, `status` (`alive`|`eliminated`), `mistake_count`, and a `picks[]` list (each with `week`, `team`, `opponent`, `home_away`, `result`, `win_prob_estimate`). Used teams are *derived* from `picks[].team` — there is no separate "used teams" list to keep in sync. `status` only ever moves `alive` → `eliminated` on a loss; it never reverts, even on a later win (per the consolation-prize rules). A pick with `result == "pending"` is the *current* week's confirmed-but-undecided pick, distinct from a decided (`win`/`loss`) pick from a past week — the grid Artifact displays these two states differently ("Your pick" vs "Used").

**`data/week_analysis.json`** is written by `survivor-pick` on every run (overwritten each time, not appended) and consumed by `survivor-grid`'s outlook panel. It's keyed by `season`/`week` — `survivor-grid` only displays it if those match the current week from `state.json`; otherwise it's stale and should be treated as absent.

**Strategy branches on `state.status`** (implemented as guidance inside `survivor-pick/SKILL.md`, not code): while `alive`, weigh this week's win probability against the opportunity cost of burning a strong team that has a much better matchup in a future week (using the full-season schedule from `fetch_full_schedule.py`/`data/full_schedule.json`). Once `eliminated`, skip that entirely and recommend whichever team has the highest win probability — there's no more future value to protect, and every remaining week counts equally toward `mistake_count`.

**`nfl_data_py` team-abbreviation quirk:** `nfl.import_team_desc()` returns 36 rows, not 32 — it includes retired/relocated abbreviations (`OAK`, `SD`, `STL`, and a duplicate `LAR` alongside `LA`) that never appear in a current-season schedule. Both fetch scripts derive the real 32-team set from the season's own schedule (`home_team`/`away_team` columns), not from `team_desc`, and only use `team_desc` for metadata (name/conference/division) lookups.

**`data/artifacts.json`** stores the published URL of the schedule-grid Artifact (`survivor_grid_url`) so `survivor-grid` updates the same page in place on each refresh instead of publishing a new one every time.

## Keeping this file updated

Update this CLAUDE.md whenever a change would make the sections above stale — e.g., adding/renaming a skill or script, changing the `state.json` schema, changing how/where data is fetched, or changing the alive/eliminated strategy split. Treat it as part of the change, not a follow-up: update it in the same commit/session as the code change, not after.
