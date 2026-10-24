"""
1st-quarter matchup projections: strong offense vs. weak defense, from each
team's own season-to-date stats (games before the target week):

  q1_for / q1_against   1st-quarter points scored / allowed per game
  rz_td / rz_td_allowed red-zone TD rate on offense / allowed on defense
                        (a red-zone trip = a drive with a scrimmage snap at
                        or inside the opponent's 20; TD = that drive ends in
                        a rushing/passing TD)

Per side in a matchup (side_features):
  pts_match = (team pts_for + opponent pts_against) / 2      full-game, per game
  q1_match  = (team q1_for + opponent q1_against) / 2
  rz_match  = (team rz_td + opponent rz_td_allowed) / 2 - league rz_td
  q1_pts    = intercept + sum(WEIGHTS[k] x feature) (+ home bonus)
Expected Q1 margin = home q1_pts - away q1_pts. FBS-vs-FBS games are ranked
by the size of that margin (most lopsided matchups first), with the market's
spread-implied Q1 margin (MARKET_Q1_SHARE x full-game spread) alongside.

Weights come from backtest_q1_matchups.py (walk-forward, 2025 wks 4-15 +
2026 wks 4-8, 827 games). Best single stat is full-game scoring (pts_match
r=0.36 with the actual Q1 margin in both seasons), ahead of Q1-only points
(0.30/0.36) and red-zone TD rate (0.11/0.20). Red zone adds nothing once
scoring is in (fitted to a small negative weight), so its weight is 0 and
it's shown as context only. Fit on one season / test on the other: r=0.35-
0.37 (the original equal-weight Q1 + RZ formula: 0.30), vs. the market's
0.41-0.44; where it disagrees with the market, the market was right
(gap r ~0). Top 10 lopsided matchups per week: edge team led 54-62%.

Writes q1_matchups_week{N}_{year}.csv. Backtest: backtest_q1_matchups.py.
"""
import argparse
import collections
import json
import math
import os

import pandas as pd

from build_first_td_picks import week_plays
from cfbd_fetch import cfbd_get, get_current_week

# Q1 points for one side = intercept + sum(weight x feature), features from
# side_features(). Fitted by backtest_q1_matchups.py (OLS on 2025 + 2026
# walk-forward team-games); rerun it to refit.
WEIGHTS = {"intercept": -2.212, "pts_match": 0.234, "q1_match": 0.176, "home": 1.035, "rz_match": 0.0}
MARKET_Q1_SHARE = 0.25
# P(a side leads by X+ after Q1) = 1 / (1 + exp(-(a + b x projected margin))),
# per threshold X. Fitted by backtest_q1_matchups.py alongside WEIGHTS.
LEAD_THRESHOLDS = (7, 10, 14)
TAIL = {7: (-1.147, 0.255), 10: (-2.232, 0.317), 14: (-2.929, 0.388)}


def lead_prob(threshold, margin):
    a, b = TAIL[threshold]
    return 1 / (1 + math.exp(-(a + b * margin)))
MIN_GAMES = 3
TD_TYPES = ("Rushing Touchdown", "Passing Touchdown")
SCRIMMAGE = ("Rush", "Pass Reception", "Pass Incompletion", "Sack", *TD_TYPES, "Fumble Recovery (Own)",
             "Fumble Recovery (Opponent)", "Fumble", "Interception", "Pass Interception Return")


def red_zone(plays):
    """{team: [trips, tds, trips_allowed, tds_allowed]} from a list of plays."""
    drives = {}
    for p in plays:
        d = drives.setdefault(p["driveId"], {"off": p["offense"], "def": p["defense"], "rz": False, "td": False})
        if p["offense"] != d["off"]:
            continue
        ytg = p.get("yardsToGoal")
        if p.get("playType") in SCRIMMAGE and ytg is not None and 0 < ytg <= 20:
            d["rz"] = True
        if p.get("playType") in TD_TYPES:
            d["td"] = True
    out = collections.defaultdict(lambda: [0, 0, 0, 0])
    for d in drives.values():
        if d["rz"]:
            out[d["off"]][0] += 1
            out[d["off"]][1] += d["td"]
            out[d["def"]][2] += 1
            out[d["def"]][3] += d["td"]
    return out


