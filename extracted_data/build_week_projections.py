"""
Generalized weekly projection builder (supersedes build_week1_projections.py,
which stays in place as the one-off record of the Week 0/1 opener run).
Pulls a target week's games/lines from CFBD, applies the 2026 power ratings,
and writes week{N}_{year}_projections.csv / _fbs_vs_other.csv -- the inputs
build_artifact.py turns into the published artifact.

Usage:
    python build_week_projections.py --year 2026            # auto-detect the upcoming week
    python build_week_projections.py --year 2026 --week 3   # explicit week
    python build_week_projections.py --year 2026 --week 3 --skip-fetch  # reuse existing cfbd_raw/ JSON

For each FBS-vs-FBS game:
  - model_margin = avg of available point-scale ratings diffs (SP+, FPI,
    bottom-up model_proj_margin_2026, Phil Steele's Power Poll rescaled to
    points -- see STEELE_POINT_SCALE below), home minus away, plus a
    home-field adjustment. Steele's Power Poll was added at the user's
    request that his opinion carry more weight than Athlon's (which has
    no numeric weight here or in cfb_2026_power_ratings.csv -- comparison
    column only). This 4th-source addition is NOT separately backtested
    (the ~76% SU accuracy figure in cfb-backtest-findings-2026 was
    measured on the 3-source SP+/FPI/bottom-up version); it's a reasonable
    extension since Steele's Power Poll is itself a talent composite like
    SP+/FPI, not an opinion piece, but treat post-integration accuracy as
    unverified until re-backtested.
  - win prob from a normal CDF on that margin with sigma=SIGMA.
  - market_margin, if a line exists yet, shown for reference only -- per
    the backtest (cfb-backtest-findings-2026), model-vs-spread gaps are
    NOT a demonstrated betting edge.

HFA/sigma calibration (build_hfa_check.py, n=2,210 FBS games 2023-2025):
home-site games average +2.92 pts of leftover margin after accounting for
team quality; NEUTRAL-site games still average +1.77 (many "neutral" sites
are de facto home-market for one side); altitude-market programs (Air
Force, BYU, Colorado, Colorado State, New Mexico, Utah, Wyoming) average
+5.96 at home, more than double every other team's +2.75; residual std
dev is 18.41. All four constants below are set from these empirical values.

FBS-vs-FCS/other games are listed separately (model has no rating for the
non-FBS side) -- just noted as expected FBS wins ("buy games").

Totals: proj_total = (home_off_sp + away_def_sp)/2 + (away_off_sp +
home_def_sp)/2, rescaled through a linear calibration fit on 2023-2025
games (see totals_backtest_README.md). Weak signal (R^2=0.032) -- shown
as a rough, low-confidence estimate, not a sharp number, no backtested
edge against market totals.
"""
import argparse
import json
import math
import os

import pandas as pd

from cfbd_fetch import cfbd_get_save, get_current_week

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

HFA_BASE = 2.9
HFA_NEUTRAL = 1.8
HFA_ALTITUDE = 6.0
ALTITUDE_TEAMS = {"Air Force", "BYU", "Colorado", "Colorado State", "New Mexico", "Utah", "Wyoming"}
SIGMA = 18.4
# Linear calibration fit from build_totals_backtest.py (actual_total ~ a + b*proj_total_raw)
TOTAL_CAL_A = 32.259
TOTAL_CAL_B = 0.389275


