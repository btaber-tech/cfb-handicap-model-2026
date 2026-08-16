"""
Render the self-contained HTML artifact source for a week's CFB model
projections. Reads the CSVs produced by build_week_projections.py
(week{N}_{year}_projections.csv / _fbs_vs_other.csv) and renders the same
visual format used for the original Week 0/1 opening-slate artifact,
generalized to any week/year so it can be re-run by the automated weekly
routine without hand-editing.

Usage:
    python build_artifact.py --year 2026 --week 2
    python build_artifact.py --year 2026 --week 2 --title "Week 2" --out week2_2026_artifact_src.html

Design/caveat language mirrors extracted_data/cfb-backtest-findings-2026
(no demonstrated ATS/totals edge -- market numbers are reference only).
"""
import argparse
import html as html_lib
import math
from datetime import datetime

import pandas as pd

CSS = """
:root {
  --bg: #f5f4ef;
  --surface: #ffffff;
  --surface-2: #edece4;
  --border: #dcd8ca;
  --text: #1a1e19;
  --text-muted: #656a5e;
  --accent: #2f6b4f;
  --accent-soft: #e3ede7;
  --gold: #9c7a23;
  --gold-soft: #f2ead2;
  --font-display: Georgia, "Iowan Old Style", "Palatino Linotype", serif;
  --font-body: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  --font-mono: ui-monospace, "SFMono-Regular", "Cascadia Mono", Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #12140f; --surface: #191c15; --surface-2: #20241b; --border: #33382c;
    --text: #edeee6; --text-muted: #9aa090; --accent: #5da682; --accent-soft: #1f2f26;
    --gold: #d1ab52; --gold-soft: #2b2617;
  }
}
:root[data-theme="dark"] {
  --bg: #12140f; --surface: #191c15; --surface-2: #20241b; --border: #33382c;
  --text: #edeee6; --text-muted: #9aa090; --accent: #5da682; --accent-soft: #1f2f26;
  --gold: #d1ab52; --gold-soft: #2b2617;
}
* { box-sizing: border-box; }
body { background: var(--bg); color: var(--text); font-family: var(--font-body); margin: 0; padding: 0 0 4rem; line-height: 1.45; }
.wrap { max-width: 920px; margin: 0 auto; padding: 0 1.5rem; }
header.masthead { border-bottom: 1px solid var(--border); padding: 2.75rem 0 1.75rem; margin-bottom: 2rem; }
.eyebrow { font-family: var(--font-mono); font-size: 0.72rem; letter-spacing: 0.11em; text-transform: uppercase; color: var(--accent); margin: 0 0 0.6rem; }
h1 { font-family: var(--font-display); font-size: 2.15rem; font-weight: 700; margin: 0 0 0.5rem; text-wrap: balance; letter-spacing: -0.01em; }
.subhead { color: var(--text-muted); font-size: 0.98rem; max-width: 60ch; margin: 0; }
.stat-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 1px; background: var(--border); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; margin: 1.75rem 0 0; }
.stat { background: var(--surface); padding: 0.9rem 1.1rem; }
.stat .n { font-family: var(--font-mono); font-size: 1.5rem; font-weight: 600; font-variant-numeric: tabular-nums; display: block; }
.stat .l { color: var(--text-muted); font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.06em; }
.callout { background: var(--accent-soft); border: 1px solid var(--border); border-left: 3px solid var(--accent); border-radius: 8px; padding: 0.9rem 1.1rem; font-size: 0.88rem; color: var(--text); margin: 1.5rem 0 2.5rem; }
.callout strong { color: var(--accent); }
section.week { margin-bottom: 3rem; }
.week-heading { display: flex; align-items: baseline; gap: 0.6rem; margin-bottom: 1.1rem; }
.week-heading h2 { font-family: var(--font-display); font-size: 1.4rem; margin: 0; }
.week-heading .range { color: var(--text-muted); font-size: 0.85rem; font-family: var(--font-mono); }
.day-block { margin-bottom: 1.6rem; }
.day-heading { font-family: var(--font-mono); font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); margin: 0 0 0.5rem; padding-bottom: 0.35rem; border-bottom: 1px dashed var(--border); }
.col-legend { display: grid; grid-template-columns: 2fr 0.85fr 1.05fr 0.95fr 0.9fr; gap: 0.75rem; padding: 0 0.2rem 0.5rem; font-family: var(--font-mono); font-size: 0.66rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted); }
.col-legend span:not(:first-child) { text-align: right; }
.game-list { display: flex; flex-direction: column; }
.game-row { display: grid; grid-template-columns: 2fr 0.85fr 1.05fr 0.95fr 0.9fr; gap: 0.75rem; align-items: center; padding: 0.7rem 0.2rem; border-bottom: 1px solid var(--border); }
.game-row:last-child { border-bottom: none; }
.matchup { font-size: 0.95rem; font-weight: 500; }
.at { color: var(--text-muted); font-weight: 400; font-size: 0.85em; }
.flag { color: var(--gold); font-size: 0.7em; cursor: help; margin-left: 0.1em; }
.home-tag { color: var(--accent); font-size: 0.68em; font-weight: 700; font-family: var(--font-mono); vertical-align: 0.15em; margin-left: 0.25em; }
.ranks { font-size: 0.76rem; color: var(--text-muted); margin-top: 0.15rem; }
.rank { font-family: var(--font-mono); }
.pick-name { font-weight: 600; font-size: 0.92rem; }
.pick-margin { font-family: var(--font-mono); font-size: 0.78rem; color: var(--accent); font-variant-numeric: tabular-nums; }
.game-wp { min-width: 0; }
.wp-bar-track { height: 6px; background: var(--surface-2); border-radius: 3px; overflow: hidden; margin-bottom: 0.3rem; }
.wp-bar-fill { height: 100%; background: var(--accent); border-radius: 3px; }
.wp-label { font-family: var(--font-mono); font-size: 0.74rem; color: var(--text-muted); font-variant-numeric: tabular-nums; }
.game-market { font-family: var(--font-mono); font-size: 0.82rem; text-align: right; }
.market-num { color: var(--gold); font-weight: 600; }
.gap-note { display: block; font-family: var(--font-mono); font-size: 0.7rem; color: var(--text-muted); margin-top: 0.15rem; }
.gap-note.big-gap { color: var(--gold); font-weight: 700; }
.game-row.big-gap { background: var(--gold-soft); border-radius: 6px; }
.muted { color: var(--text-muted); }
.game-total { font-family: var(--font-mono); font-size: 0.82rem; text-align: right; }
.total-num { font-weight: 600; }
.total-mkt { display: block; font-size: 0.68rem; color: var(--text-muted); font-weight: 400; }
details.buy-games { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 0.9rem 1.1rem; }
details.buy-games summary { cursor: pointer; font-weight: 600; font-size: 0.95rem; list-style: none; }
details.buy-games summary::-webkit-details-marker { display: none; }
details.buy-games summary::before { content: "\\25b8 "; color: var(--accent); }
details.buy-games[open] summary::before { content: "\\25be "; }
.buy-day { margin-top: 1rem; }
.buy-day h4 { font-family: var(--font-mono); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.07em; color: var(--text-muted); margin: 0 0 0.4rem; }
.buy-list { list-style: none; margin: 0; padding: 0; columns: 2; column-gap: 1.5rem; font-size: 0.85rem; }
.buy-list li { margin-bottom: 0.3rem; break-inside: avoid; }
.buy-team { font-weight: 600; }
.buy-opp { color: var(--text-muted); }
.buy-tag { font-family: var(--font-mono); font-size: 0.65rem; color: var(--text-muted); border: 1px solid var(--border); border-radius: 3px; padding: 0 0.3rem; margin-left: 0.3rem; }
footer.notes { margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid var(--border); color: var(--text-muted); font-size: 0.82rem; }
footer.notes p { margin: 0 0 0.7rem; }
footer.notes code { font-family: var(--font-mono); background: var(--surface-2); padding: 0.1rem 0.3rem; border-radius: 3px; font-size: 0.85em; }
@media (max-width: 640px) {
  .game-row { grid-template-columns: 1fr 1fr; row-gap: 0.4rem; }
  .game-market, .game-total { text-align: left; }
  .col-legend { display: none; }
  .buy-list { columns: 1; }
}
"""

