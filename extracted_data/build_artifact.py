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

from market_signals import signals_for_week

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
.wrap { max-width: 1060px; margin: 0 auto; padding: 0 1.5rem; }
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
.col-legend { display: grid; grid-template-columns: 2fr 0.55fr 0.55fr 0.85fr 1fr 1.15fr 0.95fr 0.8fr; gap: 0.75rem; padding: 0 0.2rem 0.5rem; font-family: var(--font-mono); font-size: 0.66rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted); }
.col-legend span:not(:first-child) { text-align: right; }
.game-list { display: flex; flex-direction: column; }
.game-row { display: grid; grid-template-columns: 2fr 0.55fr 0.55fr 0.85fr 1fr 1.15fr 0.95fr 0.8fr; gap: 0.75rem; align-items: center; padding: 0.7rem 0.2rem; border-bottom: 1px solid var(--border); }
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
.game-rec { font-family: var(--font-mono); font-size: 0.8rem; font-variant-numeric: tabular-nums; line-height: 1.35; }
.game-rec .rec-label { display: none; }
.wp-bar-track { height: 6px; background: var(--surface-2); border-radius: 3px; overflow: hidden; margin-bottom: 0.3rem; }
.wp-bar-fill { height: 100%; background: var(--accent); border-radius: 3px; }
.wp-label { font-family: var(--font-mono); font-size: 0.74rem; color: var(--text-muted); font-variant-numeric: tabular-nums; }
.game-market { font-family: var(--font-mono); font-size: 0.82rem; text-align: right; }
.market-num { color: var(--gold); font-weight: 600; }
.gap-note { display: block; font-family: var(--font-mono); font-size: 0.7rem; color: var(--text-muted); margin-top: 0.15rem; }
.game-row.tier-strong { background: var(--accent-soft); border-radius: 6px; }
.game-row.tier-skip .game-ats .ats-side { color: var(--text-muted); text-decoration: line-through; text-decoration-color: var(--border); }
.game-ats { min-width: 0; }
.ats-side { font-weight: 600; font-size: 0.88rem; }
.ats-line { font-family: var(--font-mono); font-size: 0.8rem; font-variant-numeric: tabular-nums; }
.tier-badge { display: inline-block; font-family: var(--font-mono); font-size: 0.62rem; font-weight: 700; letter-spacing: 0.06em; padding: 0.08rem 0.4rem; border-radius: 3px; margin-top: 0.2rem; cursor: help; border: 1px solid var(--border); color: var(--text-muted); }
.tier-badge.strong { background: var(--accent); border-color: var(--accent); color: var(--surface); }
.tier-badge.skip { border-style: dashed; }
.mkt-move { display: block; font-family: var(--font-mono); font-size: 0.68rem; color: var(--text-muted); margin-top: 0.15rem; }
.mkt-move .up { color: var(--accent); font-weight: 600; }
.mkt-move .down { color: var(--gold); font-weight: 600; }
.rlm-badge { display: inline-block; font-family: var(--font-mono); font-size: 0.6rem; font-weight: 700; letter-spacing: 0.05em; padding: 0.02rem 0.35rem; border-radius: 3px; margin-top: 0.2rem; border: 1px solid var(--gold); color: var(--gold); cursor: help; }
.strong-list { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 0.9rem 1.1rem; margin: 0 0 2rem; }
.strong-list h2 { font-family: var(--font-display); font-size: 1.15rem; margin: 0 0 0.6rem; }
.strong-list ul { list-style: none; margin: 0; padding: 0; columns: 2; column-gap: 1.5rem; font-size: 0.88rem; }
.strong-list li { margin-bottom: 0.35rem; break-inside: avoid; }
.strong-list .why { color: var(--text-muted); font-size: 0.78rem; }
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
  .game-rec .rec-label { display: inline; color: var(--text-muted); font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.06em; margin-right: 0.35em; }
  .game-rec div { display: inline; }
  .game-rec div + div::before { content: " / "; color: var(--text-muted); }
  .col-legend { display: none; }
  .buy-list { columns: 1; }
  .strong-list ul { columns: 1; }
}
"""

CALLOUT = """
    <strong>Reading this:</strong> margin and win prob are <strong>70% SP+'s weekly game projection</strong>
    (Bill Connelly's public picks sheet) and <strong>30% our preseason blend</strong> (SP+, FPI, our bottom-up
    model, Steele) plus home field. The home team is marked
    <span class="home-tag" style="margin-left:0">HOME</span>. The <strong>ATS pick</strong> column is the
    model's side of the market spread, tiered:
    <span class="tier-badge strong" style="margin-top:0">STRONG</span> = SP+ and our preseason blend
    <em>each</em> land on that side of the line, or the side is the home favourite;
    <span class="tier-badge skip" style="margin-top:0">SKIP</span> = the side is an away favourite, or runs
    into a letdown spot (P4 team off an upset win as an underdog, vs a P4 opponent) or is a losing-record
    home favourite; <span class="tier-badge" style="margin-top:0">NO SIGNAL</span> = neither. Backtest
    (2025 + 2026 weeks 1-9): STRONG 58%, NO SIGNAL ~50%, SKIP ~47% &mdash; promising, but two seasons is a
    small sample and the line still beats any model on raw accuracy, so treat tiers as a ranking, not a
    guarantee. <strong>Gap size is not a strength signal</strong> (bigger gaps did not cover more often), so
    it's shown as a plain number only. <strong>Totals are context only</strong> &mdash; no O/U signal from our
    model or SP+ in either season. A <span class="flag">&#9888;</span> next to a team means our preseason
    sources unusually disagree on that team.
    <br><br><strong>Market watch</strong> (under the spread): the ATS pick's line at open and now, with
    <span style="color:var(--accent)">&#9650;</span> if it has moved toward the pick and
    <span style="color:var(--gold)">&#9660;</span> if against; the public ticket % and money % (Action Network);
    and an <span class="rlm-badge" style="margin-top:0;cursor:default">RLM</span> badge when 55%+ of tickets are on
    one side but the line moved the other way. <strong>Tracked, not tiered</strong>: in backtests, line movement
    toward the model helped in 2026 but hurt in 2025, and RLM has no history yet. The scorecard is
    building a forward record of both.
