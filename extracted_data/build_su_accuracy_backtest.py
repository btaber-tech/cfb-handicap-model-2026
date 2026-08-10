"""
Adjustments #1 + #2: validate the live Week-0/1 formula game-by-game (has
never been tested in this exact form), and check whether equal-weighting
SP+/FPI/Elo actually beats using the single best source alone.

Scope: WEEK 1 games only, 2023-2025 (n~700-750) -- deliberately, not all
weeks. This is what the live 2026 pipeline actually projects (preseason
info predicting the season opener), so it's the fairest and most relevant
test: every input below is genuinely available *before* that season's
first game, no lookahead.

Sources tested, each converted to a projected margin (already point-scaled
in the source's own units) + a flat +2.5 HFA (0 if neutral):
  - SP+:  prior-season final overall SP+ rating diff (already in
          backtest_transitions.csv as prior_sp_rating)
  - FPI:  prior-season final FPI diff (pulled this session, cfbd_raw/fpi_*.json)
  - Elo:  that game's own pregame Elo diff, run through the fair-value fit
          from opening_line_test.py (margin = alpha + beta*elo_diff) --
          Elo is continuously updated, but week-1 pregame Elo is
          overwhelmingly last season's carryover + mean reversion, so this
          is close to a genuine preseason number too.
  - Blend: simple average of whichever of the 3 margins are available
          (mirrors the live model's equal-weight design)
  - Market: closing spread, for comparison (the ceiling everyone is
          chasing, not a source we control)

Win probability for every source uses the same normal CDF, sigma=16.5, as
the live pipeline -- isolates "whose margin number is better" rather than
"whose probability curve is better."
"""
import json
import math
import numpy as np
import pandas as pd
from scipy import stats

HFA = 2.5
SIGMA = 16.5


def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


trans = pd.read_csv("backtest_transitions.csv")
sp_lookup = trans.set_index(["season", "team"])["prior_sp_rating"].to_dict()

fpi_by_season = {}
for y in [2022, 2023, 2024, 2025]:
    fpi_raw = json.load(open(f"cfbd_raw/fpi_{y}.json", encoding="utf-8"))
    fpi_by_season[y] = {r["team"]: r["fpi"] for r in fpi_raw}

# Re-derive the Elo fair-value fit exactly as opening_line_test.py did, so this
# script stands alone (same 4-season, all-weeks fit; applied out of sample here
# to a week-1-only subset it wasn't fit on).
elo_rows = []
for y in [2022, 2023, 2024, 2025]:
    games = json.load(open(f"cfbd_raw/games_{y}.json", encoding="utf-8"))
    for g in games:
        if not g.get("completed"):
            continue
        he, ae = g.get("homePregameElo"), g.get("awayPregameElo")
        if he is None or ae is None:
            continue
        elo_rows.append({"margin": g["homePoints"] - g["awayPoints"], "elo_diff": he - ae})
elo_df = pd.DataFrame(elo_rows)
X = np.column_stack([np.ones(len(elo_df)), elo_df.elo_diff.values])
elo_beta, *_ = np.linalg.lstsq(X, elo_df.margin.values, rcond=None)
ELO_A, ELO_B = elo_beta
print(f"Elo fair-value fit (4 seasons, all weeks, n={len(elo_df)}): margin = {ELO_A:.2f} + {ELO_B:.5f}*elo_diff")

