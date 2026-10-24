"""
Backtests the first-TD-scorer method (build_first_td_picks.py) on a past
season's play-by-play, walk-forward: each week's game is scored using only
the weeks before it.

Two parts, scored separately so each knob is judged on its own:
  1. Which team scores the first offensive TD -- market implied-points
     ratio (raised to a power k) vs. the original flattened win prob.
  2. Which player on that team scores it -- the share settings in
     score_table() (expected-TD weight, recency weight, inactive filter),
     scored as binary log loss / Brier over each scoring team's top
     CANDIDATES players.
Then the full pick (team prob x share x offense share) for the old and
new settings: top-pick hit rate, hits vs. model-expected hits.

Usage:
    python backtest_first_td.py --year 2025
"""
import argparse
import itertools
import json
import math
import statistics

import pandas as pd

import build_first_td_picks as b
from grade_first_td_picks import scorer_from_text

FIRST_WEEK = 3  # need two weeks of history before shares mean anything
LAST_WEEK = 15
CANDIDATES = 8
OLD_FLATTEN = 0.55


def first_td(plays):
    """gameId -> (kind, offense team, scorer key) of the game's first TD; kind 'off' or 'other'."""
    best = {}
    for p in plays:
        if not p.get("scoring") or "TOUCHDOWN" not in (p.get("playText") or "").upper() and "Touchdown" not in p["playType"]:
            continue
        order = (p["period"], -(p["clock"]["minutes"] * 60 + p["clock"]["seconds"]), p["playNumber"] or 0)
        if p["gameId"] not in best or order < best[p["gameId"]][0]:
            best[p["gameId"]] = (order, p)
    out = {}
    for gid, (_, p) in best.items():
        if p["playType"] in ("Rushing Touchdown", "Passing Touchdown"):
            kind = "rush" if p["playType"] == "Rushing Touchdown" else "target"
            _, key = b.ball_carrier(p["playText"], kind)
            if key is None:
                _, key = scorer_from_text(p["playText"])
            out[gid] = ("off", p["offense"], key)
        else:
            out[gid] = ("other", None, None)
    return out


def market(lines_path):
    """gameId -> (home pts, away pts, home win prob) from the median line across books."""
    out = {}
    for g in json.load(open(lines_path, encoding="utf-8")):
        ls = g.get("lines") or []
        spreads = [l["spread"] for l in ls if l.get("spread") is not None]
        totals = [l["overUnder"] for l in ls if l.get("overUnder") is not None]
        if not spreads or not totals:
            continue
        margin, total = -statistics.median(spreads), statistics.median(totals)
        hp = max((total + margin) / 2, b.MIN_IMPLIED_PTS)
        ap = max((total - margin) / 2, b.MIN_IMPLIED_PTS)
        mls = [(l["homeMoneyline"], l["awayMoneyline"]) for l in ls if l.get("homeMoneyline") and l.get("awayMoneyline")]
        if mls:
            imp = lambda o: -o / (-o + 100) if o < 0 else 100 / (o + 100)
            wp = statistics.median(imp(h) / (imp(h) + imp(a)) for h, a in mls)
        else:
            wp = 1 / (1 + math.exp(-margin / 7.0))  # rough spread->win prob when no moneylines
        out[g["id"]] = (g["homeTeam"], g["awayTeam"], hp, ap, wp)
    return out