"""

FOOTER = """
    <p>Model (from Nov 3, 2026): <code>margin = 0.7 &times; SP+ weekly projection + 0.3 &times; (avg(SP+, FPI,
    bottom-up 2026 model, Steele Power Poll) + tiered home-field advantage)</code>, win probability from a normal
    CDF (&sigma;=18.4). The SP+ weight replaced our score-based in-season rating, which ran below 50% ATS this season;
    0.6-0.8 SP+ weight was best for both accuracy and ATS in 2025 and 2026. Games with no SP+ row fall back to the
    old preseason + in-season formula. HFA: +2.9 at a true home site, +1.8 at a "neutral" site, +6.0 for
    altitude-market home teams (Air Force, BYU, Colorado, Colorado State, New Mexico, Utah, Wyoming).
    Totals are a calibrated offense/defense matchup average: preseason SP+ off/def blended with each team's
    opponent-adjusted 2026 points scored/allowed (more games played = more weight). More accurate than
    preseason-only in a 2023-25 replay, but still well behind the market's total and no over/under edge --
    context only.</p>
    <p>W-L and ATS columns: each team's season-to-date record before this week, listed in matchup order
    (hover for the team). W-L includes games vs. FCS opponents; ATS counts games with a line, graded against
    the median closing spread across books (W-L-push). Context only -- not a model input.</p>
    <p>Data: SP+ weekly picks sheet (Bill Connelly, public Google Sheet),
    CollegeFootballData.com (games/lines/SP+/FPI/recruiting/returning production),
    ESPN FPI, Phil Steele's 2026 CFB Preview, this project's bottom-up 2026 power ratings.</p>
