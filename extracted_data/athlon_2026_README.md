# College Football 2026 — Extracted/Sourced Data

## Preseason power ratings (non-Athlon sources)

- **sp_plus_2026_preseason.csv** — Bill Connelly's SP+ preseason ratings for all
  138 FBS teams (overall, offensive, defensive, special teams), sourced from
  ESPN. Opponent- and tempo-adjusted efficiency measure; see the project's
  metrics/weighting notes for how this is meant to anchor the model.
- **espn_fpi_2026_preseason.csv** — ESPN FPI preseason ratings, all 138 teams.
  Second quantitative opinion alongside SP+ (used in place of Phil Steele —
  his full 1-138 list is paywalled beyond a top-40, and the secondary sources
  found for it disagreed with each other, so it wasn't trustworthy enough to
  build on).

Both files' `team` column is aligned 1:1 with `athlon_2026_teams.csv`'s
naming (verified — no join mismatches across all three).

## Athlon 2026 Preview — Extracted Data

Source: `Athlon Sports College Football Preview 2026.pdf` (scanned/image-only, no text
layer — extracted via OCR: PyMuPDF render @ 200-400 DPI + Tesseract 5.5.3, 212 pages).

### Files

- **athlon_2026_teams.csv** — one row per FBS team (138 rows), structured fields
  (conference, predicted finish, 2025 record, coaching info, returning starters,
  OC/DC, stadium).
- **athlon_2026_schedules.csv** — **1,720 rows, all 138 FBS teams' full 2026
  schedules** (game number, date, opponent, matched FBS opponent name, home/away/
  neutral, match confidence). See "Schedule data provenance" below — this file
  went through two rounds of fixes after the initial extraction.
- **athlon_2026_narrative.txt** — full raw OCR text block per team (depth chart,
  scouting quotes, recruit lists, prose analysis) for anything not captured in
  the CSVs.
- **athlon_2026_ocr.txt** — the complete raw OCR of all 212 pages (Top 25, playoff
  bracket, bowl projections, All-America teams, unit rankings, conference
  previews, etc.).
- **extract_schedule.py / extract_schedule_fixup.py** — the column-aware
  schedule-extraction scripts (see provenance below).
- **manual_schedules_all15.py / manual_schedules_batch2.py** — hand-transcribed
  schedules (read directly off rendered page images) for the 37 teams the OCR
  pipeline couldn't extract reliably.

## Teams CSV columns

| Column | Confidence | Notes |
|---|---|---|
| `team`, `conference`, `conference_predicted_finish`, `national_forecast_rank` | High | Cross-checked against the magazine's own table of contents |
| `record_2025_overall`, `record_2025_conference` | High | |
| `head_coach`, `hc_record_at_school`, `hc_years_at_school`, `hc_career_record`, `hc_career_years` | High (137/138) | `hc_years` may show `N+` where Athlon printed a "+" for a long tenure; new hires show `0-0` / `0` years |
| `returning_starters_offense`, `returning_starters_defense` | High when present, but **only ~63% of teams (86/138) have this field** | Not a parsing gap — many team pages simply don't print the numbered depth-chart box (space went to a "scouting quote" sidebar instead). Blank ≠ zero — it means "not printed." |
| `offensive_coordinator`, `defensive_coordinator`, `location`, `stadium`, `stadium_capacity` | Medium | ~15–20% of rows have a stray trailing word/bowl name from OCR column-bleed. Good enough for reference joins; worth a manual glance if a specific value looks off. |
| Western Michigan head coach | Gap | Didn't OCR cleanly, left blank. |

## Schedule data provenance (important — read before trusting a row)

Getting a clean 2026 schedule out of this PDF took three passes because the
source layout (three side-by-side columns: 2025 results / 2026 schedule / top
10 recruits, under a colored banner header) fights column-based OCR in a few
different ways. Rows are tagged by how they were produced — `match_confidence`
of `1.0` on a **verified** team means "read directly off the image by a human/
vision pass," not an algorithmic score.

1. **101 teams — pass-1 automated extraction** (`extract_schedule.py`):
   TSV-level word positions from Tesseract locate the "2026 SCHEDULE" header
   and clip just that column. Fast and accurate when it works, and validated
   by opponent-name fuzzy-matching against the 138-team FBS list
   (`match_confidence` column is a real similarity score here).
2. **37 teams — manually transcribed** (`manual_schedules_all15.py` +
   `manual_schedules_batch2.py`): pass-1 either failed outright or produced
   implausible row counts (games <11 or >14), traced to two root causes:
   - **Colored header banners**: several teams' "2026 SCHEDULE" banner is
     white text reverse-printed on the team's (light) brand color. Grayscale
     conversion washes out the contrast and Tesseract drops the row entirely,
     so there's no text anchor to find the column by.
   - **Column bleed / CSV-quote corruption**: a literal `"` character in
     Tesseract's TSV output (from pull-quote captions, inch marks) was being
     swallowed by Python's default CSV quoting, corrupting word positions for
     large stretches of a page; separately, adjacent columns sometimes sit
     close enough that the results/schedule/recruits text runs together.
   These 37 teams were re-rendered at 150 DPI and the schedule read directly
   off the page image — no OCR involved, so treat them as ground truth:
   North Carolina, Wake Forest, Oklahoma State, UCF, Bowling Green, Missouri,
   Vanderbilt, Louisville, Virginia Tech, Purdue, Buffalo, UTEP, Boise State,
   Fresno State, Tennessee, Florida State, Georgia Tech, Illinois, Texas Tech,
   Washington, Wisconsin, WKU, Akron, Ole Miss, South Carolina, Arkansas, Army,
   Central Michigan, Georgia State, Navy, Notre Dame, Oklahoma, TCU, San Diego
   State, South Florida, Texas A&M, Washington State.
3. **The remaining ~101 pass-1 teams were sanity-checked by row count** (every
   team now has 11–14 games, the plausible range) **but not individually
   re-verified against the page image.** Nine teams show 11 games where 12 is
   more typical (Boston College, Eastern Michigan, Kansas State, Louisiana
   Tech, Missouri State, South Alabama, Southern Miss, Syracuse, Utah) — this
   *could* mean one game was missed by OCR on that page. Worth a spot-check
   before leaning heavily on those specific teams' schedules.

**`opponent_matched` is blank for ~29% of rows** — this is expected, not an
error: many "opponent_raw" values are FCS/buy-game opponents (e.g. Merrimack,
Robert Morris, Mercyhurst) that aren't in the 138-team FBS list, so they're
correctly left unmatched rather than force-fit to the nearest-spelled FBS
name. `home_away` is `neutral` for true neutral-site games (season openers in
Dublin, Atlanta, Nashville, etc., and the Army-Navy game).

## Deliberately left unstructured

**Top-10 recruit lists** are not parsed into columns — same column-bleed risk
as the schedules, and much lower value for a handicap model. Raw (unsplit)
text for each team is in `athlon_2026_narrative.txt`.

## Known gaps
- Western Michigan: head coach info didn't OCR cleanly in the teams CSV, left blank.
- 9 teams have 11 (not 12) 2026 schedule games — see "provenance" section above.
- This is a **preseason** publication — every ranking/prediction here is
  Athlon's opinion as of publication, not a stats-derived rating.
