"""
Renders the self-contained HTML artifact for the season win-totals report
(season_win_totals_2026.csv). Same visual language as build_artifact.py
(the weekly game-slate artifact) -- same CSS tokens/fonts -- so the two
pages read as one product, adapted to a sortable 138-row table instead of
a day-by-day game list.

Usage:
    python build_win_totals_artifact.py --csv season_win_totals_2026.csv --out season_win_totals_2026_artifact_src.html
"""
import argparse
import html as html_lib
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
  --under: #8a4a3a;
  --under-soft: #f3e6e1;
  --font-display: Georgia, "Iowan Old Style", "Palatino Linotype", serif;
  --font-body: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  --font-mono: ui-monospace, "SFMono-Regular", "Cascadia Mono", Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #12140f; --surface: #191c15; --surface-2: #20241b; --border: #33382c;
    --text: #edeee6; --text-muted: #9aa090; --accent: #5da682; --accent-soft: #1f2f26;
    --gold: #d1ab52; --gold-soft: #2b2617; --under: #d98f78; --under-soft: #2c1e19;
  }
}
:root[data-theme="dark"] {
  --bg: #12140f; --surface: #191c15; --surface-2: #20241b; --border: #33382c;
  --text: #edeee6; --text-muted: #9aa090; --accent: #5da682; --accent-soft: #1f2f26;
  --gold: #d1ab52; --gold-soft: #2b2617; --under: #d98f78; --under-soft: #2c1e19;
}
* { box-sizing: border-box; }
body { background: var(--bg); color: var(--text); font-family: var(--font-body); margin: 0; padding: 0 0 4rem; line-height: 1.45; }
.wrap { max-width: 1080px; margin: 0 auto; padding: 0 1.5rem; }
header.masthead { border-bottom: 1px solid var(--border); padding: 2.75rem 0 1.75rem; margin-bottom: 2rem; }
.eyebrow { font-family: var(--font-mono); font-size: 0.72rem; letter-spacing: 0.11em; text-transform: uppercase; color: var(--accent); margin: 0 0 0.6rem; }
h1 { font-family: var(--font-display); font-size: 2.15rem; font-weight: 700; margin: 0 0 0.5rem; text-wrap: balance; letter-spacing: -0.01em; }
.subhead { color: var(--text-muted); font-size: 0.98rem; max-width: 68ch; margin: 0; }
.stat-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 1px; background: var(--border); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; margin: 1.75rem 0 0; }
.stat { background: var(--surface); padding: 0.9rem 1.1rem; }
.stat .n { font-family: var(--font-mono); font-size: 1.5rem; font-weight: 600; font-variant-numeric: tabular-nums; display: block; }
.stat .l { color: var(--text-muted); font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.06em; }
.callout { background: var(--accent-soft); border: 1px solid var(--border); border-left: 3px solid var(--accent); border-radius: 8px; padding: 0.9rem 1.1rem; font-size: 0.88rem; color: var(--text); margin: 1.5rem 0 1rem; }
.callout strong { color: var(--accent); }
.callout.warn { border-left-color: var(--gold); background: var(--gold-soft); margin-bottom: 2rem; }
.callout.warn strong { color: var(--gold); }
.table-scroll { overflow-x: auto; border: 1px solid var(--border); border-radius: 10px; }
table.wt { border-collapse: collapse; width: 100%; min-width: 880px; background: var(--surface); font-size: 0.86rem; }
table.wt thead th { position: sticky; top: 0; background: var(--surface-2); text-align: left; font-family: var(--font-mono); font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted); padding: 0.6rem 0.7rem; border-bottom: 1px solid var(--border); cursor: pointer; user-select: none; white-space: nowrap; }
table.wt thead th:hover { color: var(--accent); }
table.wt thead th.sorted::after { content: " " attr(data-arrow); color: var(--accent); }
table.wt tbody tr { border-bottom: 1px solid var(--border); }
table.wt tbody tr:last-child { border-bottom: none; }
table.wt tbody tr:hover { background: var(--surface-2); }
table.wt tbody tr.flag-over { background: var(--gold-soft); }
table.wt tbody tr.flag-under { background: var(--under-soft); }
table.wt td { padding: 0.55rem 0.7rem; vertical-align: middle; font-variant-numeric: tabular-nums; }
td.rank { color: var(--text-muted); font-family: var(--font-mono); font-size: 0.8rem; }
td.team { font-weight: 600; }
td.team .conf { display: block; font-weight: 400; font-size: 0.72rem; color: var(--text-muted); }
td.num { text-align: right; font-family: var(--font-mono); }
td.gap { text-align: right; font-family: var(--font-mono); font-weight: 700; }
.gap-over { color: var(--gold); }
.gap-under { color: var(--under); }
.gap-flat { color: var(--text-muted); font-weight: 400; }
.dist-cell { min-width: 190px; }
.dist-track { position: relative; height: 22px; background: var(--surface-2); border-radius: 4px; margin: 0 4px; }
.dist-range { position: absolute; top: 7px; height: 8px; background: var(--accent-soft); border: 1px solid var(--accent); border-radius: 4px; opacity: 0.75; }
.dist-mkt { position: absolute; top: 2px; width: 2px; height: 18px; background: var(--gold); }
.dist-exp { position: absolute; top: 0; width: 8px; height: 22px; margin-left: -4px; background: var(--accent); border-radius: 2px; }
.dist-label { display: flex; justify-content: space-between; font-family: var(--font-mono); font-size: 0.62rem; color: var(--text-muted); margin-top: 0.15rem; }
.legend-row { display: flex; gap: 1.4rem; flex-wrap: wrap; font-size: 0.76rem; color: var(--text-muted); margin: 0.9rem 0.2rem 0.6rem; align-items: center; }
.legend-item { display: flex; align-items: center; gap: 0.35rem; }
.legend-swatch { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
footer.notes { margin-top: 2.5rem; padding-top: 1.5rem; border-top: 1px solid var(--border); color: var(--text-muted); font-size: 0.82rem; }
footer.notes p { margin: 0 0 0.7rem; }
footer.notes code { font-family: var(--font-mono); background: var(--surface-2); padding: 0.1rem 0.3rem; border-radius: 3px; font-size: 0.85em; }
.na { color: var(--text-muted); }
"""

CALLOUT_METHOD = """
    <strong>How this is built:</strong> every team's full 2026 regular-season schedule is simulated
    game by game (same blended SP+/FPI/bottom-up-model margin + tiered home-field formula as the
    weekly slate), then combined into an exact win-count probability distribution (not just an
    average). FCS/lower-division opponents use an empirically-derived proxy rating (FBS teams beat
    them by ~31 points and win ~95.5% of the time, 2022-2025). Backtested 2023-2025 against actual
    final win totals: <strong>r=0.615 (R&sup2;=0.378)</strong>, clearly ahead of a "predict = last
    year's wins" baseline (r=0.463).
"""

CALLOUT_EDGE = """
    <strong>Is the model-vs-market gap an edge? Mixed evidence, not a green light.</strong>
    Tested the same approach against real DraftKings win-total lines for 2023-2025: 2023 was a
    <strong>losing</strong> year (43.5% hit rate on the side the model favored, below the 52.4%
    breakeven), 2024 was roughly a coin flip (53.6%), and 2025 was strong (63.8%, climbing to 81.8%
    on the biggest gaps) &mdash; but 2025 is one season, and 2023/2024's sample was Power-conference
    teams only. Three years with one losing year in the mix isn't enough to call this a validated
    edge, even though it didn't die on first contact the way the single-game spread market did.
    Gold/rust-highlighted rows below are model-vs-market gaps of a full win or more &mdash; a
    "look closer" flag, not a bet signal.
"""

FOOTER = """
    <p>Win totals count regular-season games only (no conference championship, no bowl) &mdash;
    matches how sportsbooks define the market. Market lines: DraftKings via sportsbettingdime.com,
    pulled 2026-08-11.</p>
    <p>Full methodology, FCS-proxy derivation, and both backtests: <code>win_totals_README.md</code>.
    Data: CollegeFootballData.com, ESPN FPI, this project's bottom-up 2026 power ratings.</p>
"""


def esc(s):
    return html_lib.escape(str(s), quote=True)


def fmt_num(x, decimals=1):
    return "&mdash;" if pd.isna(x) else f"{x:.{decimals}f}"


def build_row(row, scale_max):
    gap = row["model_gap"]
    if pd.isna(gap):
        gap_html = '<span class="gap-flat">&mdash;</span>'
        row_class = ""
    elif gap >= 1.0:
        gap_html = f'<span class="gap-over">+{gap:.2f}</span>'
        row_class = "flag-over"
    elif gap <= -1.0:
        gap_html = f'<span class="gap-under">{gap:.2f}</span>'
        row_class = "flag-under"
    else:
        gap_html = f'<span class="gap-flat">{gap:+.2f}</span>'
        row_class = ""

    p10, p90 = row["p10_wins"], row["p90_wins"]
    exp = row["expected_wins"]
    mkt = row["market_line"]
    range_left = p10 / scale_max * 100
    range_width = (p90 - p10) / scale_max * 100
    exp_left = exp / scale_max * 100
    mkt_marker = f'<div class="dist-mkt" style="left:{mkt / scale_max * 100:.1f}%" title="Market line {mkt}"></div>' if pd.notna(mkt) else ""

    dist_html = f"""<div class="dist-track">
            <div class="dist-range" style="left:{range_left:.1f}%;width:{range_width:.1f}%" title="p10-p90: {int(p10)}-{int(p90)} wins"></div>
            {mkt_marker}
            <div class="dist-exp" style="left:{exp_left:.1f}%" title="Expected wins: {exp:.2f}"></div>
          </div>
          <div class="dist-label"><span>0</span><span>{int(scale_max)}</span></div>"""

    conf = row.get("conference")
    conf_html = f'<span class="conf">{esc(conf)}</span>' if pd.notna(conf) else ""
    rank = row.get("blended_rank")
    rank_html = f"#{int(rank)}" if pd.notna(rank) else "&mdash;"

    return f"""      <tr class="{row_class}" data-team="{esc(row['team'])}" data-rank="{rank if pd.notna(rank) else 999}"
          data-exp="{exp}" data-mkt="{mkt if pd.notna(mkt) else ''}" data-gap="{gap if pd.notna(gap) else ''}">
        <td class="rank">{rank_html}</td>
        <td class="team">{esc(row['team'])}{conf_html}</td>
        <td class="num">{exp:.2f}</td>
        <td class="dist-cell">{dist_html}</td>
        <td class="num">{fmt_num(mkt)}</td>
        <td class="gap">{gap_html}</td>
      </tr>"""


SORT_JS = """
<script>
(function () {
  const table = document.getElementById('wtTable');
  const tbody = table.tBodies[0];
  const headers = table.querySelectorAll('thead th[data-sort]');
  let currentSort = { key: 'gap', dir: -1 };

  function sortRows(key, dir) {
    const rows = Array.from(tbody.rows);
    rows.sort((a, b) => {
      let av = a.dataset[key], bv = b.dataset[key];
      if (key === 'team') return dir * String(av).localeCompare(String(bv));
      av = av === '' ? -Infinity : parseFloat(av);
      bv = bv === '' ? -Infinity : parseFloat(bv);
      return dir * (av - bv);
    });
    rows.forEach(r => tbody.appendChild(r));
  }

  headers.forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.sort;
      const dir = (currentSort.key === key) ? -currentSort.dir : (key === 'rank' || key === 'team' ? 1 : -1);
      currentSort = { key, dir };
      headers.forEach(h => { h.classList.remove('sorted'); h.removeAttribute('data-arrow'); });
      th.classList.add('sorted');
      th.setAttribute('data-arrow', dir === 1 ? '\\u25b4' : '\\u25be');
      sortRows(key, dir);
    });
  });

  sortRows('gap', -1);
})();
</script>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="season_win_totals_2026.csv")
    ap.add_argument("--out", default="season_win_totals_2026_artifact_src.html")
    ap.add_argument("--title", default="2026 Season Win Totals")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    df = df[df["games_scheduled"] >= 10].copy()  # drop any incomplete-schedule rows
    scale_max = int(df["games_scheduled"].max())

    n_teams = len(df)
    n_over = int((df["model_gap"] >= 1.0).sum())
    n_under = int((df["model_gap"] <= -1.0).sum())
    n_no_line = int(df["market_line"].isna().sum())

    rows_html = "\n\n".join(build_row(r, scale_max) for _, r in df.iterrows())

    now = datetime.now()
    generated = f"{now.strftime('%B')} {now.day}, {now.year}"

    html_out = f"""<title>{esc(args.title)}</title>
<meta name="description" content="Projected 2026 college football season win totals for all FBS teams, vs. real sportsbook lines.">
<style>
{CSS}
</style>

<div class="wrap">
  <header class="masthead">
    <p class="eyebrow">2026 CFB Handicap Model &middot; Generated {generated}</p>
    <h1>{esc(args.title)}</h1>
    <p class="subhead">Full-schedule win projections for all {n_teams} FBS teams, simulated game by game and
    compared against real DraftKings preseason win-total lines. Click any column header to sort.</p>
    <div class="stat-row">
      <div class="stat"><span class="n">{n_teams}</span><span class="l">Teams projected</span></div>
      <div class="stat"><span class="n">{n_over}</span><span class="l">Model likes the over (+1&#8201;win)</span></div>
      <div class="stat"><span class="n">{n_under}</span><span class="l">Model likes the under (&minus;1&#8201;win)</span></div>
      <div class="stat"><span class="n">{n_no_line}</span><span class="l">No market line yet</span></div>
    </div>
  </header>

  <div class="callout">{CALLOUT_METHOD}</div>
  <div class="callout warn">{CALLOUT_EDGE}</div>

  <div class="legend-row">
    <span class="legend-item"><span class="legend-swatch" style="background:var(--accent)"></span> Expected wins</span>
    <span class="legend-item"><span class="legend-swatch" style="background:var(--accent-soft);border:1px solid var(--accent)"></span> p10&ndash;p90 range</span>
    <span class="legend-item"><span class="legend-swatch" style="background:var(--gold)"></span> Market line</span>
    <span class="legend-item"><span class="legend-swatch" style="background:var(--gold-soft)"></span> Model &ge;1 win over market</span>
    <span class="legend-item"><span class="legend-swatch" style="background:var(--under-soft)"></span> Model &ge;1 win under market</span>
  </div>

  <div class="table-scroll">
    <table class="wt" id="wtTable">
      <thead>
        <tr>
          <th data-sort="rank">Power rank</th>
          <th data-sort="team">Team</th>
          <th data-sort="exp">Exp. wins</th>
          <th>Distribution (p10&ndash;p90)</th>
          <th data-sort="mkt">Market line</th>
          <th data-sort="gap" class="sorted" data-arrow="&#9662;">Model gap</th>
        </tr>
      </thead>
      <tbody>
{rows_html}
      </tbody>
    </table>
  </div>

  <footer class="notes">
{FOOTER}
  </footer>
</div>
{SORT_JS}
"""

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"Wrote {args.out} ({n_teams} teams)")


if __name__ == "__main__":
    main()
