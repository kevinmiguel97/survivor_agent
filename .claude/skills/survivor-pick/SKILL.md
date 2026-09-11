---
name: survivor-pick
description: This skill should be used when the user asks for their weekly NFL survivor pool pick, e.g. "who should I pick this week", "give me my survivor pick", "what's the best survivor pick for week N", or discusses this repo's survivor pool strategy.
version: 1.1.0
---

# NFL Survivor Weekly Pick

Recommends this week's survivor pick for the user's private/office pool tracked in `data/state.json`. Rules: pick one team per week, each team usable only once all season, one loss eliminates you from the main prize. After elimination the user keeps picking every remaining week (no team reuse) to minimize total losses for a "fewest mistakes" consolation prize.

## Steps

1. **Load state.** Run:
   ```
   .venv\Scripts\python.exe scripts\state_store.py show
   ```
   Note `season`, `current_week`, `status` (`alive`/`eliminated`), and every team already used (from `picks[].team`).

2. **Fetch this week's structured data.** Run:
   ```
   .venv\Scripts\python.exe scripts\fetch_week_data.py --week <current_week> --season <season>
   ```
   This returns matchups, bye teams, and each playing team's current-season record-so-far plus full prior-season record (point differential per game is the key strength signal, especially early in the season when current-season sample size is small — blend toward prior season early, toward current season as more games accumulate).

3. **Determine eligible candidates**: all teams in this week's matchups that have already kicked off or finished are no longer pickable this week — exclude them. From what's left, exclude teams already in `picks[].team` and `bye_teams`.

4. **Shortlist**: rank eligible teams by a rough power score (point differential per game, blending prior/current season per step 2) and take the top ~8-10 for deeper research. Don't skip a team just because it's a home dog if its underlying numbers are strong — but do prioritize likely favorites since win probability dominates the decision.

5. **Live research per shortlisted team** (WebSearch/WebFetch). Cover all of the following, not just odds:
   - **Odds**: current Vegas spread/moneyline for their game this week → convert to implied win probability.
   - **Injuries/suspensions**: latest report — especially starting QB status for both the team and its opponent.
   - **Weather**: forecast if the game is outdoors (`roof` field from step 2) — wind and precipitation matter most for passing offenses and total scoring, less so for a heavy run-game favorite.
   - **Recent form**: last 2-3 games and any head-to-head meetings already played this season.
   - **Historic head-to-head, home-adjusted**: how this matchup has gone historically, split out by home/away — at three levels: the two **teams** overall, the two **head coaches** (including in prior stops, if either has faced the other before at a different team), and the two **starting QBs** (their personal head-to-head record and stats in this matchup, if they've faced off before). A team that historically struggles against a specific coach or QB archetype is a real signal even when the season-long power rating says otherwise.
   - **Venue/city history**: how the away team (and specifically its starting QB) has historically performed at this stadium/city — some venues (elevation, dome vs. outdoor, noise, travel distance/time-zone shift) produce a persistent record independent of the two teams' general strength.
   - **Rest/prep differential**: how many days of rest each team has coming into this game — short week (e.g. playing Thursday after a Sunday game), coming off a bye (extra prep), a long week (extra rest after a Thursday/Monday game), or a trans-continental/international trip. More prep time favors the better-coached/more disciplined side; short rest is a real drag on a normally-favored team.

6. **Screen for trap games.** A trap game is a matchup where the surface-level pick (biggest favorite, best power rating) looks obvious but carries a specific, identifiable risk the raw numbers don't capture. For every team still under consideration after step 5, explicitly ask whether any of these apply, and note it even if you conclude it doesn't change the pick:
   - **Look-ahead spot**: the favorite has a much bigger game (rivalry, playoff-implication) the following week and might not be locked in.
   - **Letdown spot**: the favorite is coming off an emotional/high-stakes win and now faces a lesser opponent.
   - **Short-week/travel trap**: covered in step 5's rest differential, but call it out explicitly here if it applies to your top choice specifically.
   - **New-system uncertainty**: a new head coach, coordinator, or scheme install (either side) that adds game-flow variance the historical numbers don't reflect yet.
   - **Get-right game for the opponent**: the underdog is bad on paper but is coming off a bye, returning a key starter from injury, or has extra motivation (revenge game, first meeting with a former team/coach) that could make the game closer than the spread implies.
   - **Public/trendy overreaction**: the line has moved sharply on early-season hype/hate rather than fundamentals.
   If your top candidate has a real trap flag, don't necessarily drop it — but downgrade its win probability slightly, say so explicitly, and check whether the next-best team is trap-free and close enough in probability to prefer instead.

7. **Blend into a win-probability estimate per candidate**: Vegas implied probability is the primary anchor; adjust up/down for injury news, home/away, weather, historic head-to-head/venue patterns, rest differential, and any trap-game discount from step 6. Note your reasoning per team.

8. **Branch on `status`:**
   - **`alive`**: Before finalizing, check the rest-of-season schedule (available via `scripts\fetch_full_schedule.py`, or reuse `data/full_schedule.json` if already generated by `survivor-grid`) for each strong shortlisted team. If a team has a much rarer/easier matchup in a specific future week (e.g. the only team with a very soft opponent in a normally brutal week like 15-17), and its edge THIS week is only marginal vs. the top choice, flag that as a reason to save it and recommend the next-best team instead. Only override the top win-probability team for a meaningful, explainable future opportunity-cost reason — don't be clever for its own sake.
   - **`eliminated`**: Skip all opportunity-cost/saving logic. Recommend whichever eligible team has the single highest blended win probability — there is no more future survival value to protect, and every remaining week counts equally toward the mistake tally.

9. **Output three sections to the user:**
   - **Top recommendation**: team, opponent, home/away, blended win probability, and a short rationale (odds, injuries, weather, head-to-head/venue history, rest, and — if alive — why it wasn't a save-for-later situation; if it carries a trap flag, say so and why you're recommending it anyway).
   - **Full ranked board**: every eligible team considered, sorted by blended win probability, with a one-line note each (include a trap-game tag on any that carry one).
   - **Season-long allocation sketch** (only if `status == "alive"`): a short forward-looking note on which remaining strong teams look best saved for which future weeks, based on the schedule data.

10. **Persist the analysis for the schedule-grid Artifact.** Write `data/week_analysis.json` (overwrite any existing file) so `survivor-grid` can display this week's board and rationale on the published grid:
    ```json
    {
      "season": <season>,
      "week": <current_week>,
      "generated_at": "<ISO 8601 timestamp>",
      "recommendation": "<team abbr>",
      "board": [
        {
          "team": "<abbr>", "opponent": "<abbr>", "home_away": "home|away",
          "win_prob": <0-1>, "rationale": "<1-2 sentence summary>",
          "trap_flags": ["<short tag, e.g. 'new-system uncertainty'>"]
        }
      ]
    }
    ```
    Include every team from the full ranked board (step 9), not just the top pick. This file is a display cache only — it is never used to determine pool eligibility; `data/state.json` remains the sole source of truth for that. Then mention to the user that the schedule-grid Artifact can be refreshed (`survivor-grid`) to see this week's board visually.

11. **Do not modify `data/state.json`.** This skill is advisory only. Only record the user's actual chosen pick (via `survivor-record`) once they confirm which team they're going with — their real choice may differ from the recommendation.
