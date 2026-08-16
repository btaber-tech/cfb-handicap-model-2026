"""
Public betting % / Reverse Line Movement (RLM) report.

Reads vegasinsider_public_betting_2026wkN_raw.json (captured manually via
an authenticated browser session -- see README note below, this data is
NOT reachable by WebFetch/an unauthenticated scrape, VegasInsider gates
all but one game behind a free account login) and checks each game's
bets% (ticket-count majority, the standard RLM baseline) against the
line's own OPEN -> CONSENSUS move (parsed from the same VegasInsider
snapshot) to flag real Reverse Line Movement: the spread actually moving
AGAINST the majority of tickets.

IMPORTANT, learned the hard way (2026-08-16): the movement check MUST use
VegasInsider's own open/consensus figures, which are captured in the same
snapshot as the bets%/money% -- NOT our separately-polled
line_movement_2026_wkN.csv (see build_line_movement_report.py), which
only spans whatever window the local Scheduled Task happened to be
running and is not time-aligned with the bet-percentage snapshot. A first
version of this script mixed the two and produced a wrong RLM flag on
Hawai'i @ Stanford (VegasInsider: Stanford opened -3, consensus -5.5,
a real -2.5 move WITH the 60% bets majority on Stanford -- not against
it; the wrongly-flagged version instead used our own Bovada history,
which only covered a narrow window that happened to catch a small -5.5
to -5.0 wobble sitting inside that larger, correctly-directioned move).
Our own polled history is still shown per-game for extra color where it
overlaps, clearly labeled as a separate, narrower window -- never as the
RLM trigger itself.

Caveat worth keeping in the report: several real flags found so far sit
on lopsided/blowout matchups (85%+ of bets on one side). Naive bet-count
RLM theory assumes the book is balancing action, but a 90%+-on-one-side
game typically draws too little real money for that to be the driver --
lines on 30+ point mismatches likely move mostly on power-rating/model
updates across books, not retail bet pressure. Flags on those games are
marked lower-confidence in the report; flags on games with a closer bet
split (still lopsided, but not a near-unanimous crowd) are shown at
normal confidence since bet-count theory is more plausible there.

Usage:
    python build_public_betting_report.py --raw vegasinsider_public_betting_2026wk1_raw.json --movement line_movement_2026_wk1.csv
"""
import argparse
import html as html_lib
import json
import re
from datetime import datetime

import pandas as pd


# VegasInsider prints the favored team as a short abbreviation, not its
# full name (e.g. "STAN" for Stanford, "UVA" for Virginia). Needed to
# figure out which side (home/away) the printed number belongs to, so
# the spread can be converted to a consistent home-team-perspective
# value (negative = home favored) regardless of which side is favored.
ABBREV_HINTS = {
    "STAN": "Stanford", "UVA": "Virginia", "NDSU": "North Dakota State",
    "EMU": "Eastern Michigan", "FSU": "Florida State", "UNLV": "UNLV",
    "TCU": "TCU", "USC": "USC", "SJSU": "San Jose State",
}


def parse_home_spread(line_str, home_team, away_team):
    """'STAN -5.5 o49.5 -218' -> -5.5 if STAN is home, +5.5 if STAN is away.
    Never assume the printed abbreviation is the home team -- check which
    side it actually names."""
    m = re.search(r"^(\S+)\s+([+-]\d+\.?\d*)", line_str)
    if not m:
        return None
    abbrev, value = m.group(1), float(m.group(2))
    named_team = ABBREV_HINTS.get(abbrev, abbrev)
    if named_team == home_team or home_team.startswith(named_team):
        return value
    if named_team == away_team or away_team.startswith(named_team):
        return -value
    raise ValueError(f"Could not match abbreviation {abbrev!r} to home={home_team!r} or away={away_team!r}")


def esc(s):
    return html_lib.escape(str(s), quote=True)


def diff_badge(money, bets):
    d = money - bets
    cls = "diff-pos" if d > 0 else ("diff-neg" if d < 0 else "diff-flat")
    return f'<span class="diff {cls}">{d:+d}</span>'