def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--week", type=int, default=None, help="If omitted, auto-detect the upcoming week via CFBD's calendar")
    ap.add_argument("--skip-fetch", action="store_true", help="Reuse existing cfbd_raw/ JSON instead of re-pulling from CFBD")
    args = ap.parse_args()

    year = args.year
    week = args.week
    if week is None:
        week = get_current_week(year)
        if week is None:
            raise SystemExit(f"Could not determine the current week for {year} -- season calendar isn't "
                              f"published yet, or the regular season is already over. Pass --week explicitly.")
        print(f"Auto-detected current week: {week}")

    games_path = f"cfbd_raw/games_{year}_wk{week}.json"
    lines_path = f"cfbd_raw/lines_{year}_wk{week}.json"
    os.makedirs("cfbd_raw", exist_ok=True)
    if args.skip_fetch and os.path.exists(games_path) and os.path.exists(lines_path):
        print(f"--skip-fetch: reusing {games_path} / {lines_path}")
    else:
        print(f"Pulling {year} week {week} games/lines from CFBD...")
        cfbd_get_save("/games", games_path, params={"year": year, "week": week, "seasonType": "regular"})
        cfbd_get_save("/lines", lines_path, params={"year": year, "week": week, "seasonType": "regular"})

    games = json.load(open(games_path, encoding="utf-8"))
    lines_raw = json.load(open(lines_path, encoding="utf-8"))
    lines_by_id = {g["id"]: g.get("lines", []) for g in lines_raw}

    pr = pd.read_csv("cfb_2026_power_ratings.csv")
    sp_split = pd.read_csv("sp_plus_2026_preseason.csv")[["team", "off_sp_plus", "def_sp_plus"]]
    pr = pr.merge(sp_split, on="team", how="left")
    # Phil Steele's Power Poll (1-138 ordinal rank) -> a point-scale value
    # comparable to sp_plus/fpi/model_proj_margin_2026: z-score it across
    # all 138 teams, then rescale by SP+'s own std dev (see comment on
    # STEELE_POINT_SCALE note in the module docstring).
    steele_score = 139 - pr["steele_power_poll_rank"]
    steele_z = (steele_score - steele_score.mean()) / steele_score.std()
    pr["steele_margin"] = steele_z * pr["sp_plus"].std()
    pr_lookup = pr.set_index("team")[
        ["sp_plus", "fpi", "model_proj_margin_2026", "steele_margin", "blended_rank",
         "off_sp_plus", "def_sp_plus", "source_disagreement"]
    ].to_dict("index")
    DISAGREEMENT_FLAG_THRESHOLD = pr["source_disagreement"].quantile(0.90)

    def resolve(cfbd_name):
        key = CFBD_TO_ATHLON.get(cfbd_name, cfbd_name)
        return pr_lookup.get(key)

    rows = []
    fbs_vs_other = []
    unmatched = set()

    for g in games:
        home, away = g["homeTeam"], g["awayTeam"]
        home_fbs = g["homeClassification"] == "fbs"
        away_fbs = g["awayClassification"] == "fbs"
        date = g["startDate"][:10]

        if not (home_fbs and away_fbs):
            fbs_side = home if home_fbs else (away if away_fbs else None)
            other_side = away if home_fbs else home
            fbs_vs_other.append({"date": date, "fbs_team": fbs_side, "opponent": other_side,
                                  "home_away": "home" if home_fbs else "away"})
            continue

        hr = resolve(home)
        ar = resolve(away)
        if hr is None:
            unmatched.add(home)
        if ar is None:
            unmatched.add(away)
        if hr is None or ar is None:
            continue

        diffs = []
        for col in ["sp_plus", "fpi", "model_proj_margin_2026", "steele_margin"]:
            if pd.notna(hr[col]) and pd.notna(ar[col]):
                diffs.append(hr[col] - ar[col])
        avg_diff = sum(diffs) / len(diffs) if diffs else float("nan")
        neutral = g.get("neutralSite", False)
        if neutral:
            hfa = HFA_NEUTRAL
        elif home in ALTITUDE_TEAMS:
            hfa = HFA_ALTITUDE
        else:
            hfa = HFA_BASE
        model_margin = avg_diff + hfa  # positive = home favored

        home_wp = norm_cdf(model_margin / SIGMA)

        game_lines = lines_by_id.get(g["id"], [])
        market_margin = None
        market_book = None
        market_total = None
        if game_lines:
            spreads = [l["spread"] for l in game_lines if l.get("spread") is not None]
            if spreads:
                spreads.sort()
                mid = spreads[len(spreads) // 2]
                market_margin = -mid  # spread is home-team-perspective; negative = home favored
                market_book = f"{len(spreads)} book(s), median {mid:+.1f}"
            totals_quoted = [l["overUnder"] for l in game_lines if l.get("overUnder") is not None]
            if totals_quoted:
                totals_quoted.sort()
                market_total = totals_quoted[len(totals_quoted) // 2]

        pick = home if model_margin > 0 else away
        pick_margin = abs(model_margin)

        model_total = None
        if pd.notna(hr["off_sp_plus"]) and pd.notna(hr["def_sp_plus"]) and \
           pd.notna(ar["off_sp_plus"]) and pd.notna(ar["def_sp_plus"]):
            proj_total_raw = (hr["off_sp_plus"] + ar["def_sp_plus"]) / 2 + (ar["off_sp_plus"] + hr["def_sp_plus"]) / 2
            model_total = round(TOTAL_CAL_A + TOTAL_CAL_B * proj_total_raw, 1)

        home_disagreement = hr["source_disagreement"]
        away_disagreement = ar["source_disagreement"]
        flagged_team, flagged_value = None, None
        if home_disagreement >= away_disagreement and home_disagreement >= DISAGREEMENT_FLAG_THRESHOLD:
            flagged_team, flagged_value = home, home_disagreement
        elif away_disagreement >= DISAGREEMENT_FLAG_THRESHOLD:
            flagged_team, flagged_value = away, away_disagreement

        rows.append({
            "game_id": g["id"],
            "date": date,
            "away": away, "home": home, "neutral": neutral,
            "model_pick": pick, "model_margin": round(pick_margin, 1),
            "home_win_prob": round(home_wp, 3),
            "home_blended_rank": hr["blended_rank"], "away_blended_rank": ar["blended_rank"],
            "market_home_margin": market_margin, "market_note": market_book,
            "model_vs_market_gap": round(model_margin - market_margin, 1) if market_margin is not None else None,
            "model_total": model_total, "market_total": market_total,
            "total_gap": round(model_total - market_total, 1) if (model_total is not None and market_total is not None) else None,
            "disagreement_team": flagged_team, "disagreement_value": round(flagged_value, 2) if flagged_value else None,
        })

    if unmatched:
        print("UNMATCHED TEAM NAMES (no power rating found):", sorted(unmatched))

    proj_out = f"week{week}_{year}_projections.csv"
    other_out = f"week{week}_{year}_fbs_vs_other.csv"

    df = pd.DataFrame(rows).sort_values(["date", "model_margin"], ascending=[True, False])
    df.to_csv(proj_out, index=False)
    print(f"\n{len(df)} FBS-vs-FBS games projected, saved to {proj_out}")
    print(f"{len(fbs_vs_other)} FBS-vs-non-FBS games (excluded from projection, expected FBS wins)")

    pd.DataFrame(fbs_vs_other).sort_values("date").to_csv(other_out, index=False)

    if not df.empty:
        with_market = df.dropna(subset=["model_vs_market_gap"]).copy()
        if not with_market.empty:
            with_market["abs_gap"] = with_market["model_vs_market_gap"].abs()
            print("\n=== Biggest projected mismatches (model vs market, where a line exists) ===")
            print(with_market.sort_values("abs_gap", ascending=False).head(15)[
                ["date", "away", "home", "model_pick", "model_margin", "market_home_margin", "model_vs_market_gap"]
            ].to_string(index=False))

    print(f"\nyear={year} week={week}")  # machine-readable tail line for the automation routine


if __name__ == "__main__":
    main()
