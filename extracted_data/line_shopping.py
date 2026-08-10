"""
Quantify the value of line shopping: for each game, compare covering the
CLOSING CONSENSUS (average across books) number vs. always taking the best
available number for whichever side you bet. This is a mechanical edge
(reduces effective vig) independent of whether your pick is any good.
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
book_counts = []
for y in YEARS:
    for g in load("lines", y):
        hp, ap = g.get("homeScore"), g.get("awayScore")
        if hp is None or ap is None:
            continue
        spreads = [x["spread"] for x in g.get("lines", []) if x.get("spread") is not None]
        if len(spreads) < 2:
            continue  # need >=2 books for "shopping" to mean anything
        book_counts.append(len(spreads))
        margin = hp - ap
        consensus = sum(spreads) / len(spreads)
        best_home = max(spreads)      # most home-friendly number available
        best_away = -min(spreads)     # most away-friendly number available (as away-relative spread)
        consensus_away = -consensus
        rows.append({
            "season": y, "gid": g["id"], "home": g["homeTeam"], "away": g["awayTeam"],
            "n_books": len(spreads), "margin": margin,
            "consensus": consensus, "best_home": best_home, "best_away": best_away,
            "book_spread_range": max(spreads) - min(spreads),
            # ATS result (points): margin + spread_used; >0 = cover, <0 = loss, 0 = push
            "home_consensus_result": margin + consensus,
            "home_best_result": margin + best_home,
            "away_consensus_result": -margin + consensus_away,
            "away_best_result": -margin + best_away,
        })

df = pd.DataFrame(rows)
print(f"Games with >=2 books quoting a closing spread: {len(df)}")
print(f"Avg books per game: {np.mean(book_counts):.1f}   Avg best-vs-worst spread gap: {df.book_spread_range.mean():.2f} pts"
      f"   (median {df.book_spread_range.median():.1f}, max {df.book_spread_range.max():.1f})")


def grade(series, label):
    n = len(series)
    covers = (series > 1e-9).sum()
    pushes = (series.abs() <= 1e-9).sum()
    losses = n - covers - pushes
    denom = n - pushes
    pct = covers / denom if denom else np.nan
    p = stats.binomtest(covers, denom, 0.5).pvalue if denom else np.nan
    print(f"{label:45s} n={n:5d}  covers={covers:5d}  losses={losses:5d}  pushes={pushes:4d}  cover%={pct:5.1%}  p={p:.3f}")
    return covers, denom


print("\n=== If you always bet HOME, consensus vs best-shopped number ===")
c1, d1 = grade(df.home_consensus_result, "Home, consensus (avg) spread")
c2, d2 = grade(df.home_best_result, "Home, best shopped spread")

print("\n=== If you always bet AWAY, consensus vs best-shopped number ===")
c3, d3 = grade(df.away_consensus_result, "Away, consensus (avg) spread")
c4, d4 = grade(df.away_best_result, "Away, best shopped spread")

# How often does shopping flip a result (loss->push->win) relative to consensus, per side
flips_home = ((df.home_consensus_result <= 1e-9) & (df.home_best_result > 1e-9)).sum()
flips_away = ((df.away_consensus_result <= 1e-9) & (df.away_best_result > 1e-9)).sum()
print(f"\nGames where shopping flipped a home non-cover into a home cover: {flips_home} / {len(df)} ({flips_home/len(df):.1%})")
print(f"Games where shopping flipped an away non-cover into an away cover: {flips_away} / {len(df)} ({flips_away/len(df):.1%})")

# Convert cover% improvement into breakeven terms at standard -110 vig (52.38% needed)
breakeven = 0.5238
home_shop_gain = c2 / d2 - c1 / d1
away_shop_gain = c4 / d4 - c3 / d3
print(f"\nCover% lift from shopping: home +{home_shop_gain:.2%} pts, away +{away_shop_gain:.2%} pts")
print(f"Standard -110 breakeven is {breakeven:.2%}. Best-number cover% (home)={c2/d2:.2%}, (away)={c4/d4:.2%}"
      f" vs breakeven {breakeven:.2%} -> {'ABOVE' if (c2/d2+c4/d4)/2 > breakeven else 'still BELOW'} breakeven on its own.")

df.to_csv("line_shopping_games.csv", index=False)