def logloss(p, y):
    p = min(max(p, 1e-4), 1 - 1e-4)
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2025)
    args = ap.parse_args()
    year = args.year

    plays = {w: b.week_plays(year, w, cache=True) for w in range(1, LAST_WEEK + 1)}
    opp = pd.DataFrame([r for w, ps in plays.items() for r in b.opportunity_rows(ps, w)])
    opp["bucket"] = pd.cut(opp["ytg"], [0, *b.YTG_BUCKETS], labels=False)
    firsts = {w: first_td(ps) for w, ps in plays.items()}
    lines = market(f"cfbd_raw/lines_{year}.json")

    games = [(w, gid, f) for w in range(FIRST_WEEK, LAST_WEEK + 1) for gid, f in firsts[w].items() if gid in lines]
    n_other = sum(f[0] == "other" for _, _, f in games)
    off_share = 1 - n_other / len(games)
    print(f"{len(games)} games with a line and a TD, weeks {FIRST_WEEK}-{LAST_WEEK}; "
          f"first TD was offensive in {off_share:.1%} (live setting OFFENSE_SHARE = {b.OFFENSE_SHARE})")

    # --- 1. team that scores the first offensive TD ---
    off_games = [(w, gid, f) for w, gid, f in games if f[0] == "off"]
    print("\nWhich team scores first (offensive first TDs only, lower = better):")
    team_models = {"old: win prob flattened x0.55": lambda h, a, hp, ap, wp: 0.5 + (wp - 0.5) * OLD_FLATTEN}
    for k in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0):
        team_models[f"implied pts ratio, k={k}"] = lambda h, a, hp, ap, wp, k=k: hp ** k / (hp ** k + ap ** k)
    team_res = {}
    for name, fn in team_models.items():
        ll = [logloss(fn(*lines[gid]), f[1] == lines[gid][0]) for _, gid, f in off_games]
        br = [(fn(*lines[gid]) - (f[1] == lines[gid][0])) ** 2 for _, gid, f in off_games]
        team_res[name] = statistics.mean(ll)
        print(f"  {name:32s} logloss {statistics.mean(ll):.4f}  brier {statistics.mean(br):.4f}")
    print(f"  {'coin flip':32s} logloss {math.log(2):.4f}  brier 0.2500")

    # --- 2. which player on the scoring team ---
    grid = list(itertools.product((0.0, 0.3, 0.5, 0.7, 1.0), (1.0, 2.0, 3.0), (0, 2)))
    tables = {}
    rows = []
    for xw, rw, ig in grid:
        ll, br, cover = [], [], 0
        for w in range(FIRST_WEEK, LAST_WEEK + 1):
            t = b.score_table(opp[opp["week"] < w], xtd_weight=xw, recent_weight=rw, inactive_games=ig)
            tables[(xw, rw, ig, w)] = t
            tot = t.groupby("team")["score"].sum()
            by_team = {team: g.nlargest(CANDIDATES, "score") for team, g in t.groupby("team")}
            for ww, gid, f in off_games:
                if ww != w or f[1] not in by_team or tot.get(f[1], 0) <= 0:
                    continue
                c = by_team[f[1]]
                cover += f[2] in set(c["key"])
                for key, sc in zip(c["key"], c["score"]):
                    p, y = sc / tot[f[1]], key == f[2]
                    ll.append(logloss(p, y))
                    br.append((p - y) ** 2)
        rows.append({"xtd_weight": xw, "recent_weight": rw, "inactive_games": ig,
                     "logloss": statistics.mean(ll), "brier": statistics.mean(br),
                     "scorer_in_top8": cover / len(off_games)})
    res = pd.DataFrame(rows).sort_values("logloss")
    res.to_csv(f"first_td_backtest_{year}.csv", index=False)
    print(f"\nWhich player on the scoring team (top {CANDIDATES} candidates; lower logloss = better), best 8 + old:")
    pd.set_option("display.width", 200)
    old = res[(res.xtd_weight == 0) & (res.recent_weight == 1) & (res.inactive_games == 0)]
    print(pd.concat([res.head(8), old]).round(4).to_string(index=False))

    # --- 3. full picks: old vs. best vs. current live settings ---
    best_team = min((n for n in team_res if n.startswith("implied")), key=team_res.get)
    best = res.iloc[0]
    setups = {
        "old method": ("old: win prob flattened x0.55", (0.0, 1.0, 0)),
        "live settings": ("implied pts ratio, k=1.0", (b.XTD_WEIGHT, b.RECENT_WEIGHT, b.INACTIVE_GAMES)),
        "best fitted": (best_team, (best.xtd_weight, best.recent_weight, int(best.inactive_games))),
    }
    print(f"\nFull picks (one per game, all {len(games)} games), offense share fitted at {off_share:.3f}:")
    for name, (tm, (xw, rw, ig)) in setups.items():
        if (xw, rw, ig, FIRST_WEEK) not in tables:
            for w in range(FIRST_WEEK, LAST_WEEK + 1):
                tables[(xw, rw, ig, w)] = b.score_table(opp[opp["week"] < w], xtd_weight=xw, recent_weight=rw, inactive_games=ig)
        hits, exp, n = 0, 0.0, 0
        for w, gid, f in games:
            t = tables[(xw, rw, ig, w)]
            h, a = lines[gid][0], lines[gid][1]
            ph = team_models[tm](*lines[gid])
            cands = []
            for team, pt in ((h, ph), (a, 1 - ph)):
                tt = t[t["team"] == team]
                if tt["score"].sum() <= 0:
                    continue
                top = tt.nlargest(1, "score").iloc[0]
                cands.append((pt * off_share * top["score"] / tt["score"].sum(), team, top["key"]))
            if not cands:
                continue
            p, team, key = max(cands)
            n += 1
            exp += p
            hits += f[0] == "off" and f[1] == team and f[2] == key
        print(f"  {name:14s} [{tm}; xtd {xw}, recent x{rw}, inactive {ig}]: "
              f"{hits}/{n} = {hits / n:.1%} hit, model expected {exp:.0f} ({exp / n:.1%})")


if __name__ == "__main__":
    main()
