"""
1st-quarter margin projections for a week's slate, built on top of that
week's model projections (week{N}_{year}_projections.csv from
build_week_projections.py), the same way build_first_td_picks.py is.

Method: empirical kernel over past games. For each game, every historical
FBS-vs-FBS game is weighted by how close its closing |spread| was to this
game's (Gaussian, bandwidth SPREAD_BW), and the weighted set of real Q1
margins (oriented to the favorite) is the projected distribution. The
market total does not sharpen the margin out of sample (LOSO log loss
0.9852 spread-only vs 0.9858 with total), so it only drives the projected
Q1 total (kernel bandwidths Q1_TOTAL_BW). Using real margins keeps the key numbers (0 / 3 / 7 / 14) and
the ~19% tie rate that a normal curve would smear out.

Inputs are the market spread + total (projections' market_home_margin /
market_total), falling back to the model's own margin + total when a game
has no line. Our model is deliberately NOT blended in: on 2026 wks 1-7
(n=388) the model-vs-market gap had r=-0.006 with the Q1 result beyond what
the spread already implies.

Backtest (backtest_q1.py, 2022-25, 2,998 games, leave-one-season-out):
  - Q1 margin ~= 0.25 x full-game market margin, r=0.40, residual SD 7.7
  - "Fast/slow starter" team tendencies are noise: within-season split-half
    r=0.006, year-over-year r=0.05, in-season rolling r~0 -> not used
  - calibrated (fav-leads 0.456/0.546/0.650 predicted vs 0.447/0.562/0.664
    actual); 2026 out-of-sample predicted ties 18.9% vs 18.6% actual
No 1Q market lines are captured, so there is no ATS test of these numbers --
they are fair prices, to be compared against a book's 1Q line by hand.

Rows for games that have kicked off are locked, so re-runs only rebuild
future games.
"""
import argparse
import datetime
import glob
import json
import os

import numpy as np
import pandas as pd

from cfbd_fetch import cfbd_get, get_current_week

SPREAD_BW = 4.0
TOTAL_BW = None  # None = ignore the total when weighting
Q1_TOTAL_BW = (8.0, 4.0)  # (spread, total) bandwidths for the projected Q1 total
HIST_YEARS = (2022, 2023, 2024, 2025)
PROVIDERS = ("DraftKings", "ESPN Bet", "Bovada", "consensus")
# Favorite 1Q spread lines priced in the output (fav -0.5 == fav leads after Q1).
FAV_LINES = (0.5, 1.5, 2.5, 3.5, 6.5, 7.5)


def history_games(games_files, lines_files):
    """[(year, home_market_margin, total, home_q1, away_q1, week, home, away)] for FBS-vs-FBS regular-season games with a line."""
    games, lines = {}, {}
    for f in games_files:
        games.update({g["id"]: g for g in json.load(open(f, encoding="utf-8"))})
    for f in lines_files:
        lines.update({l["id"]: l for l in json.load(open(f, encoding="utf-8"))})
    out = []
    for gid, g in games.items():
        if not (g.get("homeLineScores") and g.get("awayLineScores")) or g.get("seasonType") != "regular":
            continue
        if g.get("homeClassification") != "fbs" or g.get("awayClassification") != "fbs":
            continue
        ls = [l for l in lines.get(gid, {}).get("lines", []) if l.get("spread") is not None and l.get("overUnder")]
        if not ls:
            continue
        ls.sort(key=lambda l: PROVIDERS.index(l["provider"]) if l["provider"] in PROVIDERS else len(PROVIDERS))
        out.append((g["season"], -ls[0]["spread"], ls[0]["overUnder"], g["homeLineScores"][0], g["awayLineScores"][0],
                    g["week"], g["homeTeam"], g["awayTeam"]))
    return out


def load_history(year):
    """Prior seasons' cached CFBD games/lines plus this season's finished weeks."""
    rows = []
    for y in HIST_YEARS:
        if y < year:
            rows += history_games([f"cfbd_raw/games_{y}.json"], [f"cfbd_raw/lines_{y}.json"])
    rows += history_games(sorted(glob.glob(f"cfbd_raw/games_{year}_wk*_final.json")),
                          sorted(glob.glob(f"cfbd_raw/lines_{year}_wk*_final.json")))
    return np.array([r[1:5] for r in rows], dtype=float)


