"""
Capture a timestamped snapshot of current CFBD betting lines for the
current (or given) week, appending to a running log.

Why this exists: CFBD's /lines endpoint only ever returns each book's
*current* spread/total/moneyline (plus a single "opening" value) -- no
intraday history. There's no line-movement / CLV data source in this
project yet (see [[cfb-handicap-model-2026]] memory). Rather than pay for
a historical odds API, we build our own movement history for free by
polling CFBD's current-lines endpoint several times a day and logging
each pull with a timestamp. Over a season this becomes exactly the kind
of timestamped multi-snapshot dataset a CLV/steam-detection backtest
needs -- just CFBD-native, accumulated in real time instead of bought.

Usage:
    python capture_line_snapshots.py --year 2026 [--week N]
    (omits --week to auto-detect the current week via /calendar, same as
    build_week_projections.py)

Output: appends rows to line_snapshots_2026.csv (created if missing).
One row per (game, provider, snapshot). Safe to run many times a day --
every run just appends new rows, nothing is overwritten or deduplicated
at capture time (dedup/analysis happens downstream, at backtest time).
"""
import argparse
import csv
import datetime
import os

from cfbd_fetch import cfbd_get, get_current_week

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

FIELDS = [
    "snapshot_time_utc", "year", "week", "game_id", "start_date",
    "home_team", "away_team", "provider",
    "spread", "spread_open", "over_under", "over_under_open",
    "home_moneyline", "away_moneyline",
]


def capture(year, week, out_path):
    games = cfbd_get("/lines", params={"year": year, "week": week, "seasonType": "regular"})
    snapshot_time = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

    rows = []
    for g in games:
        for line in g.get("lines", []):
            rows.append({
                "snapshot_time_utc": snapshot_time,
                "year": year,
                "week": week,
                "game_id": g["id"],
                "start_date": g.get("startDate"),
                "home_team": g.get("homeTeam"),
                "away_team": g.get("awayTeam"),
                "provider": line.get("provider"),
                "spread": line.get("spread"),
                "spread_open": line.get("spreadOpen"),
                "over_under": line.get("overUnder"),
                "over_under_open": line.get("overUnderOpen"),
                "home_moneyline": line.get("homeMoneyline"),
                "away_moneyline": line.get("awayMoneyline"),
            })

    file_exists = os.path.exists(out_path)
    with open(out_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)

    return len(games), len(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--week", type=int, default=None)
    args = parser.parse_args()

    week = args.week
    if week is None:
        week = get_current_week(args.year)
        if week is None:
            print(f"could not determine current week for year={args.year} "
                  "(calendar not published yet, or season is over) -- nothing to capture")
            return

    out_path = os.path.join(SCRIPT_DIR, f"line_snapshots_{args.year}.csv")
    n_games, n_rows = capture(args.year, week, out_path)
    print(f"year={args.year} week={week} games_with_lines={n_games} rows_appended={n_rows} -> {out_path}")


if __name__ == "__main__":
    main()