CALLOUT = """
    <strong>Reading this:</strong> "Win prob" and margin come from blending SP+, ESPN FPI, this
    project's bottom-up 2026 model, and Phil Steele's Power Poll, plus a home-field adjustment.
    The home team is marked <span class="home-tag" style="margin-left:0">HOME</span> (neutral-site
    games have no marker, since neither side is truly home). The backtest found these inputs
    predict <strong>straight-up wins and margins well</strong> but have <strong>no demonstrated edge against the
    closing spread</strong> (r&lt;0.08 on cover rate across 4 separate tests). <strong>Totals are shown too, but
    trust them less</strong> &mdash; a separate backtest found game totals are far noisier than margins for
    everyone, including Vegas (model R&sup2;=0.03, market itself only R&sup2;=0.12), with no edge there
    either. Market numbers are shown for reference/line-shopping only &mdash; the model-vs-market gap is
    shown on every game as a <strong>% of the market's own line</strong> (a 12pt gap matters less on a
    40pt favorite than a 6pt gap does on a 1.5pt line) and <strong>highlighted gold at 25%+</strong>, or
    3+ raw points for near-even lines where a percentage stops being meaningful. Either way it's a
    "look closer" flag, not a bet signal by itself (no backtested edge tracks with gap size). A
    <span class="flag">&#9888;</span> next to a team means SP+/FPI/the
    bottom-up model/Steele unusually disagree on that team (top 10% of all 138 teams) &mdash; hover for the
    number, and treat that game's projection as softer than usual.
"""

