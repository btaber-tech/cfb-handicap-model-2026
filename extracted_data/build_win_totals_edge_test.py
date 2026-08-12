"""
Tests whether the win-totals engine's gap vs. real sportsbook lines predicts
actual over/under outcomes -- the actual edge question, not just whether the
model correlates with final win totals (that's build_win_totals_backtest.py).

Market lines are web-sourced DraftKings/consensus preseason win totals
(market_win_totals.py, pulled 2026-08-11 from sportsbettingdime.com).
2025 is a full ~134-team sample; 2023/2024 are Power-conference-only
(G5 rows weren't available from the source page) -- reported separately so
the smaller/biased samples don't get silently blended into the headline
number.
"""
import numpy as np
import pandas as pd

from market_win_totals import LINES_2023, LINES_2024, LINES_2025, MARKET_TO_INTERNAL

LINES_BY_SEASON = {2023: LINES_2023, 2024: LINES_2024, 2025: LINES_2025}


def add_market_line(df):
    def lookup(row):
        lines = LINES_BY_SEASON.get(row["season"], {})
        # try direct name, then the reverse-alias (internal name -> market name)
        for market_name, internal_name in MARKET_TO_INTERNAL.items():
            if internal_name == row["team"] and market_name in lines:
                return lines[market_name]
        return lines.get(row["team"])
    df = df.copy()
    df["market_line"] = df.apply(lookup, axis=1)
    return df


def summarize(df, label):
    d = df.dropna(subset=["market_line"]).copy()
    d["model_gap"] = d["expected_wins"] - d["market_line"]
    d["actual_over"] = d["wins"] > d["market_line"]  # push impossible, lines are X.5
    d["model_favors_over"] = d["model_gap"] > 0
    d["hit"] = d["model_favors_over"] == d["actual_over"]

    n = len(d)
    hit_rate = d["hit"].mean()
    r_gap_vs_actual = np.corrcoef(d["model_gap"], d["wins"] - d["market_line"])[0, 1]

    print(f"\n=== {label} (n={n}) ===")
    print(f"Model-favors-over hit rate: {hit_rate:.3f}  (breakeven at -110 is 0.524)")
    print(f"Correlation of model_gap vs (actual wins - market line): r={r_gap_vs_actual:.3f}")

    for thresh in [0.5, 1.0, 1.5, 2.0]:
        big = d[d["model_gap"].abs() >= thresh]
        if len(big) < 10:
            continue
        hr = big["hit"].mean()
        print(f"  |gap| >= {thresh}: n={len(big)}, hit rate={hr:.3f}")

    return d


def main():
    trans = pd.read_csv("win_totals_backtest_transitions.csv")
    trans = add_market_line(trans)

    all_d = []
    for season in [2023, 2024, 2025]:
        sub = trans[trans["season"] == season]
        note = " (Power-conference-only market sample)" if season in (2023, 2024) else " (full ~134-team sample)"
        d = summarize(sub, f"{season}{note}")
        all_d.append(d)

    pooled = pd.concat(all_d, ignore_index=True)
    pooled.to_csv("win_totals_edge_test_games.csv", index=False)
    summarize(pooled, "POOLED 2023-2025 (all seasons, mixed sample composition)")

    print("\nBiggest model-vs-market gaps (pooled):")
    print(pooled.reindex(pooled["model_gap"].abs().sort_values(ascending=False).index)
          [["season", "team", "expected_wins", "market_line", "model_gap", "wins", "hit"]]
          .head(15).to_string(index=False))


if __name__ == "__main__":
    main()
