# Phil Steele's 2026 College Football Preview — Extracted Data

Source: purchased digital edition of *Phil Steele's 2026 College Football Preview*
(Flipsnack flipbook, 380 pages, hosted at philsteele.com under Ben's account).

## How this was extracted (important — different method than the Athlon PDF)

This was **not** OCR'd by us. The Flipsnack viewer ships a full-text search
index client-side so its in-app search box works — every page's text is
pre-extracted (by Flipsnack's own pipeline, presumably OCR on their end since
the source is a scanned magazine) and sits in a JS object in the page
(`pages.data[id].extractedText`) as soon as the flipbook loads. We pulled that
object directly via the browser's JS console and saved it to a text file,
rather than screenshotting pages and running Tesseract ourselves. Quality is
much higher than our own OCR attempts — clean words, correct numbers, minimal
garbling — because it's whatever text layer/OCR Flipsnack generated at
upload time, not a screenshot-of-a-screenshot re-OCR.

Caveat: reading order follows Flipsnack's internal page order, which is
mostly clean but occasionally interleaves adjacent columns (schedule tables,
stat boxes, ATS trends) in a jumbled sequence — expect stats-heavy pages to
be harder to parse programmatically than prose. Treat this like the Athlon
narrative file: good for reading and for grabbing well-anchored data points,
not something to blindly regex without spot-checking.

### Files

- **phil_steele_2026_ocr.txt** — full extracted text, all 380 pages, in
  `=== PAGE N ===` blocks. ~4.7M characters, ~973K words. This is the primary
  source — read it directly or grep it for anything not covered below.
- **phil_steele_2026_team_pages.csv** — **team → starting page number**, all
  138 FBS teams, verified with no duplicates and no gaps. Each team's
  "position outlook" page is a 2-page spread: the page listed here (prose:
  position-by-position analysis — QB/RB/WR/OL/etc., transfers, returning
  starters) plus the following page (schedule, career stat leaders, ATS
  betting trends, "Signees" recruiting grade, last-5-bowls record, ratings
  header block with Homefield Edge / Schedule Difficulty numbers).

## What's on a team's pages (for model-weighting purposes)

- **Left/prose page**: position-group write-ups in Phil's own voice —
  returning production, portal adds/losses, staff continuity, snap counts,
  efficiency numbers. This is the highest-value qualitative content — it's
  where Phil's actual opinion lives, distinct from the raw stats blocks.
- **Right/data page**: 2026 schedule with game-by-game notes (mostly
  historical ATS trends per matchup, not projections), career passing/
  rushing/receiving leaders, last-7-years offense/defense splits, "2025
  Statistical Leaders," "2025 Game-by-Game Stats," and a ratings header with
  fields like `Phil's Homefield Edge`, `2026 Schedule Difficulty`, `Signees`
  grade, and `Last 5 Bowls` record. These labels only OCR'd cleanly on ~13
  of 138 team pages (column-bleed in that specific header graphic) — present
  but not reliably regex-extractable across the board; needs per-team
  spot-checking if you want them structured.
- There is **no single "predicted final record" field** printed per team the
  way Athlon prints one — Phil's forecast is expressed as prose in
  "PHIL'S FORECAST" callouts (national Top 25, conference-by-conference
  predicted order of finish, awards) rather than a per-team won-loss number.
  Search the text for `PHIL'S FORECAST` and `PHIL'S 2026 [CONFERENCE]
  FORECAST` to find these.

## Known gaps
- Two teams' section markers OCR'd as "POSITION OUTLOOK FOR **2025**"
  instead of 2026 (UCF, Louisiana Tech) — harmless once you know to search
  for both years; already accounted for when building the team-page index.
- No structured per-team CSV (record/coach/rating columns) built yet, unlike
  `athlon_2026_teams.csv`. The raw text is clean enough that this is
  buildable on request — flagged as next step, not done here.