FOOTER = """
    <p>Model: <code>margin = avg(SP+, FPI, bottom-up 2026 model, Steele Power Poll) + tiered home-field advantage</code>,
    win probability from a normal CDF (&sigma;=18.4). Steele's Power Poll (his own blend of 9 talent-rating
    systems) is rescaled from an ordinal 1-138 rank to a point scale comparable to SP+/FPI before averaging in
    -- included at equal weight to the other three sources, deliberately weighted above Athlon's national rank
    (comparison-only, not blended in). HFA/sigma recalibrated against 2,210 FBS games
    (2023-2025): +2.9 at a true home site, +1.8 at a "neutral" site (most still favor one side),
    +6.0 for altitude-market home teams (Air Force, BYU, Colorado, Colorado State, New Mexico, Utah,
    Wyoming). Totals are a calibrated SP+ offense/defense matchup average -- weak signal (R&sup2;&asymp;0.03),
    shown as context only.</p>
    <p>Data: CollegeFootballData.com (games/lines/SP+/FPI/recruiting/returning production),
    ESPN FPI, Phil Steele's 2026 CFB Preview, this project's bottom-up 2026 power ratings.</p>
"""


def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


# Games where the model-vs-market gap clears this get a bolded gap + a highlighted
# row -- purely a "look closer" flag (per the backtest, gap size isn't itself a
# demonstrated bet signal), not a change in confidence.
#
# Measured as % of the market's own line rather than raw points once that line
# is big enough for a percentage to mean anything: a 12pt gap on a 40pt market
# favorite barely changes who wins or by roughly how much, while a 6pt gap on a
# 1.5pt line flips a coin-flip into a clear side -- percentage-of-the-line
# tracks that better than a flat point threshold. Below GAP_PCT_MIN_MARKET the
# market number is too close to zero for a percentage to be meaningful (a 2pt
# gap on a 0.5pt "line" would read as 400%), so those near-pick'em games fall
# back to a flat point threshold instead.
GAP_PCT_THRESHOLD = 25.0
GAP_PCT_MIN_MARKET = 3.0
GAP_ABS_THRESHOLD = 3.0


def esc(s):
    return html_lib.escape(str(s), quote=True)


def day_heading(date_str):
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return d.strftime("%a %b ") + str(d.day)


