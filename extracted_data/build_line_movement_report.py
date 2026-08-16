"""
Line-movement report: reads line_snapshots_2026.csv (the local Scheduled
Task's 6-hourly polling of CFBD's /lines endpoint, see capture_line_snapshots.py)
and summarizes how far each tracked spread/total has moved from its first
snapshot to its latest, per provider. Pure descriptive reporting -- this is
NOT the CLV/steam-detection backtest itself (that needs many more weeks of
data spanning open-to-close per game, per cfb-backtest-findings-2026); it's
a "what does the data look like so far" check.

Usage:
    python build_line_movement_report.py
Writes line_movement_2026_wk1.csv (one row per game+provider, first/last/
move) and line_movement_report_src.html (the artifact source).
"""
import html as html_lib

import pandas as pd

SNAPSHOTS = "line_snapshots_2026.csv"


def esc(s):
    return html_lib.escape(str(s), quote=True)


def sparkline_svg(values, w=240, h=48, pad=7):
    lo, hi = min(values), max(values)
    rng = (hi - lo) or 1.0
    n = len(values)
    xs = [pad + i * (w - 2 * pad) / (n - 1) for i in range(n)]
    ys = [h - pad - (v - lo) / rng * (h - 2 * pad) for v in values]
    path = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in zip(xs, ys))
    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" class="spark-dot"/>'
        for i, (x, y) in enumerate(zip(xs, ys))
        if i > 0 and values[i] != values[i - 1]
    )
    start = f'<circle cx="{xs[0]:.1f}" cy="{ys[0]:.1f}" r="2.4" class="spark-dot-start"/>'
    end = f'<circle cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="3.4" class="spark-dot-end"/>'
    return (f'<svg viewBox="0 0 {w} {h}" class="spark" preserveAspectRatio="none" '
            f'role="img" aria-label="spread from {values[0]:+.1f} to {values[-1]:+.1f}">'
            f'<path d="{path}" class="spark-line" fill="none"/>{dots}{start}{end}</svg>')


def build_mover_card(row, df):
    sub = df[(df.game_id == row.game_id) & (df.provider == row.provider)].sort_values("snapshot_time_utc")
    vals = list(sub.spread.astype(float))
    spark = sparkline_svg(vals)
    home, away = row.home, row.away
    if row.spread_move < -0.01:
        direction = f"toward {esc(home)}"
        dclass = "dir-home"
    elif row.spread_move > 0.01:
        direction = f"toward {esc(away)}"
        dclass = "dir-away"
    else:
        direction = "total only"
        dclass = "dir-flat"
    move_txt = f"{row.spread_move:+.1f}" if abs(row.spread_move) > 0.01 else "flat"
    ou_txt = ""
    if abs(row.ou_move) > 0.01:
        ou_txt = f'<span class="ou-chip">O/U {row.ou_first:.1f}&rarr;{row.ou_last:.1f}</span>'
    return f"""
        <div class="mover-card">
          <div class="mover-head">
            <div class="mover-teams">{esc(away)} <span class="at">@</span> {esc(home)}</div>
            <span class="mover-book">{esc(row.provider)}</span>
          </div>
          <div class="mover-body">
            {spark}
            <div class="mover-figures">
              <div class="mover-line"><span class="mover-from">{row.spread_first:+.1f}</span>
                <span class="mover-arrow">&rarr;</span>
                <span class="mover-to">{row.spread_last:+.1f}</span></div>
              <div class="mover-move {dclass}">{move_txt} pts &middot; {direction}</div>
              {ou_txt}
            </div>
          </div>
        </div>"""


