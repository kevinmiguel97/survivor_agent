"""Load/save/update data/state.json — the single source of truth for the
user's own survivor picks, results, and pool status."""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = REPO_ROOT / "data" / "state.json"


def default_state(season: int) -> dict:
    return {
        "season": season,
        "current_week": 1,
        "status": "alive",
        "mistake_count": 0,
        "picks": [],
    }


def load_state() -> dict:
    if not STATE_PATH.exists():
        raise FileNotFoundError(
            f"{STATE_PATH} does not exist yet. Create one (see README) before running this."
        )
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
        f.write("\n")


def used_teams(state: dict) -> set[str]:
    return {p["team"] for p in state["picks"] if p.get("team")}


def record_pick(state: dict, week: int, team: str, opponent: str, home_away: str,
                 win_prob_estimate: float | None = None) -> dict:
    """Record a pick for a week (result starts 'pending'). Overwrites any
    existing entry for that week so re-running a pick before kickoff is safe."""
    state["picks"] = [p for p in state["picks"] if p["week"] != week]
    state["picks"].append({
        "week": week,
        "team": team,
        "opponent": opponent,
        "home_away": home_away,
        "result": "pending",
        "win_prob_estimate": win_prob_estimate,
    })
    state["picks"].sort(key=lambda p: p["week"])
    return state


def record_result(state: dict, week: int, result: str) -> dict:
    """result: 'win' or 'loss'. Updates status/mistake_count and advances
    current_week."""
    if result not in ("win", "loss"):
        raise ValueError("result must be 'win' or 'loss'")

    entry = next((p for p in state["picks"] if p["week"] == week), None)
    if entry is None:
        raise ValueError(f"No pick recorded for week {week} yet — record the pick first.")
    entry["result"] = result

    if result == "loss":
        state["mistake_count"] += 1
        state["status"] = "eliminated"

    if week >= state["current_week"]:
        state["current_week"] = week + 1

    return state


def _cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Manage data/state.json")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="Create a fresh state.json")
    p_init.add_argument("--season", type=int, required=True)

    sub.add_parser("show", help="Print the current state as JSON")

    p_pick = sub.add_parser("record-pick", help="Record this week's pick (result=pending)")
    p_pick.add_argument("--week", type=int, required=True)
    p_pick.add_argument("--team", required=True)
    p_pick.add_argument("--opponent", required=True)
    p_pick.add_argument("--home-away", choices=["home", "away"], required=True)
    p_pick.add_argument("--win-prob", type=float, default=None)

    p_result = sub.add_parser("record-result", help="Record the outcome of a picked week")
    p_result.add_argument("--week", type=int, required=True)
    p_result.add_argument("--result", choices=["win", "loss"], required=True)

    args = parser.parse_args()

    if args.cmd == "init":
        if STATE_PATH.exists():
            raise SystemExit(f"{STATE_PATH} already exists — refusing to overwrite.")
        save_state(default_state(args.season))
        print(f"Created {STATE_PATH}")
        return

    state = load_state()

    if args.cmd == "show":
        print(json.dumps(state, indent=2))
        return

    if args.cmd == "record-pick":
        state = record_pick(state, args.week, args.team, args.opponent, args.home_away, args.win_prob)
    elif args.cmd == "record-result":
        state = record_result(state, args.week, args.result)

    save_state(state)
    print(json.dumps(state, indent=2))


if __name__ == "__main__":
    _cli()