def scoring(games):
    """{team: [games, q1_for, q1_against, pts_for, pts_against]} from completed CFBD games."""
    out = collections.defaultdict(lambda: [0, 0, 0, 0, 0])
    for g in games:
        h, a = g.get("homeLineScores"), g.get("awayLineScores")
        if not (g.get("completed") and h and a and g.get("homePoints") is not None):
            continue
        for team, f, ag, pf, pa in ((g["homeTeam"], h[0], a[0], g["homePoints"], g["awayPoints"]),
                                    (g["awayTeam"], a[0], h[0], g["awayPoints"], g["homePoints"])):
            t = out[team]
            t[0] += 1
            t[1] += f
            t[2] += ag
            t[3] += pf
            t[4] += pa
    return out


def team_table(games, plays):
    """Per-team season-to-date stats from prior games + their plays."""
    rz, sc = red_zone(plays), scoring(games)
    rows = []
    for team, (n, f, ag, pf, pa) in sc.items():
        trips, tds, trips_a, tds_a = rz.get(team, [0, 0, 0, 0])
        rows.append({"team": team, "games": n, "pts_for": pf / n, "pts_against": pa / n,
                     "q1_for": f / n, "q1_against": ag / n,
                     "rz_trips": trips, "rz_td": tds / trips if trips else None,
                     "rz_trips_allowed": trips_a, "rz_td_allowed": tds_a / trips_a if trips_a else None})
    df = pd.DataFrame(rows).set_index("team")
    league_rz = sum(v[1] for v in rz.values()) / max(1, sum(v[0] for v in rz.values()))
    return df, league_rz


def side_features(off, dfn, league_rz, is_home):
    """Matchup features for one side's Q1 points: its offense vs. the opponent's defense."""
    o_rz = off["rz_td"] if pd.notna(off["rz_td"]) else league_rz
    d_rz = dfn["rz_td_allowed"] if pd.notna(dfn["rz_td_allowed"]) else league_rz
    return {"pts_match": (off["pts_for"] + dfn["pts_against"]) / 2,
            "q1_match": (off["q1_for"] + dfn["q1_against"]) / 2,
            "rz_match": (o_rz + d_rz) / 2 - league_rz,
            "home": float(is_home)}


def project(home, away, table, league_rz, neutral=False, weights=WEIGHTS):
    """(home_q1_pts, away_q1_pts) or None if either team lacks MIN_GAMES."""
    if home not in table.index or away not in table.index:
        return None
    h, a = table.loc[home], table.loc[away]
    if h["games"] < MIN_GAMES or a["games"] < MIN_GAMES:
        return None

    def pts(feats):
        return weights["intercept"] + sum(weights[k] * v for k, v in feats.items())

    return (pts(side_features(h, a, league_rz, not neutral)),
            pts(side_features(a, h, league_rz, False)))


