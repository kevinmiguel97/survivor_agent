---
name: survivor-pick
description: This skill should be used when the user asks for their weekly NFL survivor pool pick, e.g. "who should I pick this week", "give me my survivor pick", "what's the best survivor pick for week N", or discusses this repo's survivor pool strategy.
version: 1.3.0
---

# NFL Survivor Weekly Pick

Recommends this week's survivor pick for the user's private/office pool tracked in `data/state.json`. Rules: pick one team per week, each team usable only once all season, one loss eliminates you from the main prize. After elimination the user keeps picking every remaining week (no team reuse) to minimize total losses for a "fewest mistakes" consolation prize.

**Core principle: never crown a pick just because it's the biggest, cleanest Vegas favorite.** That's the lazy version of this skill and it's explicitly disallowed — see step 9. Every recommendation must survive an adversarial debate (steps 6-8) first.

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

4. **Shortlist**: rank eligible teams by a rough power score (point differential per game, blending prior/current season per step 2) and take the top ~8-10 for the full adversarial process below. Don't skip a team just because it's a home dog if its underlying numbers are strong. Everything outside the top 8-10 still appears in the final board (per step 9) but only needs a brief, one-pass positives/negatives note — not the full debate.

5. **Advocate case (live research per shortlisted team, WebSearch/WebFetch).** Build the affirmative case — this becomes that team's "Positives." Cover:
   - **Odds**: current Vegas spread/moneyline for their game this week → convert to implied win probability. Record this raw implied number specifically — step 9 needs it.
   - **Injuries/suspensions**: latest report — especially starting QB status for both the team and its opponent.
   - **Weather**: forecast if the game is outdoors (`roof` field from step 2) — wind and precipitation matter most for passing offenses and total scoring, less so for a heavy run-game favorite.
   - **Recent form**: last 2-3 games and any head-to-head meetings already played this season.
   - **Historic head-to-head, home-adjusted**: how this matchup has gone historically, split out by home/away — at three levels: the two **teams** overall, the two **head coaches** (including prior stops, if either has faced the other before at a different team), and the two **starting QBs** (personal head-to-head record/stats, if they've faced off before).
   - **Venue/city history**: how the away team (and specifically its starting QB) has historically performed at this stadium/city — elevation, dome vs. outdoor, noise, travel distance/time-zone shift can produce a persistent record independent of general team strength.
   - **Rest/prep differential**: days of rest coming in — short week, off a bye, a long week, or long travel. More prep favors the better-coached/disciplined side; short rest drags on a normally-favored team.

   Distill this into a per-team initial win-probability estimate (Vegas implied probability as the primary anchor, adjusted for everything else above) and a short list of **Positives** bullets.

6. **Trap-game screen.** For every shortlisted team, check whether any of these apply, since this feeds the Skeptic in step 7:
   - **Look-ahead spot**: a much bigger game (rivalry, playoff-implication) next week.
   - **Letdown spot**: coming off an emotional/high-stakes win into a lesser opponent.
   - **Short-week/travel trap**: already covered in step 5's rest differential — call it out here if it applies to a specific candidate.
   - **New-system uncertainty**: a new HC/coordinator/scheme install (either side) adding game-flow variance the numbers don't reflect yet.
   - **Get-right game for the opponent**: the underdog is bad on paper but off a bye, returning a key starter, or extra-motivated (revenge game, first meeting with a former team/coach).
   - **Public/trendy overreaction**: the line moved on hype/hate rather than fundamentals.

   **Trap-game status is scarce — cap it at 1-2 teams per week, not a checklist applied to everyone.** Checking for these categories is a normal part of researching every team, and most teams will trip a minor version of one — that's not enough to earn the label. Reserve "trap game" for the biggest favorite(s) whose case has a specific, well-evidenced reason they could plausibly lose outright, beyond routine downside. After the Skeptic (step 7) and Arbiter (step 8) finish, look back across the *whole* shortlist and pick only the 1-2 highest-probability teams with the most credible upset case — usually, though not always, among the top few favorites, since "trap" means a game that looks safer than it is. Clear `trap_flags` on every other team, even ones with a real negative — a real weakness that's already reflected in a modest probability isn't a trap, it's just a bad pick, and belongs in `negatives` only.

7. **Skeptic review — adversarial counterweight.** Spawn one independent subagent (Agent tool, fresh context — it must not simply inherit the Advocate's framing) covering the whole shortlist at once. Give it: each shortlisted team, its matchup, and the Advocate's Positives + initial probability from steps 5-6. Its sole job is to find flaws in that specific reasoning and produce a **Negatives** list per team — not generic downsides, but a real rebuttal: does the injury report undersell a key role player? Does the historical head-to-head/venue signal cut the other way? Is the rest advantage overstated? Does a trap-game category from step 6 deserve more weight than the Advocate gave it? Instruct it to do its own WebSearch where useful rather than just re-reading the Advocate's claims. Ask it to return, per team: a `negatives` list and (optionally) a suggested probability adjustment with reasoning — but not a final number; that's the Arbiter's job.

8. **Arbiter synthesis — independent judgment.** Spawn a second, separate subagent (Agent tool, fresh context, independent of both prior steps). Give it, per team, *only* the Positives (step 5) and Negatives (step 7) — not the raw research trail, so it judges the arguments on their merits rather than re-deriving its own research. Instruct it to genuinely weigh both sides (not average or split the difference) and return, per team: a final win probability and a 2-3 sentence `summary` explaining how the debate resolved (which side's argument mattered more and why).

9. **Apply the no-lazy-favorite and no-trap-recommendation rules, then pick the recommendation.**
   - Among the shortlisted teams, identify whichever had the single highest *raw Vegas-implied* win probability from step 5 (before any debate/adjustment) — call this the **largest Vegas favorite**.
   - Take the 1-2 teams that survived the step-6 curation with non-empty `trap_flags`.
   - Neither group is ever assigned as `recommendation`, regardless of Arbiter probability — they still appear fully in the board with their Arbiter probability, Positives, Negatives, and (respectively) the favorite note or trap flags, so the user can see the case for/against them. The `recommendation` is the highest Arbiter-probability team among everyone else. (The largest favorite and a trap-flagged team are very often the same team or two of the same handful of top favorites — that's expected, not a bug; don't force them to be different teams.)

10. **Branch on `status` for the recommendation:**
    - **`alive`**: Before finalizing, check the rest-of-season schedule (`scripts\fetch_full_schedule.py` / `data/full_schedule.json`) for the top remaining candidates. If a team has a much rarer/easier matchup in a specific future week and its edge THIS week is only marginal vs. the next choice, prefer saving it and recommend the next-best team instead. Only override for a meaningful, explainable future opportunity-cost reason.
    - **`eliminated`**: Skip opportunity-cost logic entirely — recommend the highest Arbiter-probability team among the non-excluded candidates.

11. **Output to the user:**
    - **Top recommendation**: team, opponent, home/away, Arbiter win probability, and the Arbiter's summary (why it won the debate; if `alive`, why it wasn't a save-for-later situation).
    - **Full ranked board**: every eligible team, sorted by Arbiter (or, for teams outside the shortlist, single-pass) win probability. For shortlisted teams show Team / Probability / Summary / Positives / Negatives; flag the largest-Vegas-favorite team with its note. Teams outside the shortlist can carry a lighter one-line positives/negatives note rather than the full debate.
    - **Season-long allocation sketch** (only if `status == "alive"`): which remaining strong teams look best saved for which future weeks.

12. **Persist the analysis for the schedule-grid Artifact.** Write `data/week_analysis.json` (overwrite any existing file):
    ```json
    {
      "season": <season>,
      "week": <current_week>,
      "generated_at": "<ISO 8601 timestamp>",
      "recommendation": "<team abbr>",
      "largest_vegas_favorite": {
        "team": "<abbr>", "raw_vegas_prob": <0-1>,
        "note": "Largest Vegas favorite this week — not auto-selected by policy."
      },
      "board": [
        {
          "team": "<abbr>", "opponent": "<abbr>", "home_away": "home|away",
          "win_prob": <0-1 — Arbiter's final number for shortlisted teams>,
          "summary": "<2-3 sentence synthesis of how the debate resolved>",
          "positives": ["<bullet>", "..."],
          "negatives": ["<bullet>", "..."],
          "trap_flags": ["<short tag naming which step-6 trap category applies, e.g. 'new-system uncertainty (...)'>"],
          "is_largest_vegas_favorite": <true|false>
        }
      ]
    }
    ```
    `trap_flags` is distinct from `negatives` even though the underlying evidence overlaps — it's reserved for the 1-2 teams per week that earned the curated "trap game" label in step 6, not a general-purpose flag for any concern. Every other team's array is empty, including ones with real, serious `negatives` — those just aren't trap games. `survivor-grid` renders `trap_flags` as a distinct "⚠ Trap risk" badge, separate from `is_largest_vegas_favorite`'s badge.
    Include every eligible team, not just the shortlist (non-shortlisted teams can have short 1-2 item `positives`/`negatives` lists instead of a full debate). This file is a display cache only — never used to determine pool eligibility; `data/state.json` remains the sole source of truth for that. Then mention to the user that `survivor-grid` can be refreshed to see this week's board visually.

13. **Do not modify `data/state.json`.** This skill is advisory only. Only record the user's actual chosen pick (via `survivor-record`) once they confirm which team they're going with — their real choice may differ from the recommendation.