def build_game_row(row):
    home, away = row["home"], row["away"]
    neutral = bool(row.get("neutral", False))
    matchup_sep = "vs" if neutral else "@"
    # Convention: neutral-site shows "home vs away"; normal shows "away @ home"
    left, right = (home, away) if neutral else (away, home)

    dteam = row.get("disagreement_team")
    dval = row.get("disagreement_value")
    flags = {}
    if pd.notna(dteam):
        flags[dteam] = dval

    def name_with_flag(team):
        name = esc(team)
        if team in flags:
            title = (f"SP+/FPI/bottom-up model disagree unusually widely on {esc(team)} "
                     f"({flags[team]:.2f} spread of z-scores) &mdash; worth a manual/qualitative look")
            name += f'<sup class="flag" title="{title}">&#9888;</sup>'
        # Explicit home-team marker, on top of the "away @ home" / "home vs
        # away" word-order convention already in matchup_sep -- not
        # everyone reads that as a home/away signal at a glance.
        if not neutral and team == home:
            name += '<span class="home-tag" title="Home team">HOME</span>'
        return name

    matchup = f'{name_with_flag(left)} <span class="at">{matchup_sep}</span> {name_with_flag(right)}'

    home_rank = row.get("home_blended_rank")
    away_rank = row.get("away_blended_rank")
    left_rank = home_rank if neutral else away_rank
    right_rank = away_rank if neutral else home_rank
    ranks = (f'<span class="rank">#{int(left_rank)}</span> vs <span class="rank">#{int(right_rank)}</span>'
             if pd.notna(left_rank) and pd.notna(right_rank) else "")

    wp = row["home_win_prob"]
    pick = row["model_pick"]
    pick_is_home = pick == home
    pick_wp = wp if pick_is_home else 1 - wp
    bar_pct = pick_wp * 100

    market_html = f'{esc(pick)} <span class="muted">no line yet</span>'
    row_is_big_gap = False
    if pd.notna(row.get("market_home_margin")):
        mkt_margin = row["market_home_margin"]
        mkt_team = home if mkt_margin > 0 else away
        market_html = f'{esc(mkt_team)} <span class="market-num">{-abs(mkt_margin):.1f}</span>'
        gap = row.get("model_vs_market_gap")
        if pd.notna(gap):
            abs_gap, abs_mkt = abs(gap), abs(mkt_margin)
            if abs_mkt >= GAP_PCT_MIN_MARKET:
                pct_gap = abs_gap / abs_mkt * 100
                row_is_big_gap = pct_gap >= GAP_PCT_THRESHOLD
                gap_text = f"gap {pct_gap:.0f}%"
            else:
                row_is_big_gap = abs_gap >= GAP_ABS_THRESHOLD
                gap_text = f"gap {abs_gap:.1f} pts"
            gap_class = "gap-note big-gap" if row_is_big_gap else "gap-note"
            market_html += f'<span class="{gap_class}">{gap_text}</span>'

    total_html = '<span class="muted">&mdash;</span>'
    if pd.notna(row.get("model_total")):
        total_html = f'<span class="total-num">{row["model_total"]:.1f}</span>'
        if pd.notna(row.get("market_total")):
            total_html += f'<span class="total-mkt">mkt {row["market_total"]:.1f}</span>'

    row_class = "game-row big-gap" if row_is_big_gap else "game-row"
    return f"""        <div class="{row_class}">
          <div class="game-main">
            <div class="matchup">{matchup}</div>
            <div class="ranks">{ranks}</div>
          </div>
          <div class="game-pick">
            <div class="pick-name">{esc(pick)}</div>
            <div class="pick-margin">by {row['model_margin']:.1f}</div>
          </div>
          <div class="game-wp">
            <div class="wp-bar-track"><div class="wp-bar-fill" style="width:{bar_pct:.1f}%"></div></div>
            <div class="wp-label">{bar_pct:.0f}% win prob</div>
          </div>
          <div class="game-market">{market_html}</div>
          <div class="game-total">{total_html}</div>
        </div>"""