def season_inputs(year, week):
    """Completed games and plays from weeks before `week`."""
    games = [g for g in cfbd_get("/games", params={"year": year, "seasonType": "regular"}) if g["week"] < week]
    plays = []
    for w in range(0, week):
        # Last week can still be filling in, so only older weeks come from the cache.
        plays += week_plays(year, w, cache=w < week - 1)
    return games, plays


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--week", type=int, default=None, help="If omitted, auto-detect the upcoming week via CFBD's calendar")
    ap.add_argument("--top", type=int, default=15, help="How many matchups to print")
    args = ap.parse_args()

    year, week = args.year, args.week
    if week is None:
        week = get_current_week(year)
        if week is None:
            raise SystemExit(f"Could not determine the current week for {year} -- pass --week explicitly.")
        print(f"Auto-detected current week: {week}")

    games, plays = season_inputs(year, week)
    table, league_rz = team_table(games, plays)
    slate = cfbd_get("/games", params={"year": year, "week": week, "seasonType": "regular"})

    # Market's spread-implied Q1 margin, for comparison (see backtest_q1.py).
    proj_path = f"week{week}_{year}_projections.csv"
    market = {}
    if os.path.exists(proj_path):
        proj = pd.read_csv(proj_path)
        market = dict(zip(proj["game_id"], MARKET_Q1_SHARE * proj["market_home_margin"]))

    rows = []
    for g in slate:
        if g.get("completed") or g.get("homeClassification") != "fbs" or g.get("awayClassification") != "fbs":
            continue
        p = project(g["homeTeam"], g["awayTeam"], table, league_rz, g["neutralSite"])
        if p is None:
            continue
        h, a = table.loc[g["homeTeam"]], table.loc[g["awayTeam"]]
        rows.append({
            "game_id": g["id"], "start_utc": g["startDate"][:16], "away": g["awayTeam"], "home": g["homeTeam"],
            "neutral": g["neutralSite"], "away_q1_proj": round(p[1], 1), "home_q1_proj": round(p[0], 1),
            "home_q1_margin": round(p[0] - p[1], 1),
            "market_home_q1_margin": round(market[g["id"]], 1) if pd.notna(market.get(g["id"])) else None,
            "home_pts_for": round(h["pts_for"], 1), "home_pts_against": round(h["pts_against"], 1),
            "home_games": int(h["games"]),
            "home_q1_for": round(h["q1_for"], 1), "home_q1_against": round(h["q1_against"], 1),
            "home_rz_td": round(h["rz_td"], 3) if pd.notna(h["rz_td"]) else None,
            "home_rz_td_allowed": round(h["rz_td_allowed"], 3) if pd.notna(h["rz_td_allowed"]) else None,
            "away_pts_for": round(a["pts_for"], 1), "away_pts_against": round(a["pts_against"], 1),
            "away_games": int(a["games"]),
            "away_q1_for": round(a["q1_for"], 1), "away_q1_against": round(a["q1_against"], 1),
            "away_rz_td": round(a["rz_td"], 3) if pd.notna(a["rz_td"]) else None,
            "away_rz_td_allowed": round(a["rz_td_allowed"], 3) if pd.notna(a["rz_td_allowed"]) else None,
        })
    df = pd.DataFrame(rows)
    df["edge_team"] = [r.home if r.home_q1_margin >= 0 else r.away for r in df.itertuples()]
    for t in LEAD_THRESHOLDS:
        df[f"p_lead_{t}"] = [round(lead_prob(t, abs(m)), 3) for m in df["home_q1_margin"]]
    df = df.reindex(df["home_q1_margin"].abs().sort_values(ascending=False).index)
    out_path = f"q1_matchups_week{week}_{year}.csv"
    df.to_csv(out_path, index=False)

    print(f"Week {week}: {len(df)} matchups (league RZ TD rate {league_rz:.1%}) -> {out_path}\n")
    for r in df.head(args.top).itertuples():
        fav_first = r.home_q1_margin >= 0
        (t1, s1), (t2, s2) = ((r.home, r.home_q1_proj), (r.away, r.away_q1_proj)) if fav_first \
            else ((r.away, r.away_q1_proj), (r.home, r.home_q1_proj))
        mkt = "" if pd.isna(r.market_home_q1_margin) else             f"   market {r.market_home_q1_margin * (1 if fav_first else -1):+.1f}"
        print(f"  {t1} {s1:.0f} - {s2:.0f} {t2}   expected margin {abs(r.home_q1_margin):.1f}{mkt}"
              f"   ({r.away} @ {r.home})")


if __name__ == "__main__":
    main()