def build_game_card(g, movement_by_pair):
    away, home = g["away"], g["home"]
    key = (home["team"], away["team"])
    our_polled_move = movement_by_pair.get(key)  # our own snapshot history, shown as separate context only

    open_spread = parse_home_spread(g["open"], home["team"], away["team"])
    cons_spread = parse_home_spread(g["consensus"], home["team"], away["team"])

    rlm = None
    if open_spread is not None and cons_spread is not None:
        move = cons_spread - open_spread
        if abs(move) >= 0.01:
            # move<0 => line moved toward HOME; move>0 => moved toward AWAY
            moved_toward = "home" if move < 0 else "away"
            majority_side = "home" if home["bets_spread"] > away["bets_spread"] else "away"
            if moved_toward != majority_side:
                majority_pct = max(home["bets_spread"], away["bets_spread"])
                low_confidence = majority_pct >= 85  # blowout: naive bet-count theory unreliable
                rlm = {"move": move, "moved_toward": moved_toward, "low_confidence": low_confidence}

    def team_row(t, other, is_home):
        bd = diff_badge(t["money_spread"], t["bets_spread"])
        return f"""
            <div class="pb-team">
              <div class="pb-team-name">{esc(t['team'])}{' <span class="home-tag" title="Home team">HOME</span>' if is_home else ''}</div>
              <div class="pb-bars">
                <div class="pb-bar-row"><span class="pb-bar-label">Bets</span>
                  <div class="pb-bar-track"><div class="pb-bar-fill pb-bar-bets" style="width:{t['bets_spread']}%"></div></div>
                  <span class="pb-bar-pct">{t['bets_spread']}%</span></div>
                <div class="pb-bar-row"><span class="pb-bar-label">Money</span>
                  <div class="pb-bar-track"><div class="pb-bar-fill pb-bar-money" style="width:{t['money_spread']}%"></div></div>
                  <span class="pb-bar-pct">{t['money_spread']}%</span></div>
              </div>
              <div class="pb-diff-line">money &minus; bets: {bd}</div>
            </div>"""

    rlm_html = ""
    if rlm:
        towards_team = home["team"] if rlm["moved_toward"] == "home" else away["team"]
        conf_note = (' <span class="low-conf">(low confidence &mdash; near-unanimous bets, likely a '
                     "power-rating move rather than bet pressure)</span>" if rlm["low_confidence"] else "")
        rlm_html = (f'<div class="rlm-flag">&#9888; Reverse line movement: consensus spread moved '
                    f'{rlm["move"]:+.1f} pts toward <strong>{esc(towards_team)}</strong> (open {g["open"]} '
                    f'&rarr; consensus {g["consensus"]}), the side with the <em>minority</em> of bets '
                    f'&mdash; against the crowd.{conf_note}</div>')

    our_move_html = ""
    if our_polled_move:
        parts = [f'{esc(m["provider"])} {m["spread_move"]:+.1f}' for m in our_polled_move
                 if m["spread_move"] is not None and abs(m["spread_move"]) > 0.01]
        if parts:
            our_move_html = (f'<div class="our-move">Separately, our own polled snapshots '
                              f'(narrower window) show: {", ".join(parts)}</div>')

    card_class = "pb-card rlm" if rlm else "pb-card"
    return f"""
        <div class="{card_class}">
          <div class="pb-matchup">{esc(away['team'])} <span class="at">@</span> {esc(home['team'])}</div>
          <div class="pb-line">Open {esc(g['open'])} &rarr; Consensus {esc(g['consensus'])}</div>
          <div class="pb-teams">{team_row(away, home, False)}{team_row(home, away, True)}</div>
          {rlm_html}{our_move_html}
        </div>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="vegasinsider_public_betting_2026wk1_raw.json")
    ap.add_argument("--movement", default="line_movement_2026_wk1.csv")
    ap.add_argument("--out", default="public_betting_report_src.html")
    args = ap.parse_args()

    data = json.load(open(args.raw, encoding="utf-8"))
    games = data["games"]

    mv = pd.read_csv(args.movement)
    movement_by_pair = {}
    for _, r in mv.iterrows():
        key = (r["home"], r["away"])
        movement_by_pair.setdefault(key, []).append(
            {"provider": r["provider"], "spread_move": r["spread_move"] if pd.notna(r["spread_move"]) else None}
        )

    cards = [build_game_card(g, movement_by_pair) for g in games]
    n_rlm = sum(1 for c in cards if 'class="pb-card rlm"' in c)

    now = datetime.now()
    generated = f"{now.strftime('%B')} {now.day}, {now.year}"

    html_out = f"""<title>Reverse Line Movement Watch</title>