def main():
    df = pd.read_csv(SNAPSHOTS, parse_dates=["snapshot_time_utc"])
    df = df.sort_values(["game_id", "provider", "snapshot_time_utc"])

    rows = []
    for (gid, prov), g in df.groupby(["game_id", "provider"]):
        g = g.sort_values("snapshot_time_utc")
        first, last = g.iloc[0], g.iloc[-1]
        spread_move = (last["spread"] - first["spread"]) if pd.notna(first["spread"]) and pd.notna(last["spread"]) else None
        ou_move = (last["over_under"] - first["over_under"]) if pd.notna(last["over_under"]) and pd.notna(first["over_under"]) else None
        ml_move = (last["home_moneyline"] - first["home_moneyline"]) if pd.notna(last["home_moneyline"]) and pd.notna(first["home_moneyline"]) else None
        rows.append({
            "game_id": gid, "provider": prov, "home": first["home_team"], "away": first["away_team"],
            "start_date": first["start_date"], "spread_first": first["spread"], "spread_last": last["spread"],
            "spread_move": spread_move, "ou_first": first["over_under"], "ou_last": last["over_under"],
            "ou_move": ou_move, "ml_move": ml_move, "n_snapshots": len(g),
        })
    mv = pd.DataFrame(rows)
    mv.to_csv("line_movement_2026_wk1.csv", index=False)

    movers = mv[(mv.spread_move.fillna(0).abs() > 0.01) | (mv.ou_move.fillna(0).abs() > 0.01)].copy()
    movers = movers.reindex(movers.spread_move.fillna(0).abs().sort_values(ascending=False).index)

    n_pairs = len(mv)
    n_games = mv.game_id.nunique()
    n_moved = len(movers)
    n_snapshots = df.snapshot_time_utc.nunique()
    n_providers = df.provider.nunique()
    span_start = df.snapshot_time_utc.min()
    span_end = df.snapshot_time_utc.max()
    n_ml_moved = int((mv.ml_move.fillna(0).abs() > 0.5).sum())

    cards_html = "".join(build_mover_card(r, df) for _, r in movers.iterrows())

    print(f"{n_pairs} game/provider pairs across {n_games} games, {n_moved} moved at all "
          f"({span_start} to {span_end}, {n_snapshots} snapshots, {n_providers} books)")
    print(f"Wrote line_movement_2026_wk1.csv")

    from datetime import datetime
    now = datetime.now()
    generated = f"{now.strftime('%B')} {now.day}, {now.year}"
    span_days = (span_end - span_start).days
    kickoff = pd.Timestamp("2026-08-29", tz="UTC")
    weeks_to_kickoff = round((kickoff - now_utc).days / 7, 1) if (now_utc := pd.Timestamp.now(tz="UTC")) < kickoff else 0
    pct_moved = n_moved / n_pairs * 100

    html_out = f"""<title>Week 1 Line Watch</title>
<meta name="description" content="How far Week 1 2026 college football spreads and totals have moved since first tracked, book by book.">
{CSS}
<div class="wrap">
  <header class="masthead">
    <p class="eyebrow">2026 CFB Handicap Model &middot; Generated {esc(generated)}</p>
    <h1>Week 1 Line Watch</h1>
    <p class="subhead">Tracking every Week 1 spread and total across {n_snapshots} snapshots since
    {span_start.strftime('%b')} {span_start.day}, polled every ~6 hours from Bovada and DraftKings via CollegeFootballData.com
    (CFBD only exposes each book's <em>current</em> line, not history &mdash; this dataset is built forward,
    snapshot by snapshot, for free).</p>
    <div class="stat-row">
      <div class="stat"><span class="n">{n_games}</span><span class="l">Games tracked</span></div>
      <div class="stat"><span class="n">{n_snapshots}</span><span class="l">Snapshots</span></div>
      <div class="stat"><span class="n">{span_days}</span><span class="l">Days of history</span></div>
      <div class="stat"><span class="n">{n_moved}</span><span class="l">Lines that moved</span></div>
    </div>
  </header>

  <div class="callout">
    <strong>The market is essentially frozen right now.</strong> Of {n_pairs} tracked spread/book pairs,
    only {n_moved} ({pct_moved:.0f}%) have moved at all since the first snapshot &mdash; and every move
    so far is a single half- or full-point nudge that then held steady, not a run. Moneylines haven't
    moved on a single tracked game ({n_ml_moved} of {int(mv.ml_move.notna().sum())} pairs), and totals
    have moved on just one. That's expected roughly {weeks_to_kickoff:g} weeks before kickoff &mdash; this is real
    signal, not a broken pipeline: preseason books post a line and let it sit until injury/depth-chart
    news or real market pressure builds closer to game day. The {n_moved} movers below are the entire
    story so far.
  </div>

  <section class="movers">
    <h2>Every line that's actually moved</h2>
    <div class="mover-grid">{cards_html}
    </div>
  </section>

  <footer class="notes">
    <p><strong>Why this exists:</strong> CollegeFootballData.com's <code>/lines</code> endpoint only
    returns each book's current number, with a single "open" value and no intraday history. A local
    Scheduled Task polls it every 6 hours and appends timestamped rows to
    <code>line_snapshots_2026.csv</code>, turning a snapshot-only API into a real movement history for
    free. This page reads that growing file directly.</p>
    <p><strong>What this isn't (yet):</strong> a CLV or steam-detection signal. That analysis needs many
    more weeks of data, ideally spanning open-to-close for each game once injury news and real betting
    volume start moving lines &mdash; nothing here has been backtested for a betting edge. Revisit as
    the dataset grows through the season.</p>
    <p>Data: CollegeFootballData.com <code>/lines</code> (Bovada, DraftKings), polled locally every 6
    hours since {span_start.strftime('%Y-%m-%d')}.</p>
  </footer>
</div>
"""
    with open("line_movement_report_src.html", "w", encoding="utf-8") as f:
        f.write(html_out)
    print("Wrote line_movement_report_src.html")


