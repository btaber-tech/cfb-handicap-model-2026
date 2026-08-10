"""
Adjustment #3: is the live model's flat +2.5 HFA / sigma=16.5 well-calibrated,
or is there a cheap, real refinement worth making (e.g. altitude teams)?

Method: for every FBS-vs-FBS game 2023-2025 (all weeks, not just week 1 --
need volume here), take prior-season SP+ diff (no HFA added) as a
team-quality-only projection, and look at the *leftover* average margin
(actual - sp_diff) split by neutral vs. home-site games. That leftover, for
non-neutral games, is model's empirical estimate of the average benefit of
being the home team net of quality -- directly comparable to the assumed 2.5.
"""
import json
import pandas as pd

trans = pd.read_csv("backtest_transitions.csv")
sp_lookup = trans.set_index(["season", "team"])["prior_sp_rating"].to_dict()

ALTITUDE_TEAMS = {"Wyoming", "Air Force", "Colorado State", "Colorado", "Utah", "BYU", "New Mexico"}

rows = []
for season in [2023, 2024, 2025]:
    games = json.load(open(f"cfbd_raw/games_{season}.json", encoding="utf-8"))
    for g in games:
        if g["seasonType"] != "regular" or not g["completed"]:
            continue
        if g["homeClassification"] != "fbs" or g["awayClassification"] != "fbs":
            continue
        home, away = g["homeTeam"], g["awayTeam"]
        sp_h, sp_a = sp_lookup.get((season, home)), sp_lookup.get((season, away))
        if sp_h is None or sp_a is None or pd.isna(sp_h) or pd.isna(sp_a):
            continue
        rows.append({
            "season": season, "home": home, "away": away,
            "actual_margin": g["homePoints"] - g["awayPoints"],
            "sp_diff": sp_h - sp_a,
            "neutral": g.get("neutralSite", False),
        })

df = pd.DataFrame(rows)
df["residual"] = df.actual_margin - df.sp_diff
print(f"n games: {len(df)}")

home_games = df[~df.neutral]
neutral_games = df[df.neutral]
print(f"\nHome-site games (n={len(home_games)}): mean residual (empirical HFA) = {home_games.residual.mean():+.2f} pts"
      f"  (model assumes +2.5)")
print(f"Neutral-site games (n={len(neutral_games)}): mean residual = {neutral_games.residual.mean():+.2f} pts"
      f"  (model assumes +0)")

alt_home = home_games[home_games.home.isin(ALTITUDE_TEAMS)]
other_home = home_games[~home_games.home.isin(ALTITUDE_TEAMS)]
print(f"\nAltitude-market home teams {sorted(ALTITUDE_TEAMS)} at home (n={len(alt_home)}):"
      f" mean residual = {alt_home.residual.mean():+.2f} pts")
print(f"All other home teams (n={len(other_home)}): mean residual = {other_home.residual.mean():+.2f} pts")

# Residual std, to sanity check sigma=16.5
print(f"\nOverall residual std dev (proxy for per-game unexplained variance): {df.residual.std():.2f}"
      f"  (model assumes sigma=16.5)")
print(f"Home-site games residual std: {home_games.residual.std():.2f}")
