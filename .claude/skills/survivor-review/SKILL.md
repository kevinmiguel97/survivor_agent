---
name: survivor-review
description: This skill should be used after a week's NFL games finish to grade how well survivor-pick's pregame win probabilities and Advocate/Skeptic/Arbiter debate calls held up against actual results, and to distill lessons that improve future picks — e.g. "review week N", "how did our predictions do", "grade last week's board". Also triggered automatically by survivor-record right after a result is logged. Updates data/calibration.json (the only skill that writes it).
version: 1.0.0
---

# NFL Survivor — Weekly Review & Calibration

Grades a finished week's `survivor-pick` board against what actually happened, and turns that into distilled, reusable lessons that future `survivor-pick` runs (and its Skeptic/Arbiter subagents) are instructed to apply. This is the "learning loop" — it's what makes the debate arguments and the no-lazy-favorite/trap-flag policies get better over time instead of repeating the same mistakes.

This skill is read-only with respect to `data/state.json` and `data/week_analysis.json`. `data/calibration.json` is the only file it writes.

## Steps

1. **Determine which week to review.** If invoked with an explicit week/season (the normal case — chained from `survivor-record` right after a result is logged), use it. If invoked standalone with no week named, run `state_store.py show` for `season`, and default to the most recent week with `result != "pending"` that has no entry yet in `data/calibration.json`'s `weeks[]`. If every decided week is already reviewed, ask the user which week to re-run. If the target week already has an entry in `calibration.json`, this is a re-run to pick up newly-finished games (step 4) — update that entry in place, don't duplicate it.

