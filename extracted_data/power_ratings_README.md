# 2026 Power Ratings — `cfb_2026_power_ratings.csv`

138 FBS teams, one row each. Built from three independent sources rather
than one black-box number, on purpose — agreement across sources is the
confidence signal, disagreement is where manual/Athlon qualitative
judgment (coaching change, portal churn, injuries) should override the
math.

## Columns

- **blended_rank / blended_score** — average of the three z-scored
  quantitative sources below. This is the main sort/rank column.
- **source_disagreement** — std. dev. of the three z-scores for that team.
  High = the sources disagree a lot; worth a manual look before trusting
  the blend (list of the 10 biggest included in the build script's
  output).
- **model_proj_margin_2026** — bottom-up: refit of the backtest model
  (`build_backtest.py`'s methodology) using 2025 final-season SP+/margin/
  havoc as "prior" inputs and 2026 recruiting/returning production as
  "incoming" inputs. In-sample R²=0.370 predicting next-season average
  margin (2022-2025 backtest). Talent composite was dropped from this
  refit because CFBD hasn't published a 2026 talent composite yet.
- **sp_plus / fpi** — the top-down composites pulled earlier (Bill
  Connelly's SP+, ESPN FPI), both already sophisticated preseason models
  in their own right.
- **national_forecast_rank** — Athlon's qualitative preseason rank, for
  comparison against the quantitative blend.
- Context columns: conference, 2025 record, head coach, returning starters
  (offense/defense counts from Athlon), incoming recruiting points,
  incoming returning-production %.

## Known data-quality caveats (inherited from the Athlon OCR extraction)

- **`North Dakota State` (MWC) and `Sacramento State` (MAC) are real 2026
  FBS newcomers, not OCR errors** — confirmed against the source PDF text
  (`athlon_2026_ocr.txt` line ~4061-4072): the Mountain West added UTEP,
  Northern Illinois, and convinced 10-time FCS champion North Dakota State
  to reclassify to FBS; the MAC separately added Sacramento State,
  bringing FBS to 138 teams. CFBD's own 2026 FBS team list and both SP+/
  FPI preseason sources confirm/include both. (An earlier pass here
  incorrectly flagged these as OCR misreads — that was wrong; corrected.)
  Practical effect: both get a `blended_score` from the 2 sources that do
  have them (SP+, FPI) — ND State ranks #91, Sacramento State #128.
  `model_proj_margin_2026` is genuinely NaN for both and can't be filled:
  the bottom-up model trains on 2025 FBS stats, and neither team played
  FBS in 2025. Returning-production % is unavailable for the same reason;
  recruiting points for 2026 *are* available and included.
- **Conference label OCR typos were fixed** in `athlon_2026_teams.csv`
  directly (`Bigten`→`Big Ten`, `Big12`→`Big 12`, `Mac`→`MAC`) — 22 rows
  affected, pure relabeling of known variants, not a guess.
- 10 other teams needed a name-alias map to join Athlon's spelling to
  CFBD's (Cal/California, Pitt/Pittsburgh, Miami (Fla.)/Miami, Miami
  (Ohio)/Miami (OH), FIU/Florida International, WKU/Western Kentucky,
  UMass/Massachusetts, San Jose State/San José State, Appalachian
  State/App State, ULM/UL Monroe) — handled in `build_2026_power_ratings.py`,
  no data lost.

## How to use this for handicapping, given the backtest findings

Per [[cfb-backtest-findings-2026]]-equivalent conclusions
(`backtest_README.md`, `situational_and_shopping_README.md`): this ranking
is well-supported for **straight-up win projections and relative team
strength**, not for beating closing spreads on its own. Practical use:
- Rank/compare teams, project game margins (this rating minus opponent's,
  plus a home-field adjustment) for scouting purposes.
- Use `source_disagreement` to flag games where the market (SP+/FPI/your
  model) might be less settled — that's where situational research (not in
  this data) has the most room to matter.
- Always shop the line (see `situational_and_shopping_README.md`) — small
  but real, free edge on top of any pick.
- Don't treat "my rating vs. the spread" as a standing bet signal — the
  backtest showed that doesn't clear the vig by itself.

Script: `build_2026_power_ratings.py`. Re-run any time the Athlon/SP+/FPI
source files are refreshed.
