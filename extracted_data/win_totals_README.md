# Season Win Totals — Methodology, Backtest, and Edge Test

## What this is
A projected 2026 regular-season win total (expected wins + full win-count
distribution) for all 138 FBS teams, built by simulating every game on each
team's actual schedule rather than just regressing on team quality directly.
Compared against real 2026 sportsbook win-total lines (DraftKings, via
sportsbettingdime.com, pulled 2026-08-11).

## Method
1. **Schedule**: full 2026 regular-season schedule for all 138 FBS teams,
   pulled from CFBD (`cfbd_raw/games_2026_full.json`) — excludes conference
   championship games and bowls, matching how sportsbooks define win-total
   futures.
2. **Per-game win probability**: same formula as the live weekly engine
   (`build_week_projections.py`) — blended margin = avg(SP+, FPI, bottom-up
   model diffs) + tiered home-field adjustment, win prob = normal
   CDF(margin / 18.4).
3. **FCS/lower-division opponents**: assigned a fixed proxy rating of
   **-28.7** on the SP+/FPI scale. Derived empirically (not guessed): FBS
   teams beat FCS opponents by ~31 points on average and win ~95.5% of the
   time (n=485 games, 2022-2025); regressing that margin against the FBS
   team's own SP+ and FPI ratings for the season (holding HFA fixed) gives
   an implied opponent rating of -28.55 (SP+) and -28.89 (FPI) — close
   enough to use one shared constant.
4. **Season win-count distribution**: each team's per-game win
   probabilities are combined via the exact **Poisson-binomial
   distribution** (independent, non-identical Bernoulli trials) — not just
   summed to a mean. This gives a real probability for any over/under line,
   not only an average.

Output: `season_win_totals_2026.csv` — `expected_wins`, `stdev_wins`,
`fair_win_line` (the model's own 50/50 line), `p10`/`p25`/`median`/`p75`/`p90`
win counts, plus `market_line` and `model_gap` vs. the real 2026 book line.

## Backtest 1: does the schedule simulation predict actual win totals?
`build_win_totals_backtest.py` — no-lookahead test on 2023-2025
(prior season's final SP+ only, since historical "preseason" SP+/FPI aren't
archived the way 2026's are; this is a *weaker* single-source version of the
live 3-source engine, so results here are a lower bound on the real thing).

- **r = 0.615 (R² = 0.378)** between projected and actual final wins,
  n=398 team-seasons — clearly better than a naive "predict = last year's
  wins" baseline (r=0.463, R²=0.214), and better than the flat SP+-vs-win%
  correlation from the original backtest (r=0.49, R²=0.244). Schedule-aware
  simulation adds real signal over team quality alone.
- MAE ≈ 2.0 wins, RMSE ≈ 2.45. Biggest misses are the expected outliers
  (Arizona State's 2023 miracle run, Indiana's 2024/2025 breakouts, Florida
  State's 2024 collapse) — things no prior-year rating could see coming.
- Full transition-level data: `win_totals_backtest_transitions.csv`.

## Backtest 2: is there an actual edge against real win-total lines?
`build_win_totals_edge_test.py`, using web-sourced DraftKings lines
(`market_win_totals.py`) for 2023-2025. **Mixed, inconclusive — do not treat
as a validated edge yet:**

| Season | Sample | Model-favors-over hit rate | Note |
|---|---|---|---|
| 2023 | Power-conf only, n=69 | 0.435 | **below** breakeven (0.524) |
| 2024 | Power-conf only, n=69 | 0.536 | roughly breakeven |
| 2025 | Full ~134 teams, n=127 | 0.638 | well above breakeven, hit rate climbs with gap size (up to 0.818 at \|gap\|≥2) |
| Pooled | n=265, mixed composition | 0.558 | above breakeven overall |

2023 and 2024 samples are Power-conference-only (the source page didn't
surface Group of 5 rows for those years), so they're not directly comparable
to 2025's full sample — the pooled number blends different populations and
shouldn't be over-trusted. 2025's result is the most complete and most
encouraging (hit rate scaling with gap size is a real calibration signal,
not just noise), but it's **one season**. Three years, with one clearly
losing year in the mix, is not enough to distinguish genuine skill from
variance.

**Verdict:** unlike the flat single-game spread market (4 separate tests,
consistently null, see `cfb-backtest-findings-2026`), season win totals
show a *plausible* edge that survived a first look rather than dying
immediately — worth tracking for real starting with the actual 2026 season
(where the live 3-source engine, sharper than this backtest's single-source
proxy, will be doing the projecting), not worth betting meaningfully on yet.

## Fix (2026-08-20): bottom-up model was compressing the blend

The blend averages 4 point-scale sources (SP+, FPI, this project's own
bottom-up model, Steele's Power Poll). Steele's rank was already being
z-scored and rescaled onto SP+'s point scale before blending — the
bottom-up model wasn't. Its native output scale runs at roughly half
SP+/FPI's std dev (13.25 and 11.37 vs. 6.29) even though it agrees with
them closely on *who's* good (correlates 0.73-0.79) — it's just far more
timid in points. Averaged in unscaled, that quietly pulled every blended
margin toward zero: good teams got dragged down, bad teams got dragged
up, and over a 12-game season that compounded into a visibly
too-compressed win-total spread — model_gap correlated **-0.73** with the
market line (the better the market rated a team, the more the model
claimed *below* the market, and vice versa for bad teams).

Fix: rescale the bottom-up model column the same way Steele's already is
(z-score across teams, multiply by SP+'s own std) before blending —
`model_proj_margin_2026_scaled` in `cfb_2026_power_ratings.csv`. Result:
correlation roughly halved to **-0.42**, and the season win-total spread
widened from a std dev of 1.46 to 1.69 wins (closer to the market's own
spread). Applied to both this script and the weekly game-projection
engine (`build_week_projections.py`); `build_week1_projections.py` (the
one-off record of the opening-slate run) also picked up the 4th source
(Steele) it was missing relative to its own published footer text, plus
the same rescale.

## 2026 output
`season_win_totals_2026.csv`, sorted by `model_gap` (model minus market).
Biggest overs (model likes the over): Vanderbilt (+1.5), Southern Miss
(+1.4), Rutgers/Louisiana Tech (+1.1). Biggest unders (model likes the
under): Oklahoma State (-1.9), UCLA (-1.3), Florida/Texas (-1.2). North
Dakota State has no market line yet (new FBS member, not yet posted by
books). Numbers reflect the 2026-08-20 bottom-up-model rescale above.

## Files
- `build_season_win_totals.py` — live 2026 projection engine
- `build_win_totals_backtest.py` — Backtest 1 (schedule simulation vs. actual wins)
- `build_win_totals_edge_test.py` — Backtest 2 (model gap vs. real lines)
- `market_win_totals.py` — web-sourced DraftKings win-total lines, 2023/2024/2025/2026
- `season_win_totals_2026.csv`, `win_totals_backtest_transitions.csv`, `win_totals_edge_test_games.csv`