<meta name="description" content="Public bets % vs. money % for every Week 1 2026 game with data posted, cross-checked against real spread movement for reverse line movement.">
{CSS}
<div class="wrap">
  <header class="masthead">
    <p class="eyebrow">2026 CFB Handicap Model &middot; Generated {esc(generated)}</p>
    <h1>Reverse Line Movement Watch</h1>
    <p class="subhead">Real sportsbook % of bets and % of money for every Week 1 game with public betting
    data posted so far, checked against the line's own open-to-consensus move to flag actual reverse line
    movement &mdash; not just a bets/money split sitting there, but the line demonstrably moving
    <em>against</em> the majority of tickets.</p>
    <div class="stat-row">
      <div class="stat"><span class="n">{len(games)}</span><span class="l">Games with data</span></div>
      <div class="stat"><span class="n">{n_rlm}</span><span class="l">RLM flags</span></div>
    </div>
  </header>

  <div class="callout">
    <strong>Coverage is thin right now, on purpose.</strong> Sportsbooks post real bet/money percentages
    game by game as betting volume builds, and only {len(games)} of the week's games have any posted
    yet &mdash; this will fill in as kickoff (Aug 29) approaches. <strong>Every game here is checked for
    RLM</strong> by comparing the majority ticket-count side (bets%) against the line's own open&rarr;
    consensus move (the figures VegasInsider captures in the same snapshot as the bet percentages, so
    they're properly time-aligned). Some flags are marked lower-confidence when 85%+ of bets sit on one
    side &mdash; those blowout games likely have too little real money in play for classic bet-pressure
    theory to explain the move; it's probably a power-rating update instead. Where our own separately-
    polled snapshots (<code>line_snapshots_2026.csv</code>) overlap, they're shown too, clearly labeled
    as a different, narrower time window &mdash; not the trigger for any flag.
  </div>

  <section class="games">
    <div class="pb-grid">{''.join(cards)}
    </div>
  </section>

  <footer class="notes">
    <p><strong>How this is captured:</strong> VegasInsider.com (Better Collective, same network as Action
    Network) gates all but one "featured" game's bet/money percentages behind a free account. This dataset
    was captured manually via an authenticated browser session on {esc(data.get('captured_at', ''))} &mdash;
    it is <strong>not yet an automated recurring capture</strong> the way <code>line_snapshots_2026.csv</code>
    is (that runs unattended every 6 hours locally). Turning this into a real weekly time series needs a
    session-based capture design, which is a follow-up, not done here.</p>
    <p><strong>RLM definition used:</strong> the spread moving in the direction the <em>minority</em> of
    bets (ticket count, not dollars) would want &mdash; the standard textbook definition. Money% is shown
    alongside as the usual explanation (fewer, larger bets outweighing more numerous small ones), not as
    the trigger condition itself.</p>
    <p>Data: VegasInsider.com public betting percentages; CollegeFootballData.com <code>/lines</code>
    (Bovada, DraftKings) for real spread movement.</p>
  </footer>
</div>
"""
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"Wrote {args.out} -- {len(games)} games, {n_rlm} RLM flags")


CSS = """
<style>
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #12140f; --surface: #191c15; --surface-2: #20241b; --border: #33382c;
    --text: #edeee6; --text-muted: #9aa090; --accent: #5da682; --accent-soft: #1f2f26;
    --gold: #d1ab52; --gold-soft: #2b2617; --rust: #d98f78; --rust-soft: #2c1e19;
  }
}
:root[data-theme="dark"] {
  --bg: #12140f; --surface: #191c15; --surface-2: #20241b; --border: #33382c;
  --text: #edeee6; --text-muted: #9aa090; --accent: #5da682; --accent-soft: #1f2f26;
  --gold: #d1ab52; --gold-soft: #2b2617; --rust: #d98f78; --rust-soft: #2c1e19;
}
:root {
  --bg: #f5f4ef; --surface: #ffffff; --surface-2: #edece4; --border: #dcd8ca;
  --text: #1a1e19; --text-muted: #656a5e; --accent: #2f6b4f; --accent-soft: #e3ede7;
  --gold: #9c7a23; --gold-soft: #f2ead2; --rust: #8a4a3a; --rust-soft: #f3e6e1;
  --font-display: Georgia, "Iowan Old Style", "Palatino Linotype", serif;
  --font-body: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  --font-mono: ui-monospace, "SFMono-Regular", "Cascadia Mono", Consolas, monospace;
}
* { box-sizing: border-box; }
body { background: var(--bg); color: var(--text); font-family: var(--font-body); margin: 0; padding: 0 0 4rem; line-height: 1.45; }
.wrap { max-width: 920px; margin: 0 auto; padding: 0 1.5rem; }
header.masthead { border-bottom: 1px solid var(--border); padding: 2.75rem 0 1.75rem; margin-bottom: 2rem; }
.eyebrow { font-family: var(--font-mono); font-size: 0.72rem; letter-spacing: 0.11em; text-transform: uppercase; color: var(--accent); margin: 0 0 0.6rem; }
h1 { font-family: var(--font-display); font-size: 2.15rem; font-weight: 700; margin: 0 0 0.5rem; text-wrap: balance; letter-spacing: -0.01em; }
.subhead { color: var(--text-muted); font-size: 0.98rem; max-width: 68ch; margin: 0; }
.subhead em { color: var(--text); font-style: normal; }
.stat-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 1px; background: var(--border); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; margin: 1.75rem 0 0; max-width: 340px; }
.stat { background: var(--surface); padding: 0.9rem 1.1rem; }
.stat .n { font-family: var(--font-mono); font-size: 1.5rem; font-weight: 600; font-variant-numeric: tabular-nums; display: block; }
.stat .l { color: var(--text-muted); font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.06em; }
.callout { background: var(--accent-soft); border: 1px solid var(--border); border-left: 3px solid var(--accent); border-radius: 8px; padding: 1rem 1.2rem; font-size: 0.92rem; color: var(--text); margin: 0 0 2.5rem; }
.callout strong { color: var(--accent); }
.callout em { font-style: normal; font-weight: 600; }
.pb-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 1rem; }
.pb-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 1.1rem 1.2rem; }
.pb-card.rlm { border-color: var(--rust); box-shadow: 0 0 0 1px var(--rust); }
.pb-matchup { font-weight: 700; font-size: 1rem; }
.at { color: var(--text-muted); font-weight: 400; font-size: 0.85em; }
.pb-line { font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted); margin: 0.2rem 0 0.9rem; }
.home-tag { color: var(--accent); font-size: 0.65em; font-weight: 700; font-family: var(--font-mono); vertical-align: 0.15em; margin-left: 0.25em; }
.pb-teams { display: flex; flex-direction: column; gap: 0.8rem; }
.pb-team-name { font-weight: 600; font-size: 0.88rem; margin-bottom: 0.3rem; }
.pb-bar-row { display: grid; grid-template-columns: 3.2rem 1fr 2.4rem; align-items: center; gap: 0.4rem; margin-bottom: 0.25rem; }
.pb-bar-label { font-family: var(--font-mono); font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-muted); }
.pb-bar-track { height: 7px; background: var(--surface-2); border-radius: 4px; overflow: hidden; }
.pb-bar-fill { height: 100%; border-radius: 4px; }
.pb-bar-bets { background: var(--gold); }
.pb-bar-money { background: var(--accent); }
.pb-bar-pct { font-family: var(--font-mono); font-size: 0.72rem; text-align: right; font-variant-numeric: tabular-nums; }
.pb-diff-line { font-family: var(--font-mono); font-size: 0.68rem; color: var(--text-muted); margin-top: 0.15rem; }
.diff { font-weight: 700; }
.diff-pos { color: var(--accent); }
.diff-neg { color: var(--rust); }
.diff-flat { color: var(--text-muted); }
.rlm-flag { margin-top: 0.9rem; padding: 0.6rem 0.7rem; background: var(--rust-soft); border-radius: 6px; font-size: 0.8rem; color: var(--text); }
.rlm-flag strong { color: var(--rust); }
.low-conf { color: var(--text-muted); font-weight: 400; }
.our-move { margin-top: 0.5rem; font-family: var(--font-mono); font-size: 0.68rem; color: var(--text-muted); }
footer.notes { margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid var(--border); color: var(--text-muted); font-size: 0.82rem; }
footer.notes p { margin: 0 0 0.7rem; }
footer.notes code { font-family: var(--font-mono); background: var(--surface-2); padding: 0.1rem 0.3rem; border-radius: 3px; font-size: 0.85em; }
@media (max-width: 420px) {
  .pb-grid { grid-template-columns: 1fr; }
}
</style>
"""

if __name__ == "__main__":
    main()
