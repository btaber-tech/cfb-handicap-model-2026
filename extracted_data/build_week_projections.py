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
  - preseason_diff = avg of available point-scale ratings diffs (SP+, FPI,
    bottom-up model_proj_margin_2026, Phil Steele's Power Poll rescaled to
    points -- see STEELE_POINT_SCALE below), home minus away. Steele's
    Power Poll was added at the user's request that his opinion carry more
    weight than Athlon's (which has no numeric weight here or in
    cfb_2026_power_ratings.csv -- comparison column only). This 4th-source
    addition is NOT separately backtested (the ~76% SU accuracy figure in
    cfb-backtest-findings-2026 was measured on the 3-source SP+/FPI/
    bottom-up version); it's a reasonable extension since Steele's Power
    Poll is itself a talent composite like SP+/FPI, not an opinion piece,
    but treat post-integration accuracy as unverified until re-backtested.
  - in_season_diff = home minus away SRS-style in-season rating, from
    in_season_ratings_2026.csv (build_in_season_ratings.py) if it exists
    and both teams have played at least one game -- see IN_SEASON_WEIGHT
    below for how much this counts vs. the preseason blend.
  - model_margin (2026-11-03 onward) = SPPLUS_WEIGHT * SP+ weekly projected
    margin (Connelly's public picks sheet, fetch_spplus_picks.py) +
    (1 - SPPLUS_WEIGHT) * (preseason_diff + HFA). The SP+ projection already
    includes home field. The one-pass SRS in-season rating is NO LONGER in
    the margin when SP+ has the game: on 2026 wk3-9 it ran 48.4% ATS with a
    negative edge/result correlation, while 0.6-0.8 SP+ weight was best for
    MAE and ATS in both 2025 and 2026 (see ats_tiers_README.md).
  - Fallback when SP+ has no row for a game (sheet not posted yet, name
    mismatch): the old formula, (1 - w)*preseason_diff + w*in_season_diff +
    HFA with w = IN_SEASON_WEIGHT(week). model_source records which was used.
  - ats_tier (STRONG / NO SIGNAL / SKIP) on the model's side of the market
    spread -- definitions and backtest in ats_tiers_README.md.
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
from situational_flags import conflict_reasons, team_situations
from team_records import compute_team_records, fmt_ats, fmt_wl

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
# In-season totals (2026-10-05, build_totals_inseason_backtest.py): each team's
# SP+ off/def blended with its opponent-adjusted 2026 points scored/allowed at
# weight n/(n+TOTAL_SHRINK_K), n = FBS games played. 2023-25 replay: r vs actual
# 0.19 -> 0.28 in weeks 5+, MAE 13.18 -> 12.93. Better estimate, still well short
# of the market (r 0.38) and NO over/under edge -- context only, like before.
TOTAL_SHRINK_K = 4
TOTAL_CAL_A_INSEASON = 14.120
TOTAL_CAL_B_INSEASON = 0.7308
# Weight on SP+'s weekly projected margin (rest = preseason blend + HFA). Chosen
# 2026-11-03 from 2025 (replica) + 2026 (live) tests: 0.6-0.8 best in both seasons.
SPPLUS_WEIGHT = 0.7


def load_spplus(year):
    """{(frozenset{home, away}, cfbd_week): (sp_home_margin, sp_ats_pick)} from spplus_picks_{year}.csv."""
    path = f"spplus_picks_{year}.csv"
    if not os.path.exists(path):
        return {}
    sp = pd.read_csv(path)
    out = {}
    for r in sp.itertuples(index=False):
        if pd.isna(r.sp_proj_margin):
            continue
        m = r.sp_proj_margin if r.sp_proj_winner == r.home else -r.sp_proj_margin
        out[(frozenset([r.home, r.away]), int(r.week))] = (float(m), r.home, r.sp_ats_pick)
    return out


def ats_tier(edge, sp_edge, pre_edge, side_is_home, neutral, side_is_fav, reasons):
    """STRONG / NO SIGNAL / SKIP for the model's ATS side (see ats_tiers_README.md).
    SKIP: an away favourite, or a situational conflict. STRONG: SP+ and the preseason
    blend each independently on this side of the line, or the side is the home favourite."""
    if not side_is_home and not neutral and side_is_fav:
        reasons = ["away favourite"] + reasons
    if reasons:
        return "SKIP", "; ".join(reasons)
    support = []
    if sp_edge is not None and pre_edge is not None and \
            (sp_edge > 0) == (edge > 0) and (pre_edge > 0) == (edge > 0) and sp_edge != 0 and pre_edge != 0:
        support.append("SP+ and preseason agree")
    if side_is_home and not neutral and side_is_fav:
        support.append("home favourite")
    if support:
        return "STRONG", "; ".join(support)
    return "NO SIGNAL", ""


def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def in_season_weight(week):
    """How much of the model_margin comes from in-season SRS-style
    performance vs. the preseason blend, as a function of the week being
    projected (games completed strictly before `week` feed the in-season
    rating -- no lookahead). Weeks 1-2 have no prior in-season data at all
    (0%). From week 3 on, ramp up so the in-season signal reaches roughly
    the 70-80%-by-week-6-8 target from project memory
    (cfb-handicap-model-2026) -- chosen by user preference (gradual ramp,
    not an instant switch) since 1-2 games/team is a small, noisy sample
    and shouldn't dominate the model yet. This schedule is a design
    choice, NOT itself backtested against historical seasons -- watch the
    scorecard (build_scorecard.py) as it's used and revisit if SU/margin
    accuracy doesn't hold up once it starts carrying real weight.
    """
    if week <= 2:
        return 0.0
    return min(0.78, 0.15 + 0.15 * (week - 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--week", type=int, default=None, help="If omitted, auto-detect the upcoming week via CFBD's calendar")
    ap.add_argument("--skip-fetch", action="store_true", help="Reuse existing cfbd_raw/ JSON instead of re-pulling from CFBD")
    ap.add_argument("--out-dir", default=".", help="Where to write the CSVs (use a scratch dir to re-run past weeks "
                                                    "without overwriting the graded projection files)")
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
    # model_proj_margin_2026_scaled / steele_margin_scaled: point-scale
    # versions of the bottom-up model and Steele's Power Poll, already
    # rescaled (z-score * sp_plus's std) in build_2026_power_ratings.py so
    # they're comparable to sp_plus/fpi before averaging. Use those, NOT
    # the raw model_proj_margin_2026 column -- its native scale runs at
    # roughly half sp_plus/fpi's std dev (agrees on who's good, just says
    # so far more timidly in points), which silently compresses every
    # blended margin toward zero if averaged in unscaled (2026-08-20: this
    # is what was producing the too-compressed season win-total spread --
    # see win_totals_README.md).
    pr_lookup = pr.set_index("team")[
        ["sp_plus", "fpi", "model_proj_margin_2026_scaled", "steele_margin_scaled", "blended_rank",
         "off_sp_plus", "def_sp_plus", "source_disagreement"]
    ].to_dict("index")
    DISAGREEMENT_FLAG_THRESHOLD = pr["source_disagreement"].quantile(0.90)

    w_in_season = in_season_weight(week)
    in_season_path = "in_season_ratings_2026.csv"
    in_season_lookup = {}
    if w_in_season > 0 and os.path.exists(in_season_path):
        in_season_lookup = pd.read_csv(in_season_path).set_index("team")["in_season_margin_2026"].to_dict()
        print(f"In-season blend active: week {week} weight = {w_in_season:.0%} "
              f"(loaded {len(in_season_lookup)} teams from {in_season_path})")
    elif w_in_season > 0:
        print(f"NOTE: week {week} calls for a {w_in_season:.0%} in-season weight, but "
              f"{in_season_path} doesn't exist yet -- falling back to pure preseason for every game. "
              f"Run build_in_season_ratings.py first.")
        w_in_season = 0.0

    # In-season off/def for model_total (independent of the margin ramp: uses
    # its own n/(n+k) shrink, so it applies from the first game played).
    totals_lookup = {}
    if os.path.exists(in_season_path):
        ins = pd.read_csv(in_season_path)
        if "in_season_off_2026" in ins.columns:
            totals_lookup = ins.dropna(subset=["in_season_off_2026"]).set_index("team")[
                ["totals_games", "in_season_off_2026", "in_season_def_2026"]].to_dict("index")
    totals_in_season = bool(totals_lookup) and week > 1
    if not totals_in_season and week > 1:
        print(f"NOTE: no in-season off/def in {in_season_path} -- model_total falls back to preseason SP+ only. "
              f"Re-run build_in_season_ratings.py.")

    def blend_totals(cfbd_name, rating):
        t = totals_lookup.get(CFBD_TO_ATHLON.get(cfbd_name, cfbd_name))
        if t is None:
            return rating["off_sp_plus"], rating["def_sp_plus"]
        w = t["totals_games"] / (t["totals_games"] + TOTAL_SHRINK_K)
        return ((1 - w) * rating["off_sp_plus"] + w * t["in_season_off_2026"],
                (1 - w) * rating["def_sp_plus"] + w * t["in_season_def_2026"])

    # Season-to-date W-L / ATS records (games before this week) for the page's
    # record columns -- context only, not a model input. See team_records.py.
    team_records = compute_team_records(year, week - 1, fetch=not args.skip_fetch) if week > 1 else {}
    # Situational skip angles, from the *_final.json files compute_team_records just saved.
    situations = team_situations(year, week - 1) if week > 1 else {}

    spplus = load_spplus(year)
    n_sp_week = sum(1 for (_, wk) in spplus if wk == week)
    if n_sp_week:
        print(f"SP+ weekly projections: {n_sp_week} games for week {week} (weight {SPPLUS_WEIGHT:.0%})")
    else:
        print(f"NOTE: no SP+ rows for week {week} in spplus_picks_{year}.csv -- run fetch_spplus_picks.py first. "
              f"Falling back to the preseason + in-season SRS formula for every game.")

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
            if not (home_fbs or away_fbs):
                # Neither side is FBS (e.g. two D-II/D-III teams) -- not a "buy
                # game" for any FBS team, just noise for this model. Skip.
                continue
            fbs_side = home if home_fbs else away
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
        for col in ["sp_plus", "fpi", "model_proj_margin_2026_scaled", "steele_margin_scaled"]:
            if pd.notna(hr[col]) and pd.notna(ar[col]):
                diffs.append(hr[col] - ar[col])
        preseason_diff = sum(diffs) / len(diffs) if diffs else float("nan")

        # in_season_ratings_2026.csv is keyed by Athlon team names (same as
        # pr_lookup), so map CFBD names through CFBD_TO_ATHLON here too --
        # otherwise Miami/UMass/WKU/etc. silently drop to preseason-only.
        home_in_season = in_season_lookup.get(CFBD_TO_ATHLON.get(home, home))
        away_in_season = in_season_lookup.get(CFBD_TO_ATHLON.get(away, away))
        game_w = w_in_season if (home_in_season is not None and away_in_season is not None) else 0.0
        if game_w > 0:
            in_season_diff = home_in_season - away_in_season
            core_diff = (1 - game_w) * preseason_diff + game_w * in_season_diff
        else:
            core_diff = preseason_diff

        neutral = g.get("neutralSite", False)
        if neutral:
            hfa = HFA_NEUTRAL
        elif home in ALTITUDE_TEAMS:
            hfa = HFA_ALTITUDE
        else:
            hfa = HFA_BASE
        pre_margin = preseason_diff + hfa
        sp_row = spplus.get((frozenset([home, away]), week))
        sp_home_margin = None
        if sp_row is not None:
            sp_home_margin = sp_row[0] if sp_row[1] == home else -sp_row[0]  # sheet's listed home may differ at neutral sites
            if pd.notna(pre_margin):
                model_margin = SPPLUS_WEIGHT * sp_home_margin + (1 - SPPLUS_WEIGHT) * pre_margin
                model_source = "SP+ blend"
            else:
                model_margin = sp_home_margin
                model_source = "SP+ only (no preseason rating)"
            game_w = 0.0
        else:
            model_margin = core_diff + hfa  # fallback: preseason + in-season SRS
            model_source = "fallback (no SP+ row)"
        # positive model_margin = home favored

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

        # ATS side + tier (vs the market number at projection time)
        ats_side, tier, tier_reason, sp_ats_pick = None, None, None, (sp_row[2] if sp_row else None)
        if market_margin is not None and round(model_margin, 1) != market_margin:
            edge = model_margin - market_margin
            side_is_home = edge > 0
            ats_side = home if side_is_home else away
            opp = away if side_is_home else home
            side_is_fav = market_margin > 0 if side_is_home else market_margin < 0
            reasons = conflict_reasons(ats_side, opp, side_is_home, neutral, side_is_fav, situations,
                                       g.get("homeConference") if side_is_home else g.get("awayConference"),
                                       g.get("awayConference") if side_is_home else g.get("homeConference"))
            if sp_home_margin is None:
                tier, tier_reason = "NO SIGNAL", "no SP+ projection (fallback formula)"
            else:
                tier, tier_reason = ats_tier(edge, sp_home_margin - market_margin,
                                             (pre_margin - market_margin) if pd.notna(pre_margin) else None,
                                             side_is_home, neutral, side_is_fav, reasons)

        model_total = None
        if pd.notna(hr["off_sp_plus"]) and pd.notna(hr["def_sp_plus"]) and \
           pd.notna(ar["off_sp_plus"]) and pd.notna(ar["def_sp_plus"]):
            if totals_in_season:
                h_off, h_def = blend_totals(home, hr)
                a_off, a_def = blend_totals(away, ar)
                proj_total_raw = (h_off + a_def) / 2 + (a_off + h_def) / 2
                model_total = round(TOTAL_CAL_A_INSEASON + TOTAL_CAL_B_INSEASON * proj_total_raw, 1)
            else:
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
            "away_record": fmt_wl(team_records.get(away)), "home_record": fmt_wl(team_records.get(home)),
            "away_ats": fmt_ats(team_records.get(away)), "home_ats": fmt_ats(team_records.get(home)),
            "home_blended_rank": hr["blended_rank"], "away_blended_rank": ar["blended_rank"],
            "in_season_weight": round(game_w, 2),
            "home_in_season_margin": home_in_season, "away_in_season_margin": away_in_season,
            "market_home_margin": market_margin, "market_note": market_book,
            "model_vs_market_gap": round(model_margin - market_margin, 1) if market_margin is not None else None,
            "model_total": model_total, "market_total": market_total,
            "total_gap": round(model_total - market_total, 1) if (model_total is not None and market_total is not None) else None,
            "disagreement_team": flagged_team, "disagreement_value": round(flagged_value, 2) if flagged_value else None,
            "model_source": model_source,
            "sp_home_margin": round(sp_home_margin, 1) if sp_home_margin is not None else None,
            "pre_home_margin": round(pre_margin, 1) if pd.notna(pre_margin) else None,
            "sp_ats_pick": sp_ats_pick,
            "ats_side": ats_side, "ats_tier": tier, "ats_tier_reason": tier_reason,
        })

    if unmatched:
        print("UNMATCHED TEAM NAMES (no power rating found):", sorted(unmatched))

    proj_out = os.path.join(args.out_dir, f"week{week}_{year}_projections.csv")
    other_out = os.path.join(args.out_dir, f"week{week}_{year}_fbs_vs_other.csv")

    df = pd.DataFrame(rows).sort_values(["date", "model_margin"], ascending=[True, False])
    df.to_csv(proj_out, index=False)
    print(f"\n{len(df)} FBS-vs-FBS games projected, saved to {proj_out}")
    print(f"{len(fbs_vs_other)} FBS-vs-non-FBS games (excluded from projection, expected FBS wins)")

    pd.DataFrame(fbs_vs_other, columns=["date", "fbs_team", "opponent", "home_away"]).sort_values("date").to_csv(other_out, index=False)

    if not df.empty:
        with_market = df.dropna(subset=["model_vs_market_gap"]).copy()
        if not with_market.empty:
            with_market["abs_gap"] = with_market["model_vs_market_gap"].abs()
            print("\n=== Biggest projected mismatches (model vs market, where a line exists) ===")
            print(with_market.sort_values("abs_gap", ascending=False).head(15)[
                ["date", "away", "home", "model_pick", "model_margin", "market_home_margin", "model_vs_market_gap"]
            ].to_string(index=False))

        if "ats_tier" in df.columns:
            print("\n=== ATS tiers ===")
            print(df["ats_tier"].value_counts(dropna=False).to_string())
            print(df["model_source"].value_counts().to_string())

    print(f"\nyear={year} week={week}")  # machine-readable tail line for the automation routine


if __name__ == "__main__":
    main()
