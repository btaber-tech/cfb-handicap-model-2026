# Totals backtest (2026-08-10)

Question: can this model's inputs (SP+ offense/defense split) project game
totals (home + away points), and is there any edge against posted
over/unders? Same design philosophy as `backtest_README.md` and
`situational_and_shopping_README.md` — test before trusting.

## Method

- `build_totals_backtest.py`, pooled across 2022→23, 23→24, 24→25 season
  transitions (n=2,210 FBS-vs-FBS regular season games, 2023-2025).
- No lookahead: uses each team's **prior-season final SP+ offense/defense
  ratings** (already sitting in `backtest_transitions.csv` as
  `prior_sp_off_rating`/`prior_sp_def_rating`) to project the *next*
  season's games — mirrors how the real pipeline uses preseason ratings for
  2026, not in-season-updated numbers.
- SP+ off/def ratings are already points-scaled (mean ≈25-26, matching
  real national scoring averages), so:
  `proj_total = (home_off + away_def)/2 + (away_off + home_def)/2`

## Findings

**Weak fit, weaker than the margin model and weaker than the market:**
- `proj_total` vs. actual total: **r=0.178** (p≈3e-17), raw **R²=-0.047**
  (raw scale is biased/miscalibrated — worse than guessing the mean).
- After a simple linear recalibration (`actual ≈ 32.26 + 0.39·proj`):
  **R²=0.032**. Still weak — compare to the margin-side model (season
  R²=0.33-0.37 from earlier backtests).
- The market's own closing total only reaches **r=0.346 (R²≈0.12)**
  against actual totals — confirming totals are *inherently* noisier than
  margins for everyone, not just this model. Per-game score totals depend
  heavily on pace matchups, weather, and blowout/garbage-time script that
  team-quality ratings don't capture.
- Tested adding a pace adjustment (prior-season plays/game, home+away
  averaged vs. national average): r moved 0.178 → 0.193. Not enough to
  justify the added complexity — **not adopted**.

**No betting edge vs. market total, at open or close:** hit rate testing
"model says over/under vs. market, did it hit" across gap thresholds
(any gap, ≥3, ≥5, ≥7, ≥10 pts) stayed in the 51-54% range, all
p>0.05 except one borderline case (|gap|≥7 vs. close: 53.7%, p=0.046) that
didn't hold at the next threshold up — a likely multiple-comparisons false
positive, not a real signal (same conclusion pattern as the 4 ATS tests in
`backtest_README.md`/`situational_and_shopping_README.md`).

## Practical use

`model_total` is now in `week1_2026_projections.csv` (calibrated,
`TOTAL_CAL_A`/`TOTAL_CAL_B` constants in `build_week1_projections.py`) —
shown as a **rough, low-confidence estimate for context**, same treatment
as the spread comparison: useful to sanity-check a market number or spot a
total that looks way out of line with team identity (e.g. two run-heavy
defenses priced at 65), **not a standing over/under betting signal.**

Two teams (North Dakota State, Sacramento State — both new 2026 FBS
members) have no `model_total`: no 2025 FBS SP+ offense/defense split
exists for them yet, same limitation noted for `model_proj_margin_2026` in
`power_ratings_README.md`.

Data: `totals_backtest_games.csv`. Script: `build_totals_backtest.py`.