rows = []
for season in [2023, 2024, 2025]:
    games = json.load(open(f"cfbd_raw/games_{season}.json", encoding="utf-8"))
    lines_raw = json.load(open(f"cfbd_raw/lines_{season}.json", encoding="utf-8"))
    lines_by_id = {g["id"]: g.get("lines", []) for g in lines_raw}
    fpi_prior = fpi_by_season.get(season - 1, {})

    for g in games:
        if g["week"] != 1 or g["seasonType"] != "regular" or not g["completed"]:
            continue
        if g["homeClassification"] != "fbs" or g["awayClassification"] != "fbs":
            continue
        home, away = g["homeTeam"], g["awayTeam"]
        hfa = 0 if g.get("neutralSite") else HFA
        actual_margin = g["homePoints"] - g["awayPoints"]
        home_won = actual_margin > 0

        margins = {}
        sp_h, sp_a = sp_lookup.get((season, home)), sp_lookup.get((season, away))
        if sp_h is not None and sp_a is not None and pd.notna(sp_h) and pd.notna(sp_a):
            margins["sp"] = (sp_h - sp_a) + hfa

        fpi_h, fpi_a = fpi_prior.get(home), fpi_prior.get(away)
        if fpi_h is not None and fpi_a is not None:
            margins["fpi"] = (fpi_h - fpi_a) + hfa

        he, ae = g.get("homePregameElo"), g.get("awayPregameElo")
        if he is not None and ae is not None:
            margins["elo"] = (ELO_A + ELO_B * (he - ae)) + (hfa - HFA)  # ELO_A already carries its own avg HFA; add only neutral-site adjustment

        game_lines = lines_by_id.get(g["id"], [])
        spreads = [l["spread"] for l in game_lines if l.get("spread") is not None]
        market_margin = -float(np.median(spreads)) if spreads else None

        if not margins:
            continue
        margins["blend"] = float(np.mean(list(margins.values())))

        row = {"season": season, "home": home, "away": away,
               "actual_margin": actual_margin, "home_won": home_won,
               "market_margin": market_margin}
        for src, m in margins.items():
            row[f"{src}_margin"] = m
        rows.append(row)

df = pd.DataFrame(rows)
print(f"\nWeek-1 games, 2023-2025, with at least one source: n={len(df)}")
for src in ["sp", "fpi", "elo", "blend"]:
    print(f"  n with {src}: {df[f'{src}_margin'].notna().sum()}")

print("\n=== Straight-up accuracy & Brier score (Week 1 games only) ===")
print(f"{'source':10s} {'n':>5s} {'accuracy':>9s} {'brier':>7s}   vs. always-pick-home baseline")

baseline_acc = df.home_won.mean()
print(f"{'home-fav':10s} {len(df):5d} {baseline_acc:9.3f} {'--':>7s}")

for src in ["sp", "fpi", "elo", "blend", "market"]:
    col = f"{src}_margin"
    sub = df.dropna(subset=[col])
    if len(sub) < 20:
        continue
    pred_home = sub[col] > 0
    acc = (pred_home == sub.home_won).mean()
    wp = sub[col].apply(lambda m: norm_cdf(m / SIGMA))
    brier = ((wp - sub.home_won.astype(float)) ** 2).mean()
    print(f"{src:10s} {len(sub):5d} {acc:9.3f} {brier:7.4f}")

# Head-to-head: on the subset where ALL of sp/fpi/elo are available, does the
# equal-weight blend actually beat the best single source, or just match it?
all3 = df.dropna(subset=["sp_margin", "fpi_margin", "elo_margin", "market_margin"])
print(f"\n=== Same comparison, restricted to the {len(all3)} games where SP+, FPI, Elo, AND market all exist ===")
for src in ["sp", "fpi", "elo", "blend", "market"]:
    col = f"{src}_margin"
    pred_home = all3[col] > 0
    acc = (pred_home == all3.home_won).mean()
    wp = all3[col].apply(lambda m: norm_cdf(m / SIGMA))
    brier = ((wp - all3.home_won.astype(float)) ** 2).mean()
    mae = (all3[col] - all3.actual_margin).abs().mean()
    print(f"{src:10s} n={len(all3):4d}  accuracy={acc:.3f}  brier={brier:.4f}  mean_abs_margin_error={mae:.2f}")

df.to_csv("su_accuracy_backtest_games.csv", index=False)
print("\nSaved su_accuracy_backtest_games.csv")