2. **Retrieve the archived pregame board.** Read `data/history/week_analysis_<season>_wk<NN>.json` (week zero-padded to 2 digits — this is written by `survivor-pick`'s archive step before each overwrite of `data/week_analysis.json`). If it doesn't exist (the feature wasn't live yet that week, or `survivor-pick` was skipped), degrade gracefully: skip straight to a bare outcome log using only `data/state.json`'s pick for that week plus the fetched score from step 3 — no calibration grading is possible without the archived board. State this plainly in the final report; don't error.

3. **Fetch actual results:**
   ```
   .venv\Scripts\python.exe scripts\fetch_week_data.py --week <week> --season <season>
   ```
   Build a team → `{status, winner, opponent, home_away, home_score, away_score}` map from `matchups[]` (every team appears once, as home or away). Any team whose game `status` is `"scheduled"` is simply excluded from this run's grading — noted as "not yet final, will be picked up on a re-run," not an error. This is what makes a Thu/Sun/Mon split week work without failing.

4. **Grade every eligible team** from the archived board against the fetched outcome (skip step 4-5 entirely if step 2 had no archive):
   - `actual_result` = `"win"`/`"loss"`/`"tie"` from `winner`. Games still `"scheduled"` are excluded from this pass.
   - Per-team `brier_component = (predicted_win_prob - actual_outcome[1 or 0])^2` (exclude ties and non-final games).
   - Weekly `brier_score` = mean of `brier_component` across graded teams.
   - Bucket calibration across fixed buckets `["<50%", "50-59%", "60-69%", "70-79%", "80-89%", "90-100%"]`: predicted average vs. actual win rate per bucket, for this week's graded teams.
   - Grade `largest_vegas_favorite`: did it win or lose?
   - Grade every `trap_flags`-carrying team: `validated: true` if it actually lost (the flag called it correctly), `false` if it won comfortably (false alarm). Tally hits/misses.
   - Grade the no-lazy-favorite policy directly — this is the single most important test of that policy, always compute and report it: `"cost_a_pick"` if the excluded largest-Vegas-favorite won AND `recommendation` lost; `"saved_a_pick"` if the favorite lost AND `recommendation` won; otherwise `"no_cost"`.

5. **Tiered recap depth** (mirrors `survivor-pick`'s shortlist-vs-rest pattern — don't do deep research on every team every week):
   - **Deep recap** (WebSearch what actually happened and why, 2-4 sentences each): the user's own picked team; the `largest_vegas_favorite`; any `trap_flags`-carrying team; any "surprise" team where `win_prob >= 0.65` and it lost, or `win_prob <= 0.35` and it won. Cap this tier at ~10 teams — always include the user's pick, the favorite, and trap-flagged teams first; if slots remain, rank other surprises by `|win_prob - actual_outcome|` descending.
   - **Numeric-only**: every other graded team — just `predicted_win_prob`, `actual_result`, `brier_component`, no WebSearch.
   - **Not final**: outcome-only logging once available; `predicted_win_prob: null` if there's no archived board.

6. **Distill lessons.** From the deep recaps and the aggregate stats in step 4, add 0-3 new entries to `data/calibration.json`'s `lessons_learned[]` (append-only — never edit or delete a past entry). Only add a lesson when it's genuinely generalizable to future criteria/weighting — e.g. "reverse line movement alone didn't predict this upset; require a corroborating injury/personnel signal before flagging a trap on RLM alone" is a lesson; "DET's secondary got exposed" is not, unless it points to something that generalizes (e.g. "weight a missing starter at a premium position more heavily in Negatives"). Tag each with a `criteria_area`: `vegas_favorite_bias`, `trap_flag_criteria`, `weather`, `injury_weighting`, `head_to_head_venue`, `rest_prep`, `advocate_skeptic_process`, `opportunity_cost`, or `other`.

7. **Write `data/calibration.json`** (sole owner of this file — create it fresh if it doesn't exist, otherwise load-modify-save):
   ```json
   {
     "season": <season>,
     "weeks": [
       {
         "week": <N>,
         "reviewed_at": "<ISO 8601 timestamp>",
         "board_source": "data/history/week_analysis_<season>_wk<NN>.json",
         "games_final_count": <int>,
         "games_pending_count": <int>,
         "recommendation": "<abbr>",
         "recommendation_result": "win|loss|tie|pending",
         "largest_vegas_favorite": {"team": "<abbr>", "raw_vegas_prob": <0-1>, "actual_result": "win|loss|tie|pending"},
         "trap_flags_grading": [
           {"team": "<abbr>", "flags": ["<tag>"], "actual_result": "win|loss|tie|pending", "validated": <true|false|null>}
         ],
         "no_lazy_favorite_policy_outcome": "cost_a_pick|saved_a_pick|no_cost|undetermined",
         "brier_score": <float|null>,
         "teams_graded": <int>,
         "bucket_calibration": [
           {"bucket": "80-89%", "predicted_avg": <float>, "actual_win_rate": <float>, "n": <int>}
         ],
         "team_results": [
           {
             "team": "<abbr>", "opponent": "<abbr>", "predicted_win_prob": <0-1|null>,
             "actual_result": "win|loss|tie|pending",
             "brier_component": <float|null>, "recap_tier": "deep|numeric_only|outcome_only",
             "recap": "<2-4 sentence what-happened-and-why, or null>",
             "is_largest_vegas_favorite": <bool>, "trap_flags": ["<tag>", "..."]
           }
         ]
       }
     ],
     "season_summary": {
       "weeks_reviewed": <int>,
       "total_teams_graded": <int>,
       "running_brier_score": <float|null>,
       "running_bucket_calibration": [
         {"bucket": "80-89%", "predicted_avg": <float>, "actual_win_rate": <float>, "n": <int>}
       ],
       "no_lazy_favorite_policy_record": {"no_cost": <int>, "cost_a_pick": <int>, "saved_a_pick": <int>},
       "trap_flag_policy_record": {"validated": <int>, "false_alarm": <int>}
     },
     "lessons_learned": [
       {
         "id": "L<n>",
         "added_week": <N>,
         "added_at": "<ISO 8601 timestamp>",
         "criteria_area": "<tag>",
         "lesson": "<free text, generalizable>"
       }
     ]
   }
   ```
   Upsert (don't duplicate) the entry for the reviewed week in `weeks[]`, recompute `season_summary` from all weeks present, and append any new `lessons_learned` entries from step 6. `weeks[]`/`season_summary`/`lessons_learned` are namespaced so this file never collides with `week_analysis.json`'s or `state.json`'s top-level keys — `survivor-grid` does not need to read this file.

8. **Report to the user**: this week's Brier score vs. the running season average; a one-line grade of the no-lazy-favorite and trap-flag policies; the deep recaps from step 5; any new lessons added (or explicitly "no new generalizable lessons this week"); if step 2 had no archive, say plainly that only bare outcomes were logged; if games are still pending, name them and note that re-running the review later will pick them up.
