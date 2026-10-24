"""
Grade every q1_projections_week{N}_{year}.csv (from build_q1_projections.py)
against CFBD's quarter line scores, writing q1_scorecard_{year}.csv.

Per game: actual Q1 score and margin, which 3-way outcome hit, the
probability the model gave it, log loss, and whether the favorite -0.5 /
underdog +0.5 side hit. The summary compares predicted vs. actual rates --
the honest test of fair prices with no 1Q market lines to grade against.
"""
import argparse
import glob
import math
import re

import pandas as pd

from cfbd_fetch import cfbd_get


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    args = ap.parse_args()
    year = args.year

    rows = []
    for path in sorted(glob.glob(f"q1_projections_week*_{year}.csv"),
                       key=lambda p: int(re.search(r"week(\d+)_", p).group(1))):
        week = int(re.search(r"week(\d+)_", path).group(1))
        proj = pd.read_csv(path)
        games = {g["id"]: g for g in cfbd_get("/games", params={"year": year, "week": week, "seasonType": "regular"})}
        for _, r in proj.iterrows():
            g = games.get(r["game_id"])
            if not g or not g.get("completed") or not g.get("homeLineScores") or not g.get("awayLineScores"):
                continue
            hq, aq = g["homeLineScores"][0], g["awayLineScores"][0]
            margin = hq - aq
            outcome = "home" if margin > 0 else "away" if margin < 0 else "tie"
            p_hit = r[f"p_{outcome}_lead" if outcome != "tie" else "p_tie"]
            fav_margin = margin if r["favorite"] == r["home"] else -margin
            rows.append({
                "week": week, "game_id": r["game_id"], "game": r["game"], "favorite": r["favorite"],
                "line_source": r["line_source"], "home_margin_full": r["home_margin_full"],
                "q1_home_margin_proj": r["q1_home_margin"], "home_q1": hq, "away_q1": aq, "q1_margin": margin,
                "outcome": outcome, "p_home_lead": r["p_home_lead"], "p_tie": r["p_tie"],
                "p_away_lead": r["p_away_lead"], "p_outcome": p_hit,
                "log_loss": round(-math.log(max(p_hit, 1e-6)), 4),
                "p_fav_-0.5": r["p_fav_-0.5"], "fav_-0.5_hit": fav_margin > 0, "dog_+0.5_hit": fav_margin <= 0,
                "q1_total_proj": r["q1_total"], "q1_total": hq + aq,
            })

    df = pd.DataFrame(rows)
    out_path = f"q1_scorecard_{year}.csv"
    df.to_csv(out_path, index=False)
    if df.empty:
        print(f"No finished games to grade yet -> {out_path}")
        return

    def summary(d, label):
        print(f"  {label}: {len(d)} games | log loss {d['log_loss'].mean():.3f} | "
              f"fav leads {d['fav_-0.5_hit'].mean():.1%} (pred {d['p_fav_-0.5'].mean():.1%}) | "
              f"tie {(d['outcome'] == 'tie').mean():.1%} (pred {d['p_tie'].mean():.1%}) | "
              f"margin MAE {(d['q1_margin'] - d['q1_home_margin_proj']).abs().mean():.2f}")

    print(f"Graded {len(df)} games -> {out_path}")
    for week, d in df.groupby("week"):
        summary(d, f"week {week}")
    summary(df, "season")


if __name__ == "__main__":
    main()
