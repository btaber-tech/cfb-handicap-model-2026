# In-Season Ratings — `in_season_ratings_2026.csv`

Added 2026-09-14, after weeks 1-2 were in the books, per the
"preseason priors should decay in favor of in-season efficiency" plan in
project memory. Before this, the live model (`build_week_projections.py`)
was 100% preseason (SP+/FPI/Steele/bottom-up) with nothing reacting to
actual 2026 results.

## Method

`build_in_season_ratings.py --year 2026 --through-week N` computes a
one-pass Simple Rating System (SRS) number per team from every completed
FBS-vs-FBS game through week N:

    implied_rating(team) = (team's margin in that game, net of HFA)
                            + opponent's PRESEASON points-scale rating

...averaged across all games a team has played. Anchoring to the
preseason blend (instead of iterating SRS to convergence on its own) is
deliberate: with 1-2 games per team so far, a self-referential iterative
SRS would just amplify small-sample noise. This is exactly one iteration
of the standard method, using the existing preseason composite as the
opponent-strength prior.

Run this once per week, using the last fully-completed week, before
running `build_week_projections.py` for the upcoming week:

    python build_in_season_ratings.py --year 2026 --through-week 2

## How it's used

`build_week_projections.py` blends this in via `IN_SEASON_WEIGHT(week)`:
0% for weeks 1-2 (no data yet), then ramping — 15% at week 3, up to a
cap of 78% by week 7-8 — chosen as a **gradual ramp** (user's explicit
choice over an instant switch or holding off further), so 1-2 games of
noisy small-sample data can't swing the model early, while still letting
real 2026 performance start mattering right away. Falls back to pure
preseason (weight 0) for any specific game where either team has no
in-season rating yet (bye week, or the file hasn't been rebuilt).

Output columns added to `week{N}_2026_projections.csv`:
`in_season_weight`, `home_in_season_margin`, `away_in_season_margin`.

**Not backtested** — this schedule and method are a reasonable, standard
approach applied fresh for 2026, not validated against prior seasons run
through the same pipeline. Watch `season_scorecard_2026.csv` (SU
accuracy / margin error) as the weight ramps up through the season and
revisit the schedule in `in_season_weight()`
(`build_week_projections.py`) if accuracy doesn't hold up once it starts
carrying real weight (week 5+).

## Re-run recipe each week

1. `python build_in_season_ratings.py --year 2026 --through-week <last completed week>`
2. `python build_week_projections.py --year 2026 --week <upcoming week>`
3. `python build_artifact.py --year 2026 --week <upcoming week> --title "..."`
4. `python build_scorecard.py --year 2026` (grades the week that just finished)

Step 1 needs to happen before step 2 every week now — not yet folded
into the weekly cloud routine (`trig_014BFQ57a8qkzeePrvo2v5Wk`), which
still only runs step 2+3. **Next step if keeping this automated:** add
step 1 to that routine's prompt, or accept that the routine will silently
project on pure-preseason (weight falls back to 0) until it's added,
since `build_week_projections.py` degrades gracefully rather than
erroring if `in_season_ratings_2026.csv` is stale/missing.
