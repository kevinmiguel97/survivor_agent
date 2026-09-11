---
name: survivor-grid
description: This skill should be used when the user asks to see, generate, refresh, or update the full-season NFL schedule grid — e.g. "show me the schedule grid", "update the survivor grid", "which weeks are easy/hard for each team", "show this week's pick probabilities". Publishes a teams-x-weeks matchup grid plus this week's ranked pick outlook as a Claude Code Artifact, similar to sharpfootballanalysis.com's schedule grid.
version: 1.1.0
---

# NFL Survivor — Schedule Grid Artifact

Publishes a visual reference page with two parts:
1. **This Week's Outlook** — the ranked win-probability board and rationale from the most recent `survivor-pick` run, with the currently selected pick (if any) called out.
2. **The season schedule grid** — all 32 teams (rows, grouped by division) x weeks 1-18 (columns), each cell showing that team's opponent. Same idea as the [Sharp Football Analysis schedule grid](https://www.sharpfootballanalysis.com/analysis/nfl-schedule-grid-regular-season/), for spotting bye weeks, tough/soft stretches, and rivalry games when deciding which teams to save for later.

## Steps

1. **Refresh the schedule data.** Run:
   ```
   .venv\Scripts\python.exe scripts\fetch_full_schedule.py --season <season>
   ```
   This writes `data/full_schedule.json` (every team's opponent/home-away/bye for every week) and also prints it.

2. **Load pool state.** Run `.venv\Scripts\python.exe scripts\state_store.py show`. From `picks[]`, split into:
   - **Used teams** (any pick with `week < current_week`, i.e. already decided) — win or loss, these are spent and can never be picked again.
   - **Current pick** (a pick entry with `week == current_week`, `result == "pending"`) — the team the user has locked in for this week but the game hasn't happened yet, if `survivor-record` has already logged it.

3. **Load this week's outlook, if available.** Read `data/week_analysis.json` if it exists. Only use it if its `season`/`week` match the current season/week from state — otherwise it's stale (leftover from a prior week that was never refreshed) and should be omitted rather than shown as if current. If missing or stale, skip the outlook panel and just note to the user that running `survivor-pick` first will populate it.

4. **Load required skills before writing the artifact**: load `artifact-design` (required before any artifact) and `dataviz` (for grid/table color conventions) so the page reads as a polished, theme-aware table rather than a raw data dump.

5. **Build and publish the HTML Artifact:**
   - **Outlook panel** (top of page, only if step 3 found current data): a ranked list/table of `week_analysis.json`'s `board`, sorted by `win_prob` descending — team, opponent, home/away, win probability (as a number and a simple bar), the one-line rationale, and a small warning badge for any `trap_flags`. Call out the `recommendation` team distinctly (e.g. a "Recommended" badge). If the **current pick** from step 2 exists, mark that row clearly as "Your pick" regardless of whether it's the same as the recommendation — the user's actual choice may have differed.
   - **Schedule grid** (below the outlook panel): rows = the 32 teams from `full_schedule.json`, grouped by division (`meta.conference` + `meta.division`); columns = weeks 1-18; each cell = opponent abbreviation, `@` prefix for away, "BYE" for a bye week.
     - Mark **used teams'** rows/cells distinctly (e.g. a border + "USED · Wk N" badge) — these are permanently unavailable.
     - Mark the **current pick's** cell distinctly from used cells (e.g. a different accent color + "Your pick" badge) — it's provisional until the result is recorded, unlike a used team's historical result.
   - Keep the table horizontally scrollable (18 week-columns won't fit most viewports) per the artifact responsive-design rules — never let the page itself scroll horizontally.
   - Give it a short, specific title (e.g. "2026 Survivor Schedule Grid") and a one-sentence description.

6. **Publish/update in place.** Check `data/artifacts.json` for a `survivor_grid_url` key. If present, pass that as `url` to the Artifact tool so this updates the same page in place. If absent (first run), publish a new Artifact, then write its URL into `data/artifacts.json` as `survivor_grid_url` so future runs update it instead of creating a new page each time. Mention the URL to the user so they can bookmark it.

7. Briefly tell the user what's new since the last refresh (e.g. newly used teams now marked, updated outlook, any schedule corrections) rather than re-describing the whole page.
