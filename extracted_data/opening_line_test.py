"""
Opening-line softness test: build a market-independent "fair spread" from
CFBD's pregame Elo ratings (updated game-to-game, no lookahead), then check
whether betting whenever that model disagrees with the OPENING line beats
graded-at-the-open, and compare to betting the same disagreement against
the CLOSING line graded-at-the-close. If the open-based strategy shows a
real edge that the close-based one doesn't, opening lines are measurably
softer and "beat the market early" is an actionable rule.

Important framing: a bet placed at the open is GRADED at the open number
you actually got, not the close — so each strategy must compare its own
edge-vs-market-price to its own grading price.
"""
import json
import os
import numpy as np
import pandas as pd
from scipy import stats

RAW = "cfbd_raw"
YEARS = [2022, 2023, 2024, 2025]


def load(name, year):
    with open(os.path.join(RAW, f"{name}_{year}.json"), encoding="utf-8") as f:
        return json.load(f)


rows = []
for y in YEARS:
    games = {g["id"]: g for g in load("games", y)}
    for ln in load("lines", y):
        gid = ln["id"]
        g = games.get(gid)
        if g is None or not g.get("completed"):
            continue
        hp, ap = ln.get("homeScore"), ln.get("awayScore")
        he, ae = g.get("homePregameElo"), g.get("awayPregameElo")
        if hp is None or ap is None or he is None or ae is None:
            continue
        spreads = [x["spread"] for x in ln.get("lines", []) if x.get("spread") is not None]
        opens = [x["spreadOpen"] for x in ln.get("lines", []) if x.get("spreadOpen") is not None]
        if not spreads or not opens:
            continue
        rows.append({
            "season": y, "gid": gid, "home": ln["homeTeam"], "away": ln["awayTeam"],
            "margin": hp - ap, "elo_diff": he - ae,
            "spread_close": sum(spreads) / len(spreads),
            "spread_open": sum(opens) / len(opens),
        })

df = pd.DataFrame(rows)
print(f"Games with Elo + open + close spread: {len(df)}")

# Fit fair-value model: margin = alpha + beta * elo_diff  (OLS, in-sample fit
# across all 4 seasons -- this is the "objective" market-independent power
# rating conversion; intercept absorbs any average home-field edge baked
# into or missing from CFBD's Elo).
X = np.column_stack([np.ones(len(df)), df.elo_diff.values])
beta, *_ = np.linalg.lstsq(X, df.margin.values, rcond=None)
alpha, b = beta
df["proj_margin"] = alpha + b * df.elo_diff
df["proj_spread"] = -df.proj_margin  # model's fair home spread
print(f"Fit: margin = {alpha:.2f} + {b:.5f} * elo_diff  (n={len(df)})")
r2 = 1 - ((df.margin - df.proj_margin) ** 2).sum() / ((df.margin - df.margin.mean()) ** 2).sum()
print(f"In-sample R^2 of Elo->margin fit: {r2:.3f}")

df["edge_open"] = df.spread_open - df.proj_spread    # >0 => model says home undervalued at open
df["edge_close"] = df.spread_close - df.proj_spread

# CLV check: does the closing number move toward the model's fair value on
# average, relative to the open? (i.e. |spread_close - proj_spread| < |spread_open - proj_spread|)
moved_toward_model = (df.edge_close.abs() < df.edge_open.abs()).mean()
print(f"\nShare of games where closing line moved CLOSER to the Elo fair value than the open: {moved_toward_model:.1%}"
      f"  (50% = no systematic drift toward the model)")


def grade(edge, spread_col, threshold, label):
    bet_home = edge > threshold
    bet_away = edge < -threshold
    sub_h = df[bet_home]
    sub_a = df[bet_away]
    results_h = sub_h.margin + sub_h[spread_col]   # >0 home covers
    results_a = -sub_a.margin - sub_a[spread_col]  # >0 away covers (away spread = -home spread)
    covers = (results_h > 1e-9).sum() + (results_a > 1e-9).sum()
    pushes = (results_h.abs() <= 1e-9).sum() + (results_a.abs() <= 1e-9).sum()
    n = len(sub_h) + len(sub_a)
    denom = n - pushes
    if denom < 20:
        print(f"{label:60s} n={n:5d}  (too small)")
        return
    pct = covers / denom
    p = stats.binomtest(covers, denom, 0.5).pvalue
    flag = " *" if p < 0.05 else ""
    print(f"{label:60s} n={n:5d}  cover%={pct:5.1%}  p={p:.3f}{flag}")


print("\n=== Bet vs OPEN line when model disagrees, graded at OPEN number ===")
for thresh in [1, 2, 3, 5, 7]:
    grade(df.edge_open, "spread_open", thresh, f"Edge vs open >= {thresh} pts")

print("\n=== Bet vs CLOSE line when model disagrees, graded at CLOSE number ===")
for thresh in [1, 2, 3, 5, 7]:
    grade(df.edge_close, "spread_close", thresh, f"Edge vs close >= {thresh} pts")

df.to_csv("opening_line_test_games.csv", index=False)