def build_day_block(date_str, rows):
    games_html = "\n\n".join(build_game_row(r) for _, r in rows.iterrows())
    return f"""        <div class="day-block">
          <h3 class="day-heading">{day_heading(date_str)}</h3>
          <div class="game-list">
{games_html}</div>
        </div>"""


def build_buy_games(other_df, label):
    if other_df.empty:
        return ""
    days = []
    for date_str, grp in other_df.groupby("date"):
        items = "\n".join(
            f'<li><span class="buy-team">{esc(r["fbs_team"])}</span> vs <span class="buy-opp">{esc(r["opponent"])}</span> '
            f'<span class="buy-tag">{esc(r["home_away"])}</span></li>'
            for _, r in grp.iterrows()
        )
        days.append(f'<div class="buy-day"><h4>{day_heading(date_str)}</h4><ul class="buy-list">{items}</ul></div>')
    days_html = "\n".join(days)
    return f"""
  <section class="week">
    <details class="buy-games">
      <summary>{len(other_df)} {label} games vs. FCS/non-FBS opponents (no rating to project against)</summary>
      {days_html}
    </details>
  </section>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--title", default=None, help='e.g. "Week 2" (default: "Week {N}")')
    ap.add_argument("--proj-csv", default=None)
    ap.add_argument("--other-csv", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    year, week = args.year, args.week
    title = args.title or f"Week {week}"
    proj_csv = args.proj_csv or f"week{week}_{year}_projections.csv"
    other_csv = args.other_csv or f"week{week}_{year}_fbs_vs_other.csv"
    out_path = args.out or f"week{week}_{year}_artifact_src.html"

    df = pd.read_csv(proj_csv)
    try:
        other_df = pd.read_csv(other_csv)
    except FileNotFoundError:
        other_df = pd.DataFrame(columns=["date", "fbs_team", "opponent", "home_away"])

    dates = sorted(df["date"].unique())
    date_range = f"{day_heading(dates[0])} &ndash; {day_heading(dates[-1])}" if dates else ""
    n_home_fav = int((df["model_pick"] == df["home"]).sum())
    n_road_fav = int((df["model_pick"] == df["away"]).sum())

    day_blocks = "\n\n".join(build_day_block(d, grp) for d, grp in df.groupby("date"))
    buy_games_html = build_buy_games(other_df, title)

    now = datetime.now()
    generated = f"{now.strftime('%B')} {now.day}, {now.year}"

    html_out = f"""<title>2026 CFB Model &mdash; {esc(title)}</title>
<meta name="description" content="Model projections for 2026 college football {esc(title)}.">
<style>
{CSS}
</style>

<div class="wrap">
  <header class="masthead">
    <p class="eyebrow">2026 CFB Handicap Model &middot; Generated {generated}</p>
    <h1>{esc(title)}</h1>
    <p class="subhead">Model projections for every FBS-vs-FBS game this week ({date_range}).
    Picks are straight-up / projected-margin only (see caveat below).</p>
    <div class="stat-row">
      <div class="stat"><span class="n">{len(df)}</span><span class="l">FBS games</span></div>
      <div class="stat"><span class="n">{n_home_fav}</span><span class="l">Home favored</span></div>
      <div class="stat"><span class="n">{n_road_fav}</span><span class="l">Road favored</span></div>
      <div class="stat"><span class="n">{len(other_df)}</span><span class="l">Buy games</span></div>
    </div>
  </header>

  <div class="callout">{CALLOUT}
  </div>

  <div class="col-legend">
    <span>Matchup</span><span>Model pick</span><span>Win prob</span><span>Spread (mkt)</span><span>Total (mkt)</span>
  </div>

  <section class="week">
    <div class="week-heading"><h2>{esc(title)}</h2><span class="range">{date_range}</span></div>

{day_blocks}
  </section>
{buy_games_html}

  <footer class="notes">
{FOOTER}
  </footer>
</div>
"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"Wrote {out_path} ({len(df)} games, {len(other_df)} buy games)")


if __name__ == "__main__":
    main()
