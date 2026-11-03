# SP+ blend and ATS tiers (live from 2026-11-03, week 10)

## Margin formula
`model_margin = 0.7 * SP+ weekly projected margin + 0.3 * (preseason blend + HFA)`

- **SP+ weekly projection:** from Bill Connelly's public SP+ picks sheet, pulled by `fetch_spplus_picks.py` into `spplus_picks_{year}.csv`.
  - The sheet's Week 0 and Week 1 both map to CFBD week 1.
  - The projection already includes home field.
- **Preseason blend:** the existing average of the SP+, FPI, bottom-up model and Steele diffs, plus the tiered HFA.
- **Removed from the margin:** the one-pass SRS in-season rating (`build_in_season_ratings.py`). The script still runs, because model_total uses its off/def output.
- **Fallback:** when SP+ has no row for a game, the old formula is used ((1-w)·preseason + w·SRS + HFA). `model_source` records which formula built each game.

**Why 0.7:** the weight was varied from 0 to 1 on two seasons.
- 2025 used the 2-source replica (731 games). 2026 used the live model, weeks 1-9 (500 games).
- Accuracy (mean absolute error) and the edge-to-result correlation improved in both seasons.
- The best weight was 0.6-0.8 in each.

For 2026 weeks 3-9, by component:

| Component | ATS | MAE |
|---|---|---|
| SRS in-season rating alone | 48.4% | 13.99 |
| Preseason part alone | 53.3% | |
| SP+ alone | 52.3% | |
| 0.7 SP+ / 0.3 preseason | 55.5% | 11.58 |
| Old live model | 50.4% | 11.97 |

## ATS tiers (`ats_tier`, `ats_tier_reason`)
Each tier applies to the model's side of the market spread at projection time.

- **SKIP:** the side is an away favourite, or runs into a situational conflict (`situational_flags.py`):
  - **Letdown:** a P4 team coming off an upset win as an underdog, playing a P4 opponent. 43% cover, 2022-25.
  - **Losing-record home favourite:** 43% cover, 2022-25. This one went the other way in 2026 (15-8 when skipped). Watch it.
- **STRONG:** not skipped, and at least one of:
  - SP+ and the preseason blend each independently on that side of the market line.
  - The side is the home favourite.
- **NO SIGNAL:** everything else.

Model-vs-market gap size is not used: bigger gaps did not cover more often in either season.

**Backtest** (new blend; 2025 = replica preseason + SP+ sheet; 2026 = live preseason + SP+, weeks 1-9):

| Tier | 2025 | 2026 | Both |
|---|---|---|---|
| STRONG | 206-149 (58.0%) | 149-106 (58.4%) | 58.2% |
| NO SIGNAL | 84-99 (45.9%) | 56-38 (59.6%) | 50.5% |
| SKIP | 90-87 (50.8%) | 61-77 (44.2%) | 47.9% |

The production replay of 2026 weeks 1-9 through `build_week_projections.py --out-dir <scratch>` reproduced these figures: STRONG 146-106, SKIP 62-75, new model overall 54.8% against the old model's 48.4%.

**Caveats:**
- Two seasons is a small sample.
- The 0.7 weight and the home-favourite signal were partly chosen on this same data, so expect the forward record to come in lower.
- The closing line still has a lower MAE than any blend.
- The scorecard grades `ats_tier` from week 10 onward; earlier weeks were built before this change and have no tier.
