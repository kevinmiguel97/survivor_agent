"""Pull the entire season schedule for all 32 teams (weeks 1-18) via
nfl_data_py and cache it as data/full_schedule.json for the survivor-grid
Artifact (a Sharp-Football-style teams x weeks matchup grid).

Usage:
    python fetch_full_schedule.py [--season 2026]
Writes data/full_schedule.json and also prints it to stdout.
"""

import argparse
import datetime
import json
import math
from pathlib import Path

import nfl_data_py as nfl

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "data" / "full_schedule.json"


def _sanitize(obj):
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, float) and math.isnan(obj):
        return None
    return obj


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, default=None)
    args = parser.parse_args()

    season = args.season
    if season is None:
        today = datetime.date.today()
        season = today.year if today.month >= 8 else today.year - 1

    schedules = nfl.import_schedules([season])
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
    weeks = sorted(current_season_games["week"].unique().tolist())

    by_team = {team: {} for team in all_teams}
    for _, g in schedules[schedules["season"] == season].iterrows():
        week = int(g["week"])
        home, away = g["home_team"], g["away_team"]
        if home in by_team:
            by_team[home][week] = {"opponent": away, "home_away": "home"}
        if away in by_team:
            by_team[away][week] = {"opponent": home, "home_away": "away"}

    grid = {}
    for team in all_teams:
        row = {}
        for week in weeks:
            row[str(week)] = by_team[team].get(week, {"opponent": None, "home_away": "bye"})
        grid[team] = {"meta": teams_meta[team], "weeks": row}

    output = _sanitize({"season": season, "weeks": weeks, "teams": grid})

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
