"""
Situational ATS analysis on 2022-2025 CFBD data: test classic handicapping
biases (favorite/dog, home/road, rest, conference, line movement, time of
season) against the closing spread, with sample sizes and significance,
rather than taking them on faith.
"""
import json
import os
from collections import defaultdict
from datetime import datetime

import numpy as np
import pandas as pd
from scipy import stats

RAW = "cfbd_raw"
YEARS = [2022, 2023, 2024, 2025]


def load(name, year):
    with open(os.path.join(RAW, f"{name}_{year}.json"), encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Build per-game table: join games (context: week/conf/neutral/date) with
# lines (spread open/close, scores), compute rest days per team.
# ---------------------------------------------------------------------------
all_games = []
for y in YEARS:
    games = {g["id"]: g for g in load("games", y)}
    lines = load("lines", y)

    # rest days: sort each team's completed games by date, diff consecutive
    team_dates = defaultdict(list)
    for g in games.values():
        if not g.get("completed") or not g.get("startDate"):
            continue
        dt = datetime.fromisoformat(g["startDate"].replace("Z", "+00:00"))
        team_dates[g["homeTeam"]].append((dt, g["id"]))
        team_dates[g["awayTeam"]].append((dt, g["id"]))
    rest_lookup = {}  # (team, game_id) -> rest days since prior game
    for team, lst in team_dates.items():
        lst.sort()
        for i in range(1, len(lst)):
            rest = (lst[i][0] - lst[i - 1][0]).days
            rest_lookup[(team, lst[i][1])] = rest

    for ln in lines:
        gid = ln["id"]
        g = games.get(gid)
        if g is None or not g.get("completed"):
            continue
        hp, ap = ln.get("homeScore"), ln.get("awayScore")
        if hp is None or ap is None:
            continue
        spreads = [x["spread"] for x in ln.get("lines", []) if x.get("spread") is not None]
        opens = [x["spreadOpen"] for x in ln.get("lines", []) if x.get("spreadOpen") is not None]
        if not spreads:
            continue
        spread = sum(spreads) / len(spreads)          # closing, home-relative, negative = home favored
        spread_open = sum(opens) / len(opens) if opens else np.nan
        margin = hp - ap
        ats = margin + spread  # >0 home covers closing number
        all_games.append({
            "season": y, "week": g.get("week"), "gid": gid,
            "home": ln["homeTeam"], "away": ln["awayTeam"],
            "neutral": g.get("neutralSite"), "conf_game": g.get("conferenceGame"),
            "spread": spread, "spread_open": spread_open,
            "home_favorite": spread < 0,
            "abs_spread": abs(spread),
            "home_cover": np.sign(ats) if abs(ats) > 1e-9 else 0,  # 1 home covers, -1 away covers, 0 push
            "line_move": (spread - spread_open) if not np.isnan(spread_open) else np.nan,  # <0 moved toward home
            "home_rest": rest_lookup.get((ln["homeTeam"], gid), np.nan),
            "away_rest": rest_lookup.get((ln["awayTeam"], gid), np.nan),
        })

df = pd.DataFrame(all_games)
df = df[df.home_cover != 0]  # drop pushes for cover-rate calcs
df.to_csv("situational_games.csv", index=False)
print(f"Total graded games (pushes excluded): {len(df)}")


def cover_test(mask, label, side="favorite"):
    """side='favorite' or 'home': report cover rate for that side under mask."""
    sub = df[mask]
    n = len(sub)
    if n < 30:
        print(f"{label:55s} n={n:5d}  (too small)")
        return
    if side == "favorite":
        covers = ((sub.home_favorite & (sub.home_cover == 1)) | (~sub.home_favorite & (sub.home_cover == -1))).sum()
    elif side == "home":
        covers = (sub.home_cover == 1).sum()
    elif side == "away":
        covers = (sub.home_cover == -1).sum()
    elif side == "underdog":
        covers = ((sub.home_favorite & (sub.home_cover == -1)) | (~sub.home_favorite & (sub.home_cover == 1))).sum()
    pct = covers / n
    # two-sided binomial test vs 50%
    p = stats.binomtest(covers, n, 0.5).pvalue
    flag = " *" if p < 0.05 else ("  " if p < 0.10 else "")
    print(f"{label:55s} n={n:5d}  cover%={pct:5.1%}  p={p:.3f}{flag}")


print("\n=== Favorite vs Underdog (all games) ===")
cover_test(pd.Series(True, index=df.index), "All favorites", "favorite")
cover_test(pd.Series(True, index=df.index), "All underdogs", "underdog")

print("\n=== Home Favorite / Home Dog / Road Favorite / Road Dog ===")
cover_test(df.home_favorite, "Home favorites (cover as home)", "home")
cover_test(~df.home_favorite, "Home underdogs (cover as home)", "home")
cover_test(df.home_favorite, "Away underdogs when home favored (cover as away)", "away")
cover_test(~df.home_favorite, "Away favorites when home dog (cover as away)", "away")

print("\n=== By spread size (favorite cover%) ===")
buckets = [(0, 3), (3, 7), (7, 14), (14, 21), (21, 100)]
for lo, hi in buckets:
    mask = (df.abs_spread >= lo) & (df.abs_spread < hi)
    cover_test(mask, f"Favorite, spread [{lo},{hi})", "favorite")

print("\n=== Neutral site vs not (favorite cover%) ===")
cover_test(df.neutral == True, "Neutral site, favorite covers", "favorite")
cover_test(df.neutral == False, "Non-neutral, favorite covers", "favorite")

print("\n=== Conference vs non-conference game (favorite cover%) ===")
cover_test(df.conf_game == True, "Conference game, favorite covers", "favorite")
cover_test(df.conf_game == False, "Non-conference game, favorite covers", "favorite")

print("\n=== Rest advantage (home_rest - away_rest), home cover% ===")
df["rest_diff"] = df.home_rest - df.away_rest
for lo, hi, lbl in [(-100, -3, "home rest disadvantage (<=-4 days)"), (-3, 3, "similar rest (-2..+2)"), (3, 100, "home rest advantage (>=4 days)")]:
    mask = (df.rest_diff >= lo) & (df.rest_diff < hi) & df.rest_diff.notna()
    cover_test(mask, f"Home cover, {lbl}", "home")

print("\n=== Line movement: does the side the line moved toward cover the CLOSING number more? ===")
mv = df[df.line_move.notna() & (df.line_move != 0)]
moved_home = mv.line_move < 0   # line moved toward home (home got more favored / less points)
moved_away = mv.line_move > 0
n_h = len(mv[moved_home]); covers_h = (mv[moved_home].home_cover == 1).sum()
n_a = len(mv[moved_away]); covers_a = (mv[moved_away].home_cover == -1).sum()
if n_h > 30:
    p = stats.binomtest(covers_h, n_h, 0.5).pvalue
    print(f"{'Home covers when line moved toward home':55s} n={n_h:5d}  cover%={covers_h/n_h:5.1%}  p={p:.3f}")
if n_a > 30:
    p = stats.binomtest(covers_a, n_a, 0.5).pvalue
    print(f"{'Away covers when line moved toward away':55s} n={n_a:5d}  cover%={covers_a/n_a:5.1%}  p={p:.3f}")

print("\n=== By week of season (favorite cover%) ===")
for lo, hi, lbl in [(0, 5, "weeks 1-4 (early)"), (5, 10, "weeks 5-9 (mid)"), (10, 20, "weeks 10+ (late/postseason)")]:
    mask = (df.week >= lo) & (df.week < hi)
    cover_test(mask, f"Favorite covers, {lbl}", "favorite")
