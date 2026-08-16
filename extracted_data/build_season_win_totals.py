"""
Season win-total projection engine.

For every FBS team, projects a probability for EACH game on its full
regular-season schedule (reusing the same blended-margin + tiered-HFA +
normal-CDF formula as build_week_projections.py -- 4 point-scale sources:
SP+, FPI, the bottom-up model, and Phil Steele's Power Poll rescaled to
points, equal-weighted), then combines those per-game probabilities into
a full win-count distribution via the exact Poisson-binomial pmf
(independent, non-identical Bernoulli trials -- this is the textbook way
to turn a list of game-by-game win probabilities into a season win total
distribution, not just a mean).

Conventions matched to how sportsbooks post win-total futures: regular
season only (excludes conference championship games and bowls), FCS/lower-
division "buy games" included using an empirically-derived opponent
strength proxy (see FCS_PROXY_RATING below) rather than dropped, since
those games count toward the total same as any other.

FCS_PROXY_RATING derivation (see task notes / memory): regressed actual
FBS-vs-FCS margins (2022-2025, n=485 games) against the FBS team's own
SP+ and FPI ratings for that season, holding HFA fixed. Both scales
independently implied an opponent rating of about -28.6 to -28.9 (FBS
teams beat FCS opponents by ~31 points on average, ~95.5% of the time)
-- close enough to treat as one shared constant across scales.

Usage:
    python build_season_win_totals.py --year 2026
    python build_season_win_totals.py --year 2026 --skip-fetch   # reuse cfbd_raw/games_{year}_full.json
"""
import argparse
import json
import math
import os

import pandas as pd

from cfbd_fetch import cfbd_get_save
from market_win_totals import LINES_2026, MARKET_TO_INTERNAL

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
    "Hawaii": "Hawai'i",
}

HFA_BASE = 2.9
HFA_NEUTRAL = 1.8
HFA_ALTITUDE = 6.0
ALTITUDE_TEAMS = {"Air Force", "BYU", "Colorado", "Colorado State", "New Mexico", "Utah", "Wyoming"}
SIGMA = 18.4
FCS_PROXY_RATING = -28.7  # see module docstring; applied on the sp_plus/fpi/model_proj_margin_2026/steele_margin scales alike


def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def poisson_binomial_pmf(probs):
    """Exact win-count distribution for n independent, non-identical Bernoulli trials.
    Returns a list pmf[k] = P(exactly k wins), k=0..len(probs)."""
    pmf = [1.0]
    for p in probs:
        new_pmf = [0.0] * (len(pmf) + 1)
        for k, prob_k in enumerate(pmf):
            new_pmf[k] += prob_k * (1 - p)
            new_pmf[k + 1] += prob_k * p
        pmf = new_pmf
    return pmf


