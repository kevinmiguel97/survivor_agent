"""Pull structured, free data for one NFL week via nfl_data_py:
matchups, bye teams, and season-to-date + prior-season team records, with
yards differential and turnover differential per game (from play-by-play)
as the strength signals.

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
import contextlib
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


PBP_COLUMNS = ["season", "week", "game_id", "posteam", "defteam", "play_type",
               "yards_gained", "interception", "fumble_lost"]


def load_pbp(seasons: list) -> pd.DataFrame:
    """Play-by-play for yards/turnover differentials. Returns an empty frame
    (so the yards/turnover fields come out null) if a season isn't published."""
    frames = []
    for s in seasons:
        try:
            # import_pbp_data prints progress to stdout, which would corrupt the JSON output
            with contextlib.redirect_stdout(sys.stderr):
                frames.append(nfl.import_pbp_data([s], columns=PBP_COLUMNS, downcast=True, cache=False))
        except Exception as e:
            print(f"warning: no play-by-play for {s}: {e}", file=sys.stderr)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=PBP_COLUMNS)


def yards_turnovers_through(pbp: pd.DataFrame, season: int, team: str, upto_week: int) -> dict:
    """Yards and turnover differentials for `team` in `season`, over games
    strictly before `upto_week`. Yards = net yards on pass/run plays (sacks
    included); turnovers = interceptions + lost fumbles on live plays."""
    plays = pbp[(pbp["season"] == season) & (pbp["week"] < upto_week) & (pbp["play_type"] != "no_play")]
    off = plays[plays["posteam"] == team]
    dfn = plays[plays["defteam"] == team]
    games = off["game_id"].nunique()
    scrimmage = ("pass", "run")
    yards_for = float(off.loc[off["play_type"].isin(scrimmage), "yards_gained"].sum())
    yards_against = float(dfn.loc[dfn["play_type"].isin(scrimmage), "yards_gained"].sum())
    giveaways = int(off["interception"].fillna(0).sum() + off["fumble_lost"].fillna(0).sum())
    takeaways = int(dfn["interception"].fillna(0).sum() + dfn["fumble_lost"].fillna(0).sum())
    return {
        "yards_for": yards_for if games else None,
        "yards_against": yards_against if games else None,
        "yards_diff_per_game": round((yards_for - yards_against) / games, 1) if games else None,
        "takeaways": takeaways if games else None,
        "giveaways": giveaways if games else None,
        "turnover_diff_per_game": round((takeaways - giveaways) / games, 2) if games else None,
    }


def team_record_through(schedules: pd.DataFrame, season: int, team: str, upto_week: int) -> dict:
    """Wins/losses/points for/against for `team` in `season`, only counting
    completed games (both scores present) strictly before `upto_week`.
    Points are kept for the W/L record; strength comes from yards/turnovers."""
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
    }


def strength_through(schedules: pd.DataFrame, pbp: pd.DataFrame, season: int, team: str, upto_week: int) -> dict:
    return {**team_record_through(schedules, season, team, upto_week),
            **yards_turnovers_through(pbp, season, team, upto_week)}


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

    pbp = load_pbp([prior_season, season])
    team_stats = {}
    for team in playing_teams:
        team_stats[team] = {
            "meta": teams_meta.get(team, {}),
            "current_season_record_before_this_week": strength_through(schedules, pbp, season, team, week),
            "prior_season_full_record": strength_through(schedules, pbp, prior_season, team, upto_week=99),
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
