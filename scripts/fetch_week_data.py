"""Pull structured, free data for one NFL week via nfl_data_py:
matchups, bye teams, and season-to-date + prior-season team records.

Time-sensitive info (odds, injuries, weather) is NOT here — that's fetched
live via WebSearch inside the survivor-pick skill.

Each matchups[] entry also carries status/home_score/away_score/winner/
overtime — all null until the game is final, reusing the same score columns
team_stats already relies on. This lets the same script serve both pregame
planning (survivor-pick) and postgame lookup (survivor-record, survivor-review).

Usage:
    python fetch_week_data.py --week 1 [--season 2026]
Prints JSON to stdout.
"""

import argparse
import json
import math
import sys

import nfl_data_py as nfl
import pandas as pd


def _sanitize(obj):
    """Recursively replace float NaN with None so output is strict, parseable JSON."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, float) and math.isnan(obj):
        return None
    return obj


def team_record_through(schedules: pd.DataFrame, season: int, team: str, upto_week: int) -> dict:
    """Wins/losses/points for/against for `team` in `season`, only counting
    completed games (both scores present) strictly before `upto_week`."""
    played = schedules[
        (schedules["season"] == season)
        & (schedules["week"] < upto_week)
        & schedules["home_score"].notna()
        & schedules["away_score"].notna()
        & ((schedules["home_team"] == team) | (schedules["away_team"] == team))
    ]
    wins = losses = ties = pf = pa = 0
    for _, g in played.iterrows():
        is_home = g["home_team"] == team
        team_score = g["home_score"] if is_home else g["away_score"]
        opp_score = g["away_score"] if is_home else g["home_score"]
        pf += team_score
        pa += opp_score
        if team_score > opp_score:
            wins += 1
        elif team_score < opp_score:
            losses += 1
        else:
            ties += 1
    games = wins + losses + ties
    return {
        "games_played": games,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "points_for": pf,
        "points_against": pa,
        "point_diff_per_game": round((pf - pa) / games, 2) if games else None,
    }


def full_season_record(schedules: pd.DataFrame, season: int, team: str) -> dict:
    return team_record_through(schedules, season, team, upto_week=99)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--season", type=int, default=None,
                         help="Defaults to the season inferred from the current NFL calendar year.")
    args = parser.parse_args()

    season = args.season
    if season is None:
        import datetime
        today = datetime.date.today()
        # NFL "season year" = the year the season kicks off (Sept). Jan-Jul
        # of a given calendar year still belongs to the previous season year.
        season = today.year if today.month >= 8 else today.year - 1

    week = args.week
    prior_season = season - 1

    schedules = nfl.import_schedules([prior_season, season])
    teams_df = nfl.import_team_desc()
    teams_meta = {
        row["team_abbr"]: {
            "name": row["team_name"],
            "conference": row["team_conf"],
            "division": row["team_division"],
        }
        for _, row in teams_df.iterrows()
    }
    # team_desc includes retired/relocated abbreviations (OAK, SD, STL, LAR
    # duplicate of LA) that never appear in a current schedule — derive the
    # real 32-team set from the season's own schedule instead.
    current_season_games = schedules[schedules["season"] == season]
    all_teams = sorted(set(current_season_games["home_team"]) | set(current_season_games["away_team"]))

    week_games = schedules[(schedules["season"] == season) & (schedules["week"] == week)]
    if week_games.empty:
        print(json.dumps({"error": f"No games found for season {season} week {week}"}), file=sys.stderr)
        sys.exit(1)

    playing_teams = set(week_games["home_team"]) | set(week_games["away_team"])
    bye_teams = sorted(set(all_teams) - playing_teams)

    matchups = []
    for _, g in week_games.iterrows():
        home_score = g.get("home_score")
        away_score = g.get("away_score")
        is_final = pd.notna(home_score) and pd.notna(away_score)
        winner = None
        if is_final:
            if home_score > away_score:
                winner = g["home_team"]
            elif away_score > home_score:
                winner = g["away_team"]
            # else: tie — winner stays None
        matchups.append({
            "home_team": g["home_team"],
            "away_team": g["away_team"],
            "gameday": g["gameday"],
            "gametime": g.get("gametime"),
            "location": g.get("location"),
            "roof": g.get("roof") if "roof" in g else None,
            "status": "final" if is_final else "scheduled",
            "home_score": home_score if is_final else None,
            "away_score": away_score if is_final else None,
            "winner": winner,
            "overtime": bool(g["overtime"]) if is_final and pd.notna(g.get("overtime")) else None,
        })

    team_stats = {}
    for team in playing_teams:
        team_stats[team] = {
            "meta": teams_meta.get(team, {}),
            "current_season_record_before_this_week": team_record_through(schedules, season, team, week),
            "prior_season_full_record": full_season_record(schedules, prior_season, team),
        }

    output = {
        "season": season,
        "week": week,
        "matchups": matchups,
        "bye_teams": bye_teams,
        "team_stats": team_stats,
    }
    print(json.dumps(_sanitize(output), indent=2, default=str))


if __name__ == "__main__":
    main()