def fair_line(pmf):
    """The X.5 win total where P(over) and P(under) are as close to 50/50 as the
    discrete distribution allows -- i.e. sportsbook-style half-point line."""
    cum = 0.0
    for k, p in enumerate(pmf):
        cum += p
        if cum >= 0.5:
            return k - 0.5
    return len(pmf) - 1 - 0.5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--skip-fetch", action="store_true")
    args = ap.parse_args()
    year = args.year

    games_path = f"cfbd_raw/games_{year}_full.json"
    os.makedirs("cfbd_raw", exist_ok=True)
    if args.skip_fetch and os.path.exists(games_path):
        print(f"--skip-fetch: reusing {games_path}")
    else:
        print(f"Pulling full {year} regular-season schedule from CFBD...")
        cfbd_get_save("/games", games_path, params={"year": year, "seasonType": "regular"})

    games = json.load(open(games_path, encoding="utf-8"))

    pr = pd.read_csv("cfb_2026_power_ratings.csv")
    # Phil Steele's Power Poll (1-138 ordinal rank) -> a point-scale value
    # comparable to sp_plus/fpi/model_proj_margin_2026, same treatment as
    # build_week_projections.py: z-score across all 138 teams, rescale by
    # SP+'s own std dev.
    steele_score = 139 - pr["steele_power_poll_rank"]
    steele_z = (steele_score - steele_score.mean()) / steele_score.std()
    pr["steele_margin"] = steele_z * pr["sp_plus"].std()
    pr_lookup = pr.set_index("team")[
        ["sp_plus", "fpi", "model_proj_margin_2026", "steele_margin"]
    ].to_dict("index")
    conf_lookup = pr.set_index("team")["conference"].to_dict()
    rank_lookup = pr.set_index("team")["blended_rank"].to_dict()

    def resolve(cfbd_name):
        key = CFBD_TO_ATHLON.get(cfbd_name, cfbd_name)
        return pr_lookup.get(key)

    def team_ratings(name, is_fbs):
        if is_fbs:
            r = resolve(name)
            if r is None:
                return None
            return r
        return {"sp_plus": FCS_PROXY_RATING, "fpi": FCS_PROXY_RATING,
                "model_proj_margin_2026": FCS_PROXY_RATING, "steele_margin": FCS_PROXY_RATING}

    # Per-team list of (opponent, is_home, is_neutral, win_prob_for_this_team)
    team_games = {t: [] for t in pr["team"]}
    unmatched = set()

    for g in games:
        home, away = g["homeTeam"], g["awayTeam"]
        home_fbs = g["homeClassification"] == "fbs"
        away_fbs = g["awayClassification"] == "fbs"
        if not (home_fbs or away_fbs):
            continue  # neither side FBS, irrelevant

        hr = team_ratings(home, home_fbs)
        ar = team_ratings(away, away_fbs)
        if home_fbs and hr is None:
            unmatched.add(home)
        if away_fbs and ar is None:
            unmatched.add(away)
        if hr is None or ar is None:
            continue

        diffs = []
        for col in ["sp_plus", "fpi", "model_proj_margin_2026", "steele_margin"]:
            if pd.notna(hr[col]) and pd.notna(ar[col]):
                diffs.append(hr[col] - ar[col])
        if not diffs:
            continue
        avg_diff = sum(diffs) / len(diffs)

        neutral = g.get("neutralSite", False)
        if neutral:
            hfa = HFA_NEUTRAL
        elif home in ALTITUDE_TEAMS:
            hfa = HFA_ALTITUDE
        else:
            hfa = HFA_BASE
        model_margin = avg_diff + hfa  # positive = home favored
        home_wp = norm_cdf(model_margin / SIGMA)

        if home_fbs:
            key = CFBD_TO_ATHLON.get(home, home)
            if key in team_games:
                team_games[key].append({"opponent": away, "home_away": "neutral" if neutral else "home",
                                         "win_prob": round(home_wp, 4)})
        if away_fbs:
            key = CFBD_TO_ATHLON.get(away, away)
            if key in team_games:
                team_games[key].append({"opponent": home, "home_away": "neutral" if neutral else "away",
                                         "win_prob": round(1 - home_wp, 4)})

    if unmatched:
        print("UNMATCHED TEAM NAMES (no power rating found):", sorted(unmatched))

    rows = []
    for team, glist in team_games.items():
        if not glist:
            rows.append({"team": team, "games_scheduled": 0})
            continue
        probs = [g["win_prob"] for g in glist]
        pmf = poisson_binomial_pmf(probs)
        expected_wins = sum(probs)
        variance = sum(p * (1 - p) for p in probs)
        cum = 0.0
        p10 = p25 = p50 = p75 = p90 = None
        for k, p in enumerate(pmf):
            cum += p
            if p10 is None and cum >= 0.10:
                p10 = k
            if p25 is None and cum >= 0.25:
                p25 = k
            if p50 is None and cum >= 0.50:
                p50 = k
            if p75 is None and cum >= 0.75:
                p75 = k
            if p90 is None and cum >= 0.90:
                p90 = k
        rows.append({
            "team": team,
            "conference": conf_lookup.get(team),
            "blended_rank": rank_lookup.get(team),
            "games_scheduled": len(glist),
            "expected_wins": round(expected_wins, 2),
            "stdev_wins": round(variance ** 0.5, 2),
            "fair_win_line": fair_line(pmf),
            "p10_wins": p10, "p25_wins": p25, "median_wins": p50, "p75_wins": p75, "p90_wins": p90,
            "prob_win_pct_avg": round(expected_wins / len(glist), 3),
        })

    df = pd.DataFrame(rows).sort_values("expected_wins", ascending=False)

    # Merge in web-sourced DraftKings/consensus preseason win-total lines
    # (market_win_totals.py) for the artifact's market-comparison columns.
    # Only defined for 2026 currently; other years silently get NaN, same
    # as build_win_totals_edge_test.py's historical backtest handling.
    if year == 2026:
        lines = LINES_2026

        def lookup(team):
            if team in lines:
                return lines[team]
            for market_name, internal_name in MARKET_TO_INTERNAL.items():
                if internal_name == team and market_name in lines:
                    return lines[market_name]
            # Market names generally follow CFBD's spelling, not Athlon's
            # (e.g. "Miami" not "Miami (Fla.)") -- reuse the same alias
            # map used throughout this pipeline, in reverse.
            for cfbd_name, athlon_name in CFBD_TO_ATHLON.items():
                if athlon_name == team and cfbd_name in lines:
                    return lines[cfbd_name]
            return None

        df["market_line"] = df["team"].apply(lookup)
        df["model_gap"] = df["expected_wins"] - df["market_line"]

    out_path = f"season_win_totals_{year}.csv"
    df.to_csv(out_path, index=False)
    print(f"\n{len(df)} teams projected, saved to {out_path}")
    print(df.head(15).to_string(index=False))
    zero = df[df["games_scheduled"].fillna(0) < 10]
    if not zero.empty:
        print("\nWARNING -- teams with an incomplete/missing schedule:")
        print(zero.to_string(index=False))


if __name__ == "__main__":
    main()
