"""
Totals backtest: does a preseason-style off/def SP+ projection predict game
totals, and is there a market edge against posted over/unders?

Mirrors the ATS backtest's design (build_backtest.py / situational_ats.py /
opening_line_test.py): use PRIOR-season-final SP+ off/def ratings (the same
"prior_sp_off_rating"/"prior_sp_def_rating" columns already sitting in
backtest_transitions.csv, keyed by outcome season) to project each team's
scoring in the *next* season's games -- no in-season lookahead, matching how
the real pipeline uses preseason ratings for 2026.

proj_home_pts = (home_prior_off_sp + away_prior_def_sp) / 2
proj_away_pts = (away_prior_off_sp + home_prior_def_sp) / 2
proj_total    = proj_home_pts + proj_away_pts

(off/def SP+ ratings are already points-scaled: off ~ "points this offense
scores vs an average defense", def ~ "points an average offense scores vs
this defense" -- confirmed by their ~25-26 pt means, matching real national
scoring averages.)
"""
import json
import numpy as np
import pandas as pd
from scipy import stats

trans = pd.read_csv("backtest_transitions.csv")
sp_lookup = trans.set_index(["season", "team"])[["prior_sp_off_rating", "prior_sp_def_rating"]]

rows = []
for season in [2023, 2024, 2025]:
    games = json.load(open(f"cfbd_raw/games_{season}.json", encoding="utf-8"))
    lines_raw = json.load(open(f"cfbd_raw/lines_{season}.json", encoding="utf-8"))
    lines_by_id = {g["id"]: g.get("lines", []) for g in lines_raw}

    for g in games:
        if g["seasonType"] != "regular" or not g["completed"]:
            continue
        if g["homeClassification"] != "fbs" or g["awayClassification"] != "fbs":
            continue
        home, away = g["homeTeam"], g["awayTeam"]
        try:
            h_off, h_def = sp_lookup.loc[(season, home)]
            a_off, a_def = sp_lookup.loc[(season, away)]
        except KeyError:
            continue
        if pd.isna(h_off) or pd.isna(h_def) or pd.isna(a_off) or pd.isna(a_def):
            continue

        actual_total = g["homePoints"] + g["awayPoints"]
        proj_total = (h_off + a_def) / 2 + (a_off + h_def) / 2

        game_lines = lines_by_id.get(g["id"], [])
        closes = [l["overUnder"] for l in game_lines if l.get("overUnder") is not None]
        opens = [l["overUnderOpen"] for l in game_lines if l.get("overUnderOpen") is not None]
        market_close = float(np.median(closes)) if closes else None
        market_open = float(np.median(opens)) if opens else None

        rows.append({
            "season": season, "home": home, "away": away,
            "actual_total": actual_total, "proj_total": proj_total,
            "market_close": market_close, "market_open": market_open,
        })

df = pd.DataFrame(rows)
print(f"n games with both prior-season SP+ off/def AND played: {len(df)}")

r, p = stats.pearsonr(df.proj_total, df.actual_total)
resid = df.actual_total - df.proj_total
r2 = 1 - (resid**2).sum() / ((df.actual_total - df.actual_total.mean())**2).sum()
print(f"\nproj_total vs actual_total: r={r:.3f} (p={p:.2e}), R^2={r2:.3f}")
print(f"mean bias (actual-proj): {resid.mean():+.2f}  std of residual: {resid.std():.2f}")

# Compare vs a naive constant-mean baseline (national average total) for context
naive_r2 = 0.0
print(f"(a rating-blind constant-mean guess would score R^2=0.000 by construction)")

# --- Market comparison: does proj_total beat the close, using the OPEN line so
# we're not comparing against a number that's already absorbed game-week news ---
mkt = df.dropna(subset=["market_close"]).copy()
print(f"\nn games with a market close total: {len(mkt)}")
r_m, p_m = stats.pearsonr(mkt.market_close, mkt.actual_total)
print(f"market_close vs actual_total:  r={r_m:.3f} (p={p_m:.2e})  <- how good Vegas already is")

mkt["went_over"] = mkt.actual_total > mkt.market_close
mkt["model_says_over"] = mkt.proj_total > mkt.market_close
mkt["gap"] = mkt.proj_total - mkt.market_close


def edge_test(sub, label):
    n = len(sub)
    if n == 0:
        print(f"{label}: n=0")
        return
    hits = (sub.went_over == sub.model_says_over).sum()
    rate = hits / n
    pval = stats.binomtest(hits, n, 0.5).pvalue
    print(f"{label}: n={n:4d}  hit_rate={rate:.3f}  p={pval:.3f}")


print("\n=== Betting the model's over/under lean vs. market close ===")
edge_test(mkt, "All games, any gap")
for thresh in [3, 5, 7, 10]:
    edge_test(mkt[mkt.gap.abs() >= thresh], f"|gap| >= {thresh} pts")

# Same test against the OPEN line, if available (more games would have moved by
# the close in response to news the model doesn't see -- opens are a fairer test
# of the model itself the way opening_line_test.py argued for spreads)
mkt_open = df.dropna(subset=["market_open"]).copy()
if len(mkt_open):
    mkt_open["went_over"] = mkt_open.actual_total > mkt_open.market_open
    mkt_open["model_says_over"] = mkt_open.proj_total > mkt_open.market_open
    mkt_open["gap"] = mkt_open.proj_total - mkt_open.market_open
    print("\n=== Same test vs. the OPENING total ===")
    edge_test(mkt_open, "All games, any gap")
    for thresh in [3, 5, 7, 10]:
        edge_test(mkt_open[mkt_open.gap.abs() >= thresh], f"|gap| >= {thresh} pts")

df.to_csv("totals_backtest_games.csv", index=False)
print("\nSaved totals_backtest_games.csv")
