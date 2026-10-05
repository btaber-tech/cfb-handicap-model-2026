"""
Out-of-sample check of the "3+ pt edge on the HOME side" ATS split found in
the 2026 weeks 1-5 scorecard (43-36-3, 54.4% -- found by slicing after the
fact, so it needs testing on games it wasn't picked from).

Rebuilds a historical replica of the live model for 2023-2025, all regular-
season FBS-vs-FBS weeks, no lookahead:
  - preseason_diff = avg of prior-season final SP+ and FPI diffs (the live
    model also averages in Steele + the bottom-up model; neither exists
    historically, so this is a 2-source approximation)
  - in_season_diff = one-pass SRS anchored on preseason ratings, built only
    from games completed in weeks strictly before the game's week (same
    method as build_in_season_ratings.py)
  - model_margin = (1-w)*preseason + w*in_season + HFA, same in_season_weight
    schedule and HFA constants as build_week_projections.py
Graded against the median closing spread and the median opening spread.

Usage:
    python build_home_edge_backtest.py
"""
import json

import numpy as np
import pandas as pd

from build_week_projections import ALTITUDE_TEAMS, HFA_ALTITUDE, HFA_BASE, HFA_NEUTRAL, in_season_weight

SEASONS = [2023, 2024, 2025]
EDGE_MIN = 3.0


def hfa_for(home, neutral):
    if neutral:
        return HFA_NEUTRAL
    return HFA_ALTITUDE if home in ALTITUDE_TEAMS else HFA_BASE


trans = pd.read_csv("backtest_transitions.csv")
sp_lookup = trans.set_index(["season", "team"])["prior_sp_rating"].to_dict()

rows = []
for season in SEASONS:
    fpi_prior = {r["team"]: r["fpi"] for r in json.load(open(f"cfbd_raw/fpi_{season - 1}.json", encoding="utf-8"))}
    games = [g for g in json.load(open(f"cfbd_raw/games_{season}.json", encoding="utf-8"))
             if g["seasonType"] == "regular" and g["completed"]
             and g["homeClassification"] == "fbs" and g["awayClassification"] == "fbs"
             and g.get("homePoints") is not None]
    lines_by_id = {l["id"]: l.get("lines", []) for l in json.load(open(f"cfbd_raw/lines_{season}.json", encoding="utf-8"))}

    def pre(team):
        vals = [v for v in (sp_lookup.get((season, team)), fpi_prior.get(team)) if v is not None and pd.notna(v)]
        return float(np.mean(vals)) if vals else None

    for week in sorted({g["week"] for g in games}):
        # one-pass SRS from games before this week
        implied = {}
        for g in games:
            if g["week"] >= week:
                continue
            h, a = g["homeTeam"], g["awayTeam"]
            ph, pa = pre(h), pre(a)
            if ph is None or pa is None:
                continue
            net = g["homePoints"] - g["awayPoints"] - hfa_for(h, g.get("neutralSite"))
            implied.setdefault(h, []).append(net + pa)
            implied.setdefault(a, []).append(-net + ph)
        in_season = {t: float(np.mean(v)) for t, v in implied.items()}
        w = in_season_weight(week)

        for g in (g for g in games if g["week"] == week):
            h, a = g["homeTeam"], g["awayTeam"]
            ph, pa = pre(h), pre(a)
            if ph is None or pa is None:
                continue
            core = ph - pa
            if w > 0 and h in in_season and a in in_season:
                core = (1 - w) * core + w * (in_season[h] - in_season[a])
            model = core + hfa_for(h, g.get("neutralSite"))

            gl = lines_by_id.get(g["id"], [])
            close = [l["spread"] for l in gl if l.get("spread") is not None]
            opn = [l["spreadOpen"] for l in gl if l.get("spreadOpen") is not None]
            rows.append({
                "season": season, "week": week, "home": h, "away": a,
                "neutral": bool(g.get("neutralSite")),
                "model_margin": model,
                "actual_margin": g["homePoints"] - g["awayPoints"],
                "market_close": -float(np.median(close)) if close else np.nan,
                "market_open": -float(np.median(opn)) if opn else np.nan,
            })

df = pd.DataFrame(rows)
df.to_csv("home_edge_backtest_games.csv", index=False)


def grade(sub, mkt):
    s = sub.dropna(subset=[mkt])
    pick_home = s.model_margin > s[mkt]
    home_cov = s.actual_margin > s[mkt]
    push = s.actual_margin == s[mkt]
    win = (pick_home == home_cov) & ~push
    w, l, p = int(win.sum()), int((~win & ~push).sum()), int(push.sum())
    pct = w / (w + l) if w + l else float("nan")
    return f"{w}-{l}-{p} ({pct:.1%})"


print(f"Replica games graded: {len(df)} (2023-2025, FBS v FBS regular season)\n")
for mkt in ["market_close", "market_open"]:
    d = df.dropna(subset=[mkt]).copy()
    d["edge"] = d.model_margin - d[mkt]  # + = model on home side
    d["home_fav"] = d[mkt] > 0
    print(f"=== vs {mkt} ===")
    big = d[d.edge.abs() >= EDGE_MIN]
    home, away = big[big.edge > 0], big[big.edge < 0]
    print(f"  3+ edge, model on HOME:   {grade(home, mkt)}")
    print(f"      home is market fav:   {grade(home[home.home_fav], mkt)}")
    print(f"      home is market dog:   {grade(home[~home.home_fav], mkt)}")
    print(f"  3+ edge, model on AWAY:   {grade(away, mkt)}")
    print(f"  <3 edge (any side):       {grade(d[d.edge.abs() < EDGE_MIN], mkt)}")
    print(f"  home 3+, non-neutral only: {grade(home[~home.neutral], mkt)}")
    for s in SEASONS:
        print(f"    {s} home 3+: {grade(home[home.season == s], mkt)}   away 3+: {grade(away[away.season == s], mkt)}")
    print(f"    weeks 1-5 only, home 3+: {grade(home[home.week <= 5], mkt)}   weeks 6+: {grade(home[home.week > 5], mkt)}")
    print()
