"""
ATS consensus across four independent sides, and how each agreement level has done this season.

The four sources (each either names a side for a game or abstains):
  - SGPN:   at least SGPN_MIN analysts (default 5) on the same side, from
            sgpn_picks_{year}.csv (fetch_sgpn_picks.py). Fewer pickers on a side = abstain.
  - SP+:    Bill Connelly's ATS pick from his weekly sheet (sp_ats_pick).
  - Model:  our model's ATS side (ats_side). Completed weeks use model_replay_{year}/,
            which is the CURRENT model formula replayed on each week's projection-time
            data, so the record isn't a mix of old and new formulas. The current week
            uses the live week{N}_{year}_projections.csv.
  - Sharp:  "Market sharp side" = the side the consensus spread moved toward from open to
            close (median across books), when the move is at least SHARP_MIN_MOVE points.
            For an unfinished week, "close" is the latest line.
            Caveat: a move can come from injury or news, not just sharp money.

Grading is against the median CLOSING spread for every source, so all four are judged on the
same number (pushes excluded). Only FBS-vs-FBS games our model projects are included.

Outputs consensus_{year}.csv (one row per game) and prints the season summary.
build_artifact.py calls consensus_section_html() for the weekly page.

Usage:
    python build_consensus.py --year 2026
    python build_consensus.py --year 2026 --rebuild-replay   # re-run model_replay_{year}/ first
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import date

import pandas as pd

SGPN_MIN = 5
SHARP_MIN_MOVE = 0.5
SOURCES = ["sgpn", "sp", "model", "sharp"]
LABELS = {"sgpn": "SGPN (5+ experts)", "sp": "SP+", "model": "Our model", "sharp": "Market sharp side"}

# Tallysight/SGPN school names -> CFBD names (FBS only; FCS games aren't modelled).
SGPN_TO_CFBD = {
    "Appalachian State": "App State", "Brigham Young": "BYU", "Hawaii": "Hawai'i",
    "Louisiana-Lafayette": "Louisiana", "Louisiana-Monroe": "UL Monroe", "Miami (FL)": "Miami",
    "North Carolina State": "NC State", "Sam Houston State": "Sam Houston",
    "San Jose State": "San José State",
}


def _median(vals):
    vals = sorted(v for v in vals if v is not None)
    return vals[len(vals) // 2] if vals else None


def _lines(year, week):
    """{game_id: (open_home_margin, close_home_margin, final?)}; positive = home favoured."""
    for name, final in ((f"lines_{year}_wk{week}_final.json", True), (f"lines_{year}_wk{week}.json", False)):
        path = os.path.join("cfbd_raw", name)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
            out = {}
            for g in raw:
                ls = g.get("lines") or []
                o = _median([l.get("spreadOpen") for l in ls])
                c = _median([l.get("spread") for l in ls])
                out[g["id"]] = (-o if o is not None else None, -c if c is not None else None, final)
            return out
    return {}


def _results(year, week):
    path = os.path.join("cfbd_raw", f"games_{year}_wk{week}_final.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return {g["id"]: g["homePoints"] - g["awayPoints"] for g in json.load(f)
                if g.get("completed") and g.get("homePoints") is not None}


def _sgpn_sides(year):
    """[(date, frozenset{teams}, {team: n_analysts})] from the SGPN picks file."""
    path = f"sgpn_picks_{year}.csv"
    if not os.path.exists(path):
        return []
    s = pd.read_csv(path)
    for c in ("away", "home", "picked_team"):
        s[c] = s[c].map(lambda n: SGPN_TO_CFBD.get(n, n))
    s = s.drop_duplicates(["week", "away", "home", "analyst"])
    out = []
    for (d, a, h), grp in s.groupby(["game_date", "away", "home"]):
        out.append((pd.Timestamp(d), frozenset([a, h]), grp["picked_team"].value_counts().to_dict()))
    return out


def _match_sgpn(sgpn, teams, game_date):
    best = None
    for d, pair, counts in sgpn:
        if pair == teams and abs((d - game_date).days) <= 3:
            if best is None or abs((d - game_date).days) < abs((best[0] - game_date).days):
                best = (d, counts)
    return best[1] if best else None


def build_table(year, last_week, live_week=None):
    sgpn = _sgpn_sides(year)
    rows = []
    for w in range(1, last_week + 1):
        live = (w == live_week)
        proj_path = f"week{w}_{year}_projections.csv" if live else os.path.join(f"model_replay_{year}", f"week{w}_{year}_projections.csv")
        if not os.path.exists(proj_path):
            proj_path = f"week{w}_{year}_projections.csv"
        if not os.path.exists(proj_path):
            continue
        proj = pd.read_csv(proj_path)
        if "ats_side" not in proj.columns:
            continue
        lines, results = _lines(year, w), _results(year, w)
        for _, r in proj.iterrows():
            home, away = r["home"], r["away"]
            o, c, final = lines.get(r["game_id"], (None, None, False))
            if c is None and pd.notna(r.get("market_home_margin")):
                c = r["market_home_margin"]
            sides = {
                "model": r["ats_side"] if isinstance(r["ats_side"], str) else None,
                "sp": r["sp_ats_pick"] if isinstance(r.get("sp_ats_pick"), str) else None,
            }
            counts = _match_sgpn(sgpn, frozenset([home, away]), pd.Timestamp(r["date"]))
            sgpn_home = (counts or {}).get(home, 0)
            sgpn_away = (counts or {}).get(away, 0)
            sides["sgpn"] = home if sgpn_home >= SGPN_MIN and sgpn_home > sgpn_away else \
                            away if sgpn_away >= SGPN_MIN and sgpn_away > sgpn_home else None
            move = (c - o) if (o is not None and c is not None) else None
            sides["sharp"] = (home if move >= SHARP_MIN_MOVE else away if move <= -SHARP_MIN_MOVE else None) \
                if move is not None else None
            n_home = sum(1 for s in SOURCES if sides[s] == home)
            n_away = sum(1 for s in SOURCES if sides[s] == away)
            cons = home if n_home > n_away else away if n_away > n_home else None
            margin = results.get(r["game_id"])
            cover = None
            if margin is not None and c is not None and margin != c:
                cover = home if margin > c else away
            rows.append({
                "week": w, "game_id": r["game_id"], "date": r["date"], "away": away, "home": home,
                "open_home_margin": o, "close_home_margin": c, "line_move": move,
                "sgpn_home_n": sgpn_home, "sgpn_away_n": sgpn_away, "sgpn_matched": counts is not None,
                **{f"{s}_side": sides[s] for s in SOURCES},
                "n_agree": max(n_home, n_away), "n_oppose": min(n_home, n_away),
                "n_opinions": n_home + n_away, "consensus_side": cons,
                "home_margin": margin, "cover_side": cover,
            })
    return pd.DataFrame(rows)


def _rec(sub, side_col):
    g = sub[sub[side_col].notna() & sub["cover_side"].notna()]
    w = int((g[side_col] == g["cover_side"]).sum())
    return w, len(g) - w


def _fmt(w, l):
    return f"{w}-{l} ({w / (w + l):.1%})" if w + l else "-"


def summary(df):
    """[(label, wins, losses)]: each source alone, then agreement levels."""
    out = [(LABELS[s], *_rec(df, f"{s}_side")) for s in SOURCES]
    lv = [
        ("All 4 agree", (df.n_agree == 4)),
        ("3 agree, 4th abstains", (df.n_agree == 3) & (df.n_oppose == 0)),
        ("3 agree, 4th disagrees", (df.n_agree == 3) & (df.n_oppose == 1)),
        ("3+ agree, none opposed", (df.n_agree >= 3) & (df.n_oppose == 0)),
        ("2 agree, none opposed", (df.n_agree == 2) & (df.n_oppose == 0)),
        ("SGPN + SP+ + model agree", (df.sgpn_side.notna()) & (df.sgpn_side == df.sp_side) & (df.sp_side == df.model_side)),
    ]
    for label, mask in lv:
        out.append((label, *_rec(df[mask], "consensus_side")))
    return out


def consensus_section_html(year, week, esc):
    """Weekly-page section: this week's 3+-agreement games and season record by level."""
    path = f"consensus_{year}.csv"
    if not os.path.exists(path):
        return ""
    df = pd.read_csv(path)
    past = df[df.week < week]
    cur = df[(df.week == week) & (df.n_agree >= 3)].sort_values(["n_agree", "date"], ascending=[False, True])

    def side_cell(r, s):
        v = r[f"{s}_side"]
        if not isinstance(v, str):
            return '<td class="c-none">&ndash;</td>'
        cls = "c-agree" if v == r["consensus_side"] else "c-opp"
        return f'<td class="{cls}">{esc(v)}</td>'

    def line_txt(r):
        c = r["close_home_margin"]
        if pd.isna(c) or not isinstance(r["consensus_side"], str):
            return ""
        spread = -c if r["consensus_side"] == r["home"] else c
        return f"{spread:+.1f}"

    rows_html = "\n".join(
        f'<tr><td>{esc(r["away"])} <span class="at">@</span> {esc(r["home"])}</td>'
        f'<td class="c-pick">{esc(r["consensus_side"])} <span class="ats-line">{line_txt(r)}</span></td>'
        f'<td class="c-n">{int(r["n_agree"])}/4{" &middot; 1 opp" if r["n_oppose"] else ""}</td>'
        + "".join(side_cell(r, s) for s in SOURCES) + "</tr>"
        for _, r in cur.iterrows())
    this_week = (f"""<table class="cons-table"><thead><tr><th>Game</th><th>Consensus side</th><th>Agree</th>
      <th>SGPN 5+</th><th>SP+</th><th>Model</th><th>Sharp</th></tr></thead><tbody>
{rows_html}
      </tbody></table>""" if len(cur) else '<p class="muted">No game has 3 or more sources on the same side yet.</p>')

    rec_rows = "\n".join(
        f'<tr><td>{esc(label)}</td><td class="c-n">{_fmt(w, l)}</td></tr>' for label, w, l in summary(past))
    n_graded = int(past.cover_side.notna().sum())
    return f"""
  <section class="consensus">
    <h2>Consensus board</h2>
    <p class="muted">Four sides per game: SGPN experts (only when 5+ pick the same side), SP+, our model,
    and the market sharp side (the way the spread moved from open to close, at least {SHARP_MIN_MOVE:g} pts). Games below have
    3 or more on the same side. Green = agrees, gold = opposes, dash = no side.</p>
    {this_week}
    <h3>Season record, weeks 1&ndash;{week - 1} (graded at the closing line, {n_graded} games)</h3>
    <table class="cons-rec"><tbody>
{rec_rows}
    </tbody></table>
    <p class="muted">Record only, not a validated edge: one season, small samples at the higher agreement levels,
    and the sharp side uses the closing line it is graded against.</p>
  </section>"""