CSS = """
<style>
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #12140f; --surface: #191c15; --surface-2: #20241b; --border: #33382c;
    --text: #edeee6; --text-muted: #9aa090; --accent: #5da682; --accent-soft: #1f2f26;
    --gold: #d1ab52; --gold-soft: #2b2617; --rust: #d98f78;
  }
}
:root[data-theme="dark"] {
  --bg: #12140f; --surface: #191c15; --surface-2: #20241b; --border: #33382c;
  --text: #edeee6; --text-muted: #9aa090; --accent: #5da682; --accent-soft: #1f2f26;
  --gold: #d1ab52; --gold-soft: #2b2617; --rust: #d98f78;
}
:root {
  --bg: #f5f4ef; --surface: #ffffff; --surface-2: #edece4; --border: #dcd8ca;
  --text: #1a1e19; --text-muted: #656a5e; --accent: #2f6b4f; --accent-soft: #e3ede7;
  --gold: #9c7a23; --gold-soft: #f2ead2; --rust: #8a4a3a;
  --font-display: Georgia, "Iowan Old Style", "Palatino Linotype", serif;
  --font-body: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  --font-mono: ui-monospace, "SFMono-Regular", "Cascadia Mono", Consolas, monospace;
}
* { box-sizing: border-box; }
body { background: var(--bg); color: var(--text); font-family: var(--font-body); margin: 0; padding: 0 0 4rem; line-height: 1.45; }
.wrap { max-width: 880px; margin: 0 auto; padding: 0 1.5rem; }
header.masthead { border-bottom: 1px solid var(--border); padding: 2.75rem 0 1.75rem; margin-bottom: 2rem; }
.eyebrow { font-family: var(--font-mono); font-size: 0.72rem; letter-spacing: 0.11em; text-transform: uppercase; color: var(--accent); margin: 0 0 0.6rem; }
h1 { font-family: var(--font-display); font-size: 2.15rem; font-weight: 700; margin: 0 0 0.5rem; text-wrap: balance; letter-spacing: -0.01em; }
.subhead { color: var(--text-muted); font-size: 0.98rem; max-width: 66ch; margin: 0; }
.subhead em { color: var(--text); font-style: normal; }
.stat-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 1px; background: var(--border); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; margin: 1.75rem 0 0; }
.stat { background: var(--surface); padding: 0.9rem 1.1rem; }
.stat .n { font-family: var(--font-mono); font-size: 1.5rem; font-weight: 600; font-variant-numeric: tabular-nums; display: block; }
.stat .l { color: var(--text-muted); font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.06em; }
.callout { background: var(--accent-soft); border: 1px solid var(--border); border-left: 3px solid var(--accent); border-radius: 8px; padding: 1rem 1.2rem; font-size: 0.92rem; color: var(--text); margin: 0 0 2.5rem; }
.callout strong { color: var(--accent); }
section.movers h2 { font-family: var(--font-display); font-size: 1.3rem; margin: 0 0 1.1rem; }
.mover-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 0.9rem; }
.mover-card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 0.9rem 1rem 1rem; }
.mover-head { display: flex; justify-content: space-between; align-items: baseline; gap: 0.5rem; margin-bottom: 0.5rem; }
.mover-teams { font-weight: 600; font-size: 0.9rem; }
.at { color: var(--text-muted); font-weight: 400; font-size: 0.85em; }
.mover-book { font-family: var(--font-mono); font-size: 0.66rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); border: 1px solid var(--border); border-radius: 3px; padding: 0.1rem 0.35rem; white-space: nowrap; }
.mover-body { display: flex; align-items: center; gap: 0.8rem; }
.spark { width: 110px; height: 44px; flex-shrink: 0; }
.spark-line { stroke: var(--accent); stroke-width: 2; }
.spark-dot { fill: var(--border); }
.spark-dot-start { fill: var(--text-muted); }
.spark-dot-end { fill: var(--accent); }
.mover-figures { font-family: var(--font-mono); font-size: 0.82rem; }
.mover-line { font-variant-numeric: tabular-nums; }
.mover-from { color: var(--text-muted); }
.mover-arrow { color: var(--text-muted); margin: 0 0.15rem; }
.mover-to { font-weight: 700; }
.mover-move { font-size: 0.72rem; margin-top: 0.2rem; font-weight: 600; }
.dir-home { color: var(--accent); }
.dir-away { color: var(--gold); }
.dir-flat { color: var(--text-muted); }
.ou-chip { display: inline-block; margin-top: 0.35rem; font-size: 0.66rem; color: var(--text-muted); background: var(--surface-2); border-radius: 3px; padding: 0.1rem 0.3rem; }
footer.notes { margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid var(--border); color: var(--text-muted); font-size: 0.82rem; }
footer.notes p { margin: 0 0 0.7rem; }
footer.notes code { font-family: var(--font-mono); background: var(--surface-2); padding: 0.1rem 0.3rem; border-radius: 3px; font-size: 0.85em; }
@media (max-width: 480px) {
  .mover-grid { grid-template-columns: 1fr; }
}
</style>
"""

if __name__ == "__main__":
    main()