"""


def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


# 2026-11-03: the old gold "big gap" highlight (25%+ of the line / 3+ pts) is gone --
# bigger model-vs-market gaps did not cover more often in 2025 or 2026. Row emphasis
# now comes from the ATS tier (ats_tier column, see ats_tiers_README.md).


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

    # Season-to-date records, listed in the same left/right order as the matchup.
    # Older projection CSVs (pre-record columns) just leave these blank.
    def rec_cell(kind, label):
        lv, rv = (row.get(f"home_{kind}"), row.get(f"away_{kind}")) if neutral else (row.get(f"away_{kind}"), row.get(f"home_{kind}"))
        if pd.isna(lv) or pd.isna(rv):
            return '<span class="muted">&mdash;</span>'
        return (f'<span class="rec-label">{label}</span>'
                f'<div title="{esc(left)}">{esc(lv)}</div><div title="{esc(right)}">{esc(rv)}</div>')

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

    market_html = '<span class="muted">no line yet</span>'
    if pd.notna(row.get("market_home_margin")):
        mkt_margin = row["market_home_margin"]
        mkt_team = home if mkt_margin > 0 else away
        market_html = f'{esc(mkt_team)} <span class="market-num">{-abs(mkt_margin):.1f}</span>'
        gap = row.get("model_vs_market_gap")
        if pd.notna(gap):
            market_html += f'<span class="gap-note">model {abs(gap):.1f} pts off</span>'
    market_html += market_watch_html(row)

    ats_html, tier_class = '<span class="muted">&mdash;</span>', ""
    tier = row.get("ats_tier")
    if pd.notna(row.get("ats_side")) and pd.notna(tier):
        side = row["ats_side"]
        side_line = -row["market_home_margin"] if side == home else row["market_home_margin"]
        reason = row.get("ats_tier_reason")
        tip = esc(reason) if pd.notna(reason) and reason else "no supporting signal"
        badge_cls = {"STRONG": "tier-badge strong", "SKIP": "tier-badge skip"}.get(tier, "tier-badge")
        tier_class = {"STRONG": " tier-strong", "SKIP": " tier-skip"}.get(tier, "")
        ats_html = (f'<div class="ats-side">{esc(side)} <span class="ats-line">{side_line:+.1f}</span></div>'
                    f'<span class="{badge_cls}" title="{tip}">{esc(tier)}</span>')

    total_html = '<span class="muted">&mdash;</span>'
    if pd.notna(row.get("model_total")):
        total_html = f'<span class="total-num">{row["model_total"]:.1f}</span>'
        if pd.notna(row.get("market_total")):
            total_html += f'<span class="total-mkt">mkt {row["market_total"]:.1f}</span>'

    row_class = "game-row" + tier_class
    return f"""        <div class="{row_class}">
          <div class="game-main">
            <div class="matchup">{matchup}</div>
            <div class="ranks">{ranks}</div>
          </div>
          <div class="game-rec">{rec_cell("record", "W-L")}</div>
          <div class="game-rec">{rec_cell("ats", "ATS")}</div>
          <div class="game-pick">
            <div class="pick-name">{esc(pick)}</div>
            <div class="pick-margin">by {row['model_margin']:.1f}</div>
          </div>
          <div class="game-wp">
            <div class="wp-bar-track"><div class="wp-bar-fill" style="width:{bar_pct:.1f}%"></div></div>
            <div class="wp-label">{bar_pct:.0f}% win prob</div>
          </div>
          <div class="game-ats">{ats_html}</div>
          <div class="game-market">{market_html}</div>
          <div class="game-total">{total_html}</div>
        </div>"""


def market_watch_html(row):
    """Line move (open -> latest) relative to the ATS pick, public splits, RLM. Info only."""
    home, away = row["home"], row["away"]
    side = row.get("ats_side") if isinstance(row.get("ats_side"), str) else None
    out = ""
    o, c = row.get("open_home_spread"), row.get("close_home_spread")
    if pd.notna(o) and pd.notna(c) and side:
        so, sc = (o, c) if side == home else (-o, -c)
        mv = row.get("line_move_model")
        arrow = ""
        if pd.notna(mv) and mv >= 0.5:
            arrow = f' <span class="up" title="Line moved toward the ATS pick since open">&#9650;{mv:.1f}</span>'
        elif pd.notna(mv) and mv <= -0.5:
            arrow = f' <span class="down" title="Line moved against the ATS pick since open">&#9660;{-mv:.1f}</span>'
        out += f'<span class="mkt-move">{esc(side)}: open {so:+.1f} &rarr; now {sc:+.1f}{arrow}</span>'
    tix, money = row.get("home_tickets_pct"), row.get("home_money_pct")
    if pd.notna(tix):
        t_team, t_pct = (home, tix) if tix >= 50 else (away, 100 - tix)
        m_txt = ""
        if pd.notna(money):
            m_team, m_pct = (home, money) if money >= 50 else (away, 100 - money)
            m_txt = f" &middot; {m_pct:.0f}% $ {esc(m_team)}"
        out += f'<span class="mkt-move">{t_pct:.0f}% tix {esc(t_team)}{m_txt}</span>'
    rlm = row.get("rlm_side")
    if isinstance(rlm, str) and rlm:
        tip = ("Reverse line movement: most tickets are on the other side but the line moved toward "
               f"{esc(rlm)}. Tracked only, not part of the tier.")
        out += f'<span class="rlm-badge" title="{tip}">RLM &rarr; {esc(rlm)}</span>'
    return out


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

    try:  # market watch columns (open/now line, public %, RLM) -- info only, never blocks the page
        df = pd.concat([df, signals_for_week(df, year, week)], axis=1)
    except Exception as e:
        print(f"market signals skipped: {e}")

    dates = sorted(df["date"].unique())
    date_range = f"{day_heading(dates[0])} &ndash; {day_heading(dates[-1])}" if dates else ""
    if "ats_tier" not in df.columns:  # projection CSVs built before the SP+ blend
        df["ats_tier"] = None; df["ats_side"] = None; df["ats_tier_reason"] = None
    n_strong = int((df["ats_tier"] == "STRONG").sum())
    n_skip = int((df["ats_tier"] == "SKIP").sum())
    strong = df[df["ats_tier"] == "STRONG"].sort_values("date")
    strong_items = "\n".join(
        f'<li><strong>{esc(r["ats_side"])}</strong> '
        f'<span class="ats-line">{(-r["market_home_margin"] if r["ats_side"] == r["home"] else r["market_home_margin"]):+.1f}</span> '
        f'<span class="muted">vs {esc(r["away"] if r["ats_side"] == r["home"] else r["home"])}, {day_heading(r["date"])}</span>'
        f'<br><span class="why">{esc(r["ats_tier_reason"])}</span></li>'
        for _, r in strong.iterrows())
    strong_html = (f'<section class="strong-list"><h2>STRONG ATS picks ({n_strong})</h2><ul>{strong_items}</ul></section>'
                   if n_strong else "")

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
    <p class="subhead">Model projections for every FBS-vs-FBS game this week ({date_range}):
    straight-up pick and margin, plus the model's ATS side with a STRONG / NO SIGNAL / SKIP tier.</p>
    <div class="stat-row">
      <div class="stat"><span class="n">{len(df)}</span><span class="l">FBS games</span></div>
      <div class="stat"><span class="n">{n_strong}</span><span class="l">STRONG ATS</span></div>
      <div class="stat"><span class="n">{n_skip}</span><span class="l">SKIP</span></div>
      <div class="stat"><span class="n">{len(other_df)}</span><span class="l">Buy games</span></div>
    </div>
  </header>

  <div class="callout">{CALLOUT}
  </div>

  {strong_html}

  <div class="col-legend">
    <span>Matchup</span><span title="Season straight-up record, in matchup order">W-L</span><span title="Season record against the spread, in matchup order">ATS</span><span>Model pick</span><span>Win prob</span><span title="Model's side of the market spread, with tier">ATS pick</span><span>Spread (mkt)</span><span>Total (mkt)</span>
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