CONSENSUS_CSS = """
section.consensus { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 0.9rem 1.1rem; margin: 0 0 2rem; }
section.consensus h2 { font-family: var(--font-display); font-size: 1.15rem; margin: 0 0 0.4rem; }
section.consensus h3 { font-size: 0.9rem; margin: 1.2rem 0 0.4rem; }
section.consensus p { font-size: 0.82rem; margin: 0 0 0.6rem; }
.cons-table, .cons-rec { border-collapse: collapse; width: 100%; font-size: 0.84rem; }
.cons-rec { max-width: 460px; }
.cons-table th { text-align: left; font-family: var(--font-mono); font-size: 0.64rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted); padding: 0.3rem 0.4rem; border-bottom: 1px solid var(--border); }
.cons-table td, .cons-rec td { padding: 0.35rem 0.4rem; border-bottom: 1px solid var(--border); }
.cons-table tr:last-child td, .cons-rec tr:last-child td { border-bottom: none; }
.c-pick { font-weight: 600; }
.c-n { font-family: var(--font-mono); font-variant-numeric: tabular-nums; white-space: nowrap; }
.c-agree { color: var(--accent); font-weight: 600; }
.c-opp { color: var(--gold); }
.c-none { color: var(--text-muted); }
@media (max-width: 640px) { .cons-table th:nth-child(n+4), .cons-table td:nth-child(n+4) { display: none; } }
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--week", type=int, default=None, help="current (live) week; default = highest week with a projections file")
    ap.add_argument("--rebuild-replay", action="store_true")
    args = ap.parse_args()
    year = args.year
    week = args.week or max(int(f[4:].split("_")[0]) for f in os.listdir(".")
                            if f.startswith("week") and f.endswith(f"_{year}_projections.csv"))
    os.makedirs(f"model_replay_{year}", exist_ok=True)
    for w in range(1, week):  # replay any completed week not yet in model_replay_{year}/ (or all, with --rebuild-replay)
        if args.rebuild_replay or not os.path.exists(os.path.join(f"model_replay_{year}", f"week{w}_{year}_projections.csv")):
            subprocess.run([sys.executable, "build_week_projections.py", "--year", str(year), "--week", str(w),
                            "--skip-fetch", "--out-dir", f"model_replay_{year}"], check=True,
                           stdout=subprocess.DEVNULL)
    df = build_table(year, week, live_week=week)
    df.to_csv(f"consensus_{year}.csv", index=False)
    print(f"wrote consensus_{year}.csv: {len(df)} games, weeks 1-{week}; "
          f"SGPN matched {int(df.sgpn_matched.sum())}, SGPN 5+ side on {int(df.sgpn_side.notna().sum())}")
    past = df[df.week < week]
    print(f"\nSeason record, weeks 1-{week - 1}, graded at the close:")
    for label, w, l in summary(past):
        print(f"  {label:28s} {_fmt(w, l)}")
    cur = df[(df.week == week) & (df.n_agree >= 3)]
    print(f"\nWeek {week}: {len(cur)} games with 3+ sources agreeing")


if __name__ == "__main__":
    main()
