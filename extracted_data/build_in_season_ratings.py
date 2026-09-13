"""
Builds an in-season, SRS-style power rating from actual 2026 results played
so far, to be blended into the live weekly formula (build_week_projections.py)
per the "preseason priors should decay in favor of in-season efficiency"
design decision in project memory (cfb-handicap-model-2026).

Method: one-pass SRS bootstrapped off the preseason blend (not iterative --
with only a couple of games per team so far, iterating to convergence would
just amplify small-sample noise). For every completed FBS-vs-FBS game:

    implied_rating(team) = (team's own margin in that game, net of HFA)
                            + opponent's PRESEASON points-scale rating

...averaged across all of a team's games played to date. This is exactly
the standard one-iteration Simple Rating System calculation, using the
existing 4-source preseason blend (sp_plus/fpi/bottom-up/Steele, points-
scale) as the opponent-strength prior instead of raw win-margin averages
(which would be nonsense with n=1-2 games and no opponent adjustment at
all). A team that beat good opponents by more than expected gets an
implied rating above its preseason number; a team that struggled against
weak opponents gets pulled down -- exactly the in-season signal that's
currently completely absent from the live formula.

Output: in_season_ratings_2026.csv (team, games_played, in_season_margin_2026).
NOT itself backtested yet (no historical seasons of "in-season SRS vs.
preseason blend" have been run through the same pipeline) -- treat as a
reasonable, standard method applied fresh, to be checked against real
results as the season progresses, same as the rest of the model.

Usage:
    python build_in_season_ratings.py --year 2026 --through-week 2
"""
import argparse
import json
import os

import pandas as pd

from cfbd_fetch import cfbd_get_save

HFA_BASE = 2.9
HFA_NEUTRAL = 1.8
HFA_ALTITUDE = 6.0
ALTITUDE_TEAMS = {"Air Force", "BYU", "Colorado", "Colorado State", "New Mexico", "Utah", "Wyoming"}

CFBD_TO_ATHLON = {
    "California": "Cal",
    "Miami": "Miami (Fla.)",
    "Pittsburgh": "Pitt",
    "Florida International": "FIU",
    "Western Kentucky": "WKU",
    "Miami (OH)": "Miami (Ohio)",
    "Massachusetts": "UMass",
    "San José State": "San Jose State",
    "App State": "Appalachian State",
    "UL Monroe": "ULM",
}

PRESEASON_COLS = ["sp_plus", "fpi", "model_proj_margin_2026_scaled", "steele_margin_scaled"]


def hfa_for(home, neutral):
    if neutral:
        return HFA_NEUTRAL
    if home in ALTITUDE_TEAMS:
        return HFA_ALTITUDE
    return HFA_BASE


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--through-week", type=int, required=True,
                     help="Last completed week to include (e.g. 2 after weeks 1-2 are in the books)")
    ap.add_argument("--skip-fetch", action="store_true")
    args = ap.parse_args()

    year, through_week = args.year, args.through_week

    pr = pd.read_csv("cfb_2026_power_ratings.csv")
    pr["preseason_points"] = pr[PRESEASON_COLS].mean(axis=1, skipna=True)
    preseason_lookup = pr.set_index("team")["preseason_points"].to_dict()

    def resolve(cfbd_name):
        return CFBD_TO_ATHLON.get(cfbd_name, cfbd_name)

    samples = {}  # team -> list of implied ratings
    for week in range(1, through_week + 1):
        games_path = f"cfbd_raw/games_{year}_wk{week}.json"
        os.makedirs("cfbd_raw", exist_ok=True)
        if not (args.skip_fetch and os.path.exists(games_path)):
            print(f"Pulling {year} week {week} games from CFBD...")
            cfbd_get_save("/games", games_path, params={"year": year, "week": week, "seasonType": "regular"})
        games = json.load(open(games_path, encoding="utf-8"))

        for g in games:
            if not g.get("completed") or g.get("homePoints") is None or g.get("awayPoints") is None:
                continue
            if g["homeClassification"] != "fbs" or g["awayClassification"] != "fbs":
                continue  # only FBS-vs-FBS: no preseason rating exists for the other side

            home, away = resolve(g["homeTeam"]), resolve(g["awayTeam"])
            home_pre, away_pre = preseason_lookup.get(home), preseason_lookup.get(away)
            if pd.isna(home_pre) or pd.isna(away_pre):
                continue

            hfa = hfa_for(home, g.get("neutralSite", False))
            home_margin = g["homePoints"] - g["awayPoints"]
            away_margin = -home_margin

            samples.setdefault(home, []).append((home_margin - hfa) + away_pre)
            samples.setdefault(away, []).append((away_margin + hfa) + home_pre)

    rows = [
        {"team": team, "games_played": len(vals), "in_season_margin_2026": round(sum(vals) / len(vals), 2)}
        for team, vals in samples.items()
    ]
    out = pd.DataFrame(rows).sort_values("in_season_margin_2026", ascending=False)
    out_path = "in_season_ratings_2026.csv"
    out.to_csv(out_path, index=False)
    print(f"\n{len(out)} teams with in-season ratings through week {through_week}, saved to {out_path}")
    print(out.head(10).to_string(index=False))
    print("...")
    print(out.tail(5).to_string(index=False))


if __name__ == "__main__":
    main()
