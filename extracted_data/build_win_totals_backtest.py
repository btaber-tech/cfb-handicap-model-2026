"""
Backtest for the season win-totals engine (build_season_win_totals.py).

No-lookahead design, same pattern as the original backtest
(cfb-backtest-findings-2026): for each transition year N -> N+1
(2022->23, 2023->24, 2024->25), use ONLY team N's final SP+ rating
(cfbd_team_season_fbs.csv, season==N) as the "preseason" rating proxy for
season N+1, run it through year N+1's REAL schedule (cfbd_raw/games_{N+1}.json,
already-completed games) with the same per-game formula as the live engine,
sum to expected wins, and correlate against N+1's actual final win total.

This isolates whether schedule-aware win projection has real skill -- it's
a single-source-rating version (no FPI/bottom-up blend, since those aren't
available uniformly as historical no-lookahead preseason numbers), so it's
expected to underperform the live 3-source 2026 engine slightly, but should
land in the same ballpark as the SP+-alone r=0.49 win% correlation already
found in the original backtest.
"""
import json
import math

import numpy as np
import pandas as pd

from build_season_win_totals import poisson_binomial_pmf, fair_line

HFA_BASE = 2.9
HFA_NEUTRAL = 1.8
HFA_ALTITUDE = 6.0
ALTITUDE_TEAMS = {"Air Force", "BYU", "Colorado", "Colorado State", "New Mexico", "Utah", "Wyoming"}
SIGMA = 18.4
FCS_PROXY_RATING = -28.7


def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def project_season(year_pred, prior_ratings):
    """prior_ratings: dict team -> rating (prior-season final SP+, no lookahead)."""
    games = json.load(open(f"cfbd_raw/games_{year_pred}.json", encoding="utf-8"))
    team_games = {t: [] for t in prior_ratings}

    for g in games:
        home, away = g["homeTeam"], g["awayTeam"]
        home_fbs = g["homeClassification"] == "fbs"
        away_fbs = g["awayClassification"] == "fbs"
        if not (home_fbs or away_fbs):
            continue

        hr = prior_ratings.get(home) if home_fbs else FCS_PROXY_RATING
        ar = prior_ratings.get(away) if away_fbs else FCS_PROXY_RATING
        if hr is None or ar is None:
            continue  # FBS team with no prior-year rating (promoted from FCS etc.)

        neutral = g.get("neutralSite", False)
        if neutral:
            hfa = HFA_NEUTRAL
        elif home in ALTITUDE_TEAMS:
            hfa = HFA_ALTITUDE
        else:
            hfa = HFA_BASE
        model_margin = (hr - ar) + hfa
        home_wp = norm_cdf(model_margin / SIGMA)

        if home_fbs and home in team_games:
            team_games[home].append(home_wp)
        if away_fbs and away in team_games:
            team_games[away].append(1 - home_wp)

    rows = []
    for team, probs in team_games.items():
        if not probs:
            continue
        pmf = poisson_binomial_pmf(probs)
        rows.append({
            "season": year_pred, "team": team,
            "games_scheduled": len(probs),
            "expected_wins": sum(probs),
            "fair_win_line": fair_line(pmf),
        })
    return pd.DataFrame(rows)


def main():
    team_season = pd.read_csv("cfbd_team_season_fbs.csv")
    all_results = []

    for year_pred in [2023, 2024, 2025]:
        prior_year = year_pred - 1
        prior = team_season[team_season["season"] == prior_year].set_index("team")["sp_rating"].to_dict()
        proj = project_season(year_pred, prior)

        actual = team_season[team_season["season"] == year_pred][["team", "wins", "games", "win_pct"]]
        merged = proj.merge(actual, on="team", how="inner")
        merged["transition"] = f"{prior_year}->{year_pred}"
        all_results.append(merged)
        print(f"{prior_year}->{year_pred}: {len(merged)} team-seasons matched "
              f"({len(proj)} projected, {len(actual)} actual)")

    df = pd.concat(all_results, ignore_index=True)
    df["error"] = df["expected_wins"] - df["wins"]
    df.to_csv("win_totals_backtest_transitions.csv", index=False)

    r = np.corrcoef(df["expected_wins"], df["wins"])[0, 1]
    mae = df["error"].abs().mean()
    rmse = (df["error"] ** 2).mean() ** 0.5
    bias = df["error"].mean()

    print(f"\n=== Pooled backtest (n={len(df)} team-seasons, 2023-2025) ===")
    print(f"Pearson r (expected_wins vs actual wins): {r:.3f}  (R^2={r**2:.3f})")
    print(f"MAE: {mae:.2f} wins   RMSE: {rmse:.2f} wins   Mean bias: {bias:+.2f} wins")

    # Naive baseline: predict this year's win total = prior year's actual win total (games-scaled)
    prior_wins = team_season.set_index(["season", "team"])["wins"]
    df["naive_prior_wins"] = df.apply(
        lambda row: prior_wins.get((row["season"] - 1, row["team"])), axis=1
    )
    nb = df.dropna(subset=["naive_prior_wins"])
    r_naive = np.corrcoef(nb["naive_prior_wins"], nb["wins"])[0, 1]
    mae_naive = (nb["naive_prior_wins"] - nb["wins"]).abs().mean()
    print(f"\nNaive baseline (predict = prior year's actual wins), n={len(nb)}:")
    print(f"Pearson r: {r_naive:.3f}  (R^2={r_naive**2:.3f})   MAE: {mae_naive:.2f} wins")

    # Over/under hit rate at the model's own fair_win_line, using actual wins
    df["actual_over"] = df["wins"] > df["fair_win_line"]
    print(f"\nFair-line calibration check: mean(actual_over) should be ~0.5 if lines are well-centered: "
          f"{df['actual_over'].mean():.3f}")

    print("\nBiggest misses (|error| desc):")
    print(df.reindex(df["error"].abs().sort_values(ascending=False).index)
          [["transition", "team", "expected_wins", "wins", "error"]].head(15).to_string(index=False))


if __name__ == "__main__":
    main()
