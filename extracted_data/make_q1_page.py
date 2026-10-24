"""
Render q1_matchups_week{N}_{year}.csv (from build_q1_matchups.py) into the
Q1 Edge Board page, q1_matchups_week{N}_{year}.html, using q1_page_tpl.html.

BACKTEST holds the numbers shown in the page's method section; they come
from backtest_q1_matchups.py and should be updated whenever WEIGHTS are refit.
"""
import argparse
import datetime
import json
import os

import pandas as pd

from build_q1_matchups import WEIGHTS
from cfbd_fetch import get_current_week

BACKTEST = {
    "corr": [
        {"label": "Market spread", "y2025": 0.411, "y2026": 0.440},
        {"label": "Season scoring", "y2025": 0.355, "y2026": 0.366},
        {"label": "Q1 scoring", "y2025": 0.295, "y2026": 0.364},
        {"label": "Red-zone TD %", "y2025": 0.106, "y2026": 0.202},
    ],
    "models": [
        {"label": "This board (weighted)", "r": "0.35–0.37"},
        {"label": "Equal-weight Q1 + red zone", "r": "0.30"},
        {"label": "Market spread", "r": "0.41–0.44"},
    ],
    "base": {"7": "26%", "10": "12%", "14": "7%"},
    "top_led": "54–62%",
    "top_tied": "15–23%",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--week", type=int, default=None, help="If omitted, auto-detect the upcoming week via CFBD's calendar")
    args = ap.parse_args()
    if args.week is None:
        args.week = get_current_week(args.year)
        if args.week is None:
            raise SystemExit(f"Could not determine the current week for {args.year} -- pass --week explicitly.")

    csv_path = f"q1_matchups_week{args.week}_{args.year}.csv"
    if not os.path.exists(csv_path):
        print(f"{csv_path} not built yet -- run build_q1_matchups.py first.")
        return
    df = pd.read_csv(csv_path)
    games = json.loads(df.to_json(orient="records"))
    data = {"games": games, "weights": WEIGHTS}

    built = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = open("q1_page_tpl.html", encoding="utf-8").read()
    for key, val in {"__DATA__": json.dumps(data), "__BACKTEST__": json.dumps(BACKTEST),
                     "__WEEK__": str(args.week), "__PREVWEEK__": str(args.week - 1),
                     "__YEAR__": str(args.year), "__BUILT__": built}.items():
        html = html.replace(key, val)
    out_path = f"q1_matchups_week{args.week}_{args.year}.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"{len(games)} matchups -> {out_path}")


if __name__ == "__main__":
    main()
