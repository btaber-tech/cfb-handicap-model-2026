"""
Results-tracking scorecard: grades the model's weekly projections
(week{N}_2026_projections.csv) against actual final scores once games
are played.

Purpose (per cfb-handicap-model-2026 project memory, priority (B)):
close the loop on the model by tracking real accuracy through the season
-- not a betting tool, since the backtest (cfb-backtest-findings-2026)
found no ATS edge; this is about knowing whether the SU/margin model is
actually performing as backtested once live 2026 data exists.

For every week{N}_{year}_projections.csv found on disk, pulls that
week's actual results from CFBD, joins on game_id, and grades:
  - straight-up (SU): did model_pick match the actual winner?
  - margin error: |signed model margin - actual margin|
  - ATS (informational only, NOT a claimed edge): did the model's picked
    side cover the market line that was quoted at projection time?
  - totals: model_total / market_total vs actual total, over/under hit.

Games not yet completed are skipped (silently -- normal mid-week state,
not an error). Output is a fresh season_scorecard_2026.csv (all graded
games, all weeks, overwritten each run -- cheap to recompute, avoids
any risk of stale/duplicated rows) plus a per-week and cumulative
summary printed to stdout.

Usage:
    python build_scorecard.py --year 2026
"""
import argparse
import glob
import os
import re

import pandas as pd

from cfbd_fetch import cfbd_get


def grade_week(year, week, proj_path):
    proj = pd.read_csv(proj_path)
    if "game_id" not in proj.columns:
        print(f"  week {week}: {proj_path} has no game_id column (built before the scorecard existed) -- skipping")
        return pd.DataFrame()

    games = cfbd_get("/games", params={"year": year, "week": week, "seasonType": "regular"})
    results_by_id = {
        g["id"]: g for g in games
        if g.get("completed") and g.get("homePoints") is not None and g.get("awayPoints") is not None
    }

    rows = []
    for _, r in proj.iterrows():
        g = results_by_id.get(r["game_id"])
        if g is None:
            continue  # not played yet, or postponed/no result -- skip, not an error

        home_pts, away_pts = g["homePoints"], g["awayPoints"]
        actual_margin = home_pts - away_pts  # positive = home won
        actual_winner = r["home"] if actual_margin > 0 else r["away"]
        actual_total = home_pts + away_pts

        signed_model_margin = r["model_margin"] if r["model_pick"] == r["home"] else -r["model_margin"]
        correct_pick = (r["model_pick"] == actual_winner)
        margin_error = abs(signed_model_margin - actual_margin)

        ats_result = None
        model_side_covered = None
        if pd.notna(r.get("market_home_margin")):
            home_covered = actual_margin > r["market_home_margin"]
            away_covered = actual_margin < r["market_home_margin"]
            if not home_covered and not away_covered:
                ats_result = "push"
            else:
                ats_result = "home_covered" if home_covered else "away_covered"
                model_picked_home = (r["model_pick"] == r["home"])
                model_side_covered = (model_picked_home and home_covered) or (not model_picked_home and away_covered)

        total_error_model = abs(r["model_total"] - actual_total) if pd.notna(r.get("model_total")) else None
        ou_result_model = None
        if pd.notna(r.get("model_total")):
            if actual_total > r["model_total"]:
                ou_result_model = "over"
            elif actual_total < r["model_total"]:
                ou_result_model = "under"
            else:
                ou_result_model = "push"

        rows.append({
            "year": year, "week": week, "game_id": r["game_id"], "date": r["date"],
            "away": r["away"], "home": r["home"],
            "model_pick": r["model_pick"], "model_margin_signed": round(signed_model_margin, 1),
            "actual_winner": actual_winner, "actual_margin": actual_margin,
            "away_pts": away_pts, "home_pts": home_pts,
            "correct_pick": correct_pick, "margin_error": round(margin_error, 1),
            "market_home_margin": r.get("market_home_margin"), "ats_result": ats_result,
            "model_side_covered": model_side_covered,
            "model_total": r.get("model_total"), "market_total": r.get("market_total"),
            "actual_total": actual_total, "total_error_model": round(total_error_model, 1) if total_error_model is not None else None,
            "ou_result_model": ou_result_model,
        })

    return pd.DataFrame(rows)


def summarize(df, label):
    if df.empty:
        print(f"  {label}: no completed games yet")
        return
    n = len(df)
    su_acc = df["correct_pick"].mean()
    mae = df["margin_error"].mean()
    print(f"  {label}: {n} games graded | SU accuracy {su_acc:.1%} | mean margin error {mae:.1f} pts")

    ats = df.dropna(subset=["model_side_covered"])
    if not ats.empty:
        print(f"    ATS (model's picked side vs. market line, informational only -- no backtested edge): "
              f"{ats['model_side_covered'].mean():.1%} cover rate over {len(ats)} games with a line")

    tot = df.dropna(subset=["total_error_model"])
    if not tot.empty:
        print(f"    Totals: mean model error {tot['total_error_model'].mean():.1f} pts over {len(tot)} games")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    args = ap.parse_args()
    year = args.year

    proj_files = sorted(
        glob.glob(f"week*_{year}_projections.csv"),
        key=lambda p: int(re.search(r"week(\d+)_", p).group(1)),
    )
    if not proj_files:
        print(f"No week*_{year}_projections.csv files found -- nothing to grade.")
        return

    all_graded = []
    print(f"Grading {len(proj_files)} week(s) of {year} projections against CFBD final scores...")
    for path in proj_files:
        week = int(re.search(r"week(\d+)_", path).group(1))
        graded = grade_week(year, week, path)
        if not graded.empty:
            summarize(graded, f"week {week}")
            all_graded.append(graded)
        else:
            print(f"  week {week}: no completed games yet")

    if not all_graded:
        print("\nNo completed games across any projected week yet -- nothing to score. "
              "This is expected before/during the season's first games.")
        return

    full = pd.concat(all_graded, ignore_index=True)
    out_path = f"season_scorecard_{year}.csv"
    full.to_csv(out_path, index=False)
    print(f"\nWrote {len(full)} graded games to {out_path}")

    print("\n=== Cumulative season-to-date ===")
    summarize(full, f"all weeks ({full['week'].min()}-{full['week'].max()})")


if __name__ == "__main__":
    main()
