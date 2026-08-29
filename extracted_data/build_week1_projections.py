"""
Apply the 2026 power ratings to the season's opening slate (CFBD lumps
"Week 0" (Aug 27-30 kickoff games) and "Week 1" (Sep 3-7) into a single
week=1 for the 2026 season -- there is no separate week=0 bucket this year).

For each FBS-vs-FBS game:
  - model_margin = avg of available point-scale ratings diffs (SP+, FPI,
    bottom-up model_proj_margin_2026), home minus away, plus a home-field
    adjustment (see HFA constants below).
  - win prob from a normal CDF on that margin with sigma=SIGMA (a per-game
    CFB margin-to-winprob heuristic; NOT the same as the backtest's
    season-average-margin R^2).
  - market_margin, if a line exists yet, for reference only -- per the
    backtest (cfb-backtest-findings-2026), model-vs-spread gaps are NOT a
    demonstrated betting edge, shown for context only.

HFA/sigma calibration (added 2026-08-10, build_hfa_check.py, n=2,210 FBS
games 2023-2025): a flat +2.5/0-neutral/sigma=16.5 was never checked
against real data. Empirically: home-site games average +2.92 pts of
leftover margin after accounting for team quality (not +2.5); NEUTRAL-site
games still average +1.77 (not 0 -- many "neutral" sites are de facto
home-market for one side, e.g. kickoff classics); a set of altitude-market
programs (Air Force, BYU, Colorado, Colorado State, New Mexico, Utah,
Wyoming) average +5.96 at home, more than double every other team's +2.75
-- a real, sizeable effect worth a specific adjustment rather than folding
into one national constant. Residual std dev came in at 18.41, wider than
the assumed 16.5 (the model was mildly overconfident). All four constants
below are set from these empirical values.

FBS-vs-FCS/other games are listed separately (model has no rating for the
non-FBS side, so no margin is projected -- these are just noted as expected
FBS wins).

Totals (added 2026-08-10, see totals_backtest_README.md for the backtest
this is based on): proj_total = (home_off_sp + away_def_sp)/2 +
(away_off_sp + home_def_sp)/2, then rescaled through a linear calibration
fit on 2023-2025 games (raw projection was biased/miscalibrated: r=0.178,
R^2=-0.05 uncalibrated -> R^2=0.032 after fitting actual_total ~ a + b*proj).
That R^2=0.032 is genuinely weak -- much weaker than the margin model
(R^2=0.33-0.37) and weaker than the market's own total (R^2~=0.12) -- so
totals are shown as a rough, low-confidence estimate, not a sharp number,
and there is NO backtested edge against market totals (all thresholds
p>0.05 except one marginal, likely-multiple-comparisons hit).
"""
import json
import math
import pandas as pd

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


games = json.load(open("cfbd_raw/games_2026_wk1.json", encoding="utf-8"))
lines_raw = json.load(open("cfbd_raw/lines_2026_wk1.json", encoding="utf-8"))
lines_by_id = {g["id"]: g.get("lines", []) for g in lines_raw}

pr = pd.read_csv("cfb_2026_power_ratings.csv")
sp_split = pd.read_csv("sp_plus_2026_preseason.csv")[["team", "off_sp_plus", "def_sp_plus"]]
pr = pr.merge(sp_split, on="team", how="left")
# model_proj_margin_2026_scaled / steele_margin_scaled: point-scale versions
# of the bottom-up model and Steele's Power Poll (rescaled in
# build_2026_power_ratings.py via z-score * sp_plus's std). Use those, not
# the raw model_proj_margin_2026 column -- its native scale runs at
# roughly half sp_plus/fpi's std dev, which silently compresses every
# blended margin toward zero if averaged in unscaled (2026-08-20 fix, see
# win_totals_README.md).
pr_lookup = pr.set_index("team")[
    ["sp_plus", "fpi", "model_proj_margin_2026_scaled", "steele_margin_scaled", "blended_rank",
     "off_sp_plus", "def_sp_plus", "source_disagreement"]
].to_dict("index")
# Adjustment #4: flag games where a team's SP+/FPI/bottom-up sources disagree a
# lot (90th-percentile+ of source_disagreement across all 138 teams) instead of
# leaving that signal buried in the power-ratings CSV.
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

    # Totals: only when both teams have an off/def SP+ split (2 new FBS members
    # -- North Dakota State, Sacramento State -- don't have one yet)
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

df = pd.DataFrame(rows).sort_values(["date", "model_margin"], ascending=[True, False])
df.to_csv("week1_2026_projections.csv", index=False)
print(f"\n{len(df)} FBS-vs-FBS games projected, saved to week1_2026_projections.csv")
print(f"{len(fbs_vs_other)} FBS-vs-non-FBS games (excluded from projection, expected FBS wins)")

pd.DataFrame(fbs_vs_other).sort_values("date").to_csv("week1_2026_fbs_vs_other.csv", index=False)

print("\n=== Biggest projected mismatches (model vs market, where a line exists) ===")
with_market = df.dropna(subset=["model_vs_market_gap"]).copy()
with_market["abs_gap"] = with_market["model_vs_market_gap"].abs()
print(with_market.sort_values("abs_gap", ascending=False).head(15)[
    ["date", "away", "home", "model_pick", "model_margin", "market_home_margin", "model_vs_market_gap"]
].to_string(index=False))
