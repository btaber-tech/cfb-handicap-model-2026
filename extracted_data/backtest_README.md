# 2022-2025 CFBD Backtest: What Actually Predicts Next-Season Performance

**Method:** Pulled 2022-2025 team-season data from CollegeFootballData.com
(advanced stats, SP+, returning production, recruiting, talent composite,
games, betting lines). Built three year-over-year transitions
(2022→2023, 2023→2024, 2024→2025), pairing each team's **end-of-year-N**
stats (SP+, opponent-adjusted efficiency, havoc, win%) and **incoming-to-
year-N+1** indicators (returning production, recruiting class, talent
composite) against that team's **actual year-N+1 outcome** (win%, ATS cover%).
n = 398 team-season transitions, pooled across all 3 year-pairs.

Scripts: `build_backtest.py`. Data: `cfbd_raw/` (raw JSON),
`cfbd_team_season.csv` / `cfbd_team_season_fbs.csv` (flattened per-team-season),
`backtest_transitions.csv` (the merged N→N+1 table),
`backtest_correlations.csv` (full correlation table).

## Finding 1: Win% next year is genuinely predictable

Best single predictors of next year's win% (pooled Pearson r):

| predictor | r | what it is |
|---|---|---|
| prior avg scoring margin | 0.51 | last year's point differential |
| prior SP+ rating | 0.49 | last year's SP+ overall |
| prior net PPA (off-def) | 0.46 | last year's opponent-adj. efficiency |
| prior win% | 0.46 | last year's raw record |
| prior net success rate | 0.45 | |
| prior net havoc | 0.42 | |
| incoming recruit class points | 0.30 | |
| incoming talent composite | 0.25 | |
| incoming returning production % | 0.18 | |

A **combined model** (SP+ + havoc + recruiting + talent + returning production,
standardized OLS) gets **R²=0.275** on next-year win%, vs. **R²=0.244** for
SP+ alone — recruiting/talent/returning production add real but modest
incremental signal on top of SP+. This matches the recommended weighting
philosophy: SP+ dominant, efficiency/havoc secondary, recruiting/returning
production a smaller boost. Raw last-year win% (0.46) is actually a *worse*
predictor than SP+ or margin — confirms treating raw W-L as a weak signal
was right.

## Finding 2: ATS cover% next year is essentially NOT predictable from team quality

This is the important one. Every single predictor above — SP+, efficiency,
havoc, recruiting, talent, returning production, even a team's *own* prior
ATS cover rate (does covering carry over? r = -0.02, no) — comes in at
**|r| < 0.08** against next-year ATS cover%. The combined multivariate model
gets **R² = 0.006** (essentially zero). Mean cover rate across all
team-seasons is 49.7%, almost exactly a coin flip (slightly under 50%,
consistent with the vig).

**What this means for the model:** team-quality metrics (SP+, efficiency,
recruiting, etc.) predict *how good a team actually is* well — but Vegas
already prices that into the spread. Being able to rank teams accurately
does not by itself produce a betting edge, because the market is doing the
same ranking. A quantitative power-rating model built purely from these
inputs will be good at picking straight-up winners and projecting margins,
but **will not beat the closing spread on its own**. Finding an actual ATS
edge requires something the market is *slower to price* — e.g., line
movement/CLV, injury/lineup news timing, situational spots (letdown/lookahead,
short rest, travel), or shopping for number/soft-book inefficiencies — not
just "my power rating says Team A is better than the market thinks," unless
your power rating is meaningfully sharper than the consensus. Straight
power-rating-vs-spread comparison is exactly the naive approach that this
backtest shows doesn't work.

## Practical implication for the 2026 model

- Use the SP+/efficiency/recruiting/talent blend to build a **straight-up win
  probability / projected margin model** — that part is well-supported by
  this backtest and worth building.
- Do **not** expect "my projected margin minus the Vegas spread" to be a
  profitable signal by itself. If ATS betting is the goal, the next layer of
  work is either (a) tracking line movement and CLV rather than static
  team-quality gaps, or (b) being honest that the model's value is for
  picking games/totals where you have a specific informational edge, not a
  blanket "bet whenever my rating disagrees with the line" rule.