def q1_distribution(home_margin, total, hist, spread_bw=SPREAD_BW, total_bw=TOTAL_BW):
    """(home-perspective Q1 margins, Q1 totals, normalized weights) for a game with this market margin/total."""
    fav = np.where(hist[:, 0] >= 0, 1.0, -1.0)
    z = np.zeros(len(hist))
    if spread_bw is not None:
        z += ((np.abs(hist[:, 0]) - abs(home_margin)) / spread_bw) ** 2
    if total_bw is not None:
        z += ((hist[:, 1] - total) / total_bw) ** 2
    w = np.exp(-0.5 * z)
    side = 1.0 if home_margin >= 0 else -1.0
    margins = (hist[:, 2] - hist[:, 3]) * fav * side
    return margins, hist[:, 2] + hist[:, 3], w / w.sum()


def american(p):
    if p <= 0 or p >= 1:
        return ""
    return f"{-round(100 * p / (1 - p))}" if p >= 0.5 else f"+{round(100 * (1 - p) / p)}"


def build_rows(proj, starts, hist, built_at):
    rows = []
    for _, r in proj.iterrows():
        if pd.notna(r["market_home_margin"]) and pd.notna(r["market_total"]):
            hm, tot, src = float(r["market_home_margin"]), float(r["market_total"]), "market"
        else:
            hm, tot, src = float(r["model_margin"]), float(r["model_total"]), "model"
        m, _, w = q1_distribution(hm, tot, hist)
        _, t, wt = q1_distribution(hm, tot, hist, *Q1_TOTAL_BW)
        p_home, p_tie, p_away = (w * (m > 0)).sum(), (w * (m == 0)).sum(), (w * (m < 0)).sum()
        fav, dog, sgn = (r["home"], r["away"], 1) if hm >= 0 else (r["away"], r["home"], -1)
        row = {
            "game_id": r["game_id"], "start_utc": starts.get(r["game_id"], ""),
            "game": f"{r['away']} @ {r['home']}", "away": r["away"], "home": r["home"],
            "line_source": src, "home_margin_full": round(hm, 1), "total_full": tot,
            "q1_home_margin": round((w * m).sum(), 2), "q1_total": round((wt * t).sum(), 2),
            "p_home_lead": round(p_home, 3), "p_tie": round(p_tie, 3), "p_away_lead": round(p_away, 3),
            "p_scoreless": round((wt * (t == 0)).sum(), 3),
            "fair_home_3way": american(p_home), "fair_tie_3way": american(p_tie), "fair_away_3way": american(p_away),
            "favorite": fav, "underdog": dog,
        }
        fav_m = m * sgn
        for line in FAV_LINES:
            p = (w * (fav_m > line)).sum()
            row[f"p_fav_-{line}"] = round(p, 3)
            row[f"fair_fav_-{line}"] = american(p)
            row[f"fair_dog_+{line}"] = american(1 - p)
        row["built_at"] = built_at
        rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--week", type=int, default=None, help="If omitted, auto-detect the upcoming week via CFBD's calendar")
    args = ap.parse_args()

    year, week = args.year, args.week
    if week is None:
        week = get_current_week(year)
        if week is None:
            raise SystemExit(f"Could not determine the current week for {year} -- pass --week explicitly.")
        print(f"Auto-detected current week: {week}")

    proj_path = f"week{week}_{year}_projections.csv"
    if not os.path.exists(proj_path):
        print(f"{proj_path} not built yet -- no Q1 projections for week {week} until it is.")
        return
    out_path = f"q1_projections_week{week}_{year}.csv"

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M")
    games = cfbd_get("/games", params={"year": year, "week": week, "seasonType": "regular"})
    starts = {g["id"]: g["startDate"][:16] for g in games}

    locked = pd.DataFrame()
    if os.path.exists(out_path):
        prev = pd.read_csv(out_path, dtype=str)
        locked = prev[prev["start_utc"] <= now]
        locked = locked.assign(game_id=locked["game_id"].astype(int))

    proj = pd.read_csv(proj_path)
    proj = proj[~proj["game_id"].isin(locked["game_id"] if len(locked) else [])]
    proj = proj[proj["game_id"].map(lambda g: starts.get(g, "") > now)]

    hist = load_history(year)
    new = pd.DataFrame(build_rows(proj, starts, hist, now))
    df = pd.concat([locked, new], ignore_index=True).sort_values(["start_utc", "game"])
    df.to_csv(out_path, index=False)

    print(f"Week {week}: {len(df)} games ({len(locked)} locked, {len(new)} rebuilt; {len(hist)} history games) -> {out_path}")
    if len(new):
        pd.set_option("display.width", 200)
        print(new.sort_values(["start_utc", "game"])[["start_utc", "game", "home_margin_full", "q1_home_margin", "p_home_lead", "p_tie",
                   "p_away_lead", "fair_fav_-0.5", "fair_dog_+0.5"]].to_string(index=False))


if __name__ == "__main__":
    main()
