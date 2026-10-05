"""
Does adding in-season scoring to model_total help? (2026-10-05)

The live model_total (build_week_projections.py) is prior-season SP+
off/def only, run through a linear calibration -- it ignores every point
scored in the current season. This replays 2023-2025 (FBS v FBS regular
season, no lookahead) with team offense/defense updated from games
completed strictly before each game's week:

  in-season off(team)  = avg over games of: pts scored  - (opp_pre_def - avg_def)
  in-season def(team)  = avg over games of: pts allowed - (opp_pre_off - avg_off)

i.e. one-pass opponent adjustment anchored on the preseason SP+ split
(same idea as build_in_season_ratings.py's SRS for margins). Blended:

  off = (1-w)*pre_off + w*in_off   (same for def)
  raw = (home_off + away_def)/2 + (away_off + home_def)/2

Variants for w:
  pre      : w = 0 (current live behaviour)
  ramp     : the margin model's in_season_weight(week) schedule
  shrink_k : w = n / (n + k), n = games the team has played (per team)

Calibration (actual ~ a + b*raw) is fit leave-one-season-out so no season
is graded with constants fit on itself.

Usage:
    python build_totals_inseason_backtest.py
"""
import json

import numpy as np
import pandas as pd

from build_week_projections import in_season_weight

SEASONS = [2023, 2024, 2025]
SHRINK_KS = [2, 4]

trans = pd.read_csv("backtest_transitions.csv")
pre_off = trans.set_index(["season", "team"])["prior_sp_off_rating"].to_dict()
pre_def = trans.set_index(["season", "team"])["prior_sp_def_rating"].to_dict()


def variants():
    v = {"pre": lambda week, n: 0.0, "ramp": lambda week, n: in_season_weight(week)}
    for k in SHRINK_KS:
        v[f"shrink_{k}"] = (lambda kk: lambda week, n: n / (n + kk))(k)
    return v


VARIANTS = variants()

rows = []
for season in SEASONS:
    games = [g for g in json.load(open(f"cfbd_raw/games_{season}.json", encoding="utf-8"))
             if g["seasonType"] == "regular" and g["completed"]
             and g["homeClassification"] == "fbs" and g["awayClassification"] == "fbs"
             and g.get("homePoints") is not None]
    lines_by_id = {l["id"]: l.get("lines", []) for l in json.load(open(f"cfbd_raw/lines_{season}.json", encoding="utf-8"))}
    teams = {t for (s, t) in pre_off if s == season and pd.notna(pre_off[(s, t)])}
    avg_off = np.mean([pre_off[(season, t)] for t in teams])
    avg_def = np.mean([pre_def[(season, t)] for t in teams])

    for week in sorted({g["week"] for g in games}):
        off_s, def_s = {}, {}
        for g in games:
            if g["week"] >= week:
                continue
            h, a = g["homeTeam"], g["awayTeam"]
            if h not in teams or a not in teams:
                continue
            hp, ap = g["homePoints"], g["awayPoints"]
            off_s.setdefault(h, []).append(hp - (pre_def[(season, a)] - avg_def))
            def_s.setdefault(h, []).append(ap - (pre_off[(season, a)] - avg_off))
            off_s.setdefault(a, []).append(ap - (pre_def[(season, h)] - avg_def))
            def_s.setdefault(a, []).append(hp - (pre_off[(season, h)] - avg_off))

        for g in (g for g in games if g["week"] == week):
            h, a = g["homeTeam"], g["awayTeam"]
            if h not in teams or a not in teams:
                continue
            gl = lines_by_id.get(g["id"], [])
            closes = [l["overUnder"] for l in gl if l.get("overUnder") is not None]
            row = {"season": season, "week": week, "home": h, "away": a,
                   "actual_total": g["homePoints"] + g["awayPoints"],
                   "market_close": float(np.median(closes)) if closes else np.nan}
            for name, wf in VARIANTS.items():
                def blend(t, pre, ins):
                    n = len(ins.get(t, []))
                    w = wf(week, n) if n else 0.0
                    return (1 - w) * pre[(season, t)] + w * (np.mean(ins[t]) if n else 0.0)
                ho, hd = blend(h, pre_off, off_s), blend(h, pre_def, def_s)
                ao, ad = blend(a, pre_off, off_s), blend(a, pre_def, def_s)
                row[f"raw_{name}"] = (ho + ad) / 2 + (ao + hd) / 2
            rows.append(row)

df = pd.DataFrame(rows)

# leave-one-season-out calibration
for name in VARIANTS:
    df[f"cal_{name}"] = np.nan
    for s in SEASONS:
        train = df[df.season != s]
        b, a = np.polyfit(train[f"raw_{name}"], train.actual_total, 1)
        df.loc[df.season == s, f"cal_{name}"] = a + b * df.loc[df.season == s, f"raw_{name}"]
    b, a = np.polyfit(df[f"raw_{name}"], df.actual_total, 1)
    print(f"{name:9s} full-sample calibration: actual = {a:.3f} + {b:.4f}*raw")

df.to_csv("totals_inseason_backtest_games.csv", index=False)


def ou(sub, col, gap_min=0.0):
    s = sub.dropna(subset=["market_close"])
    gap = s[col] - s.market_close
    m = (gap.abs() >= gap_min) & (gap != 0) & (s.actual_total != s.market_close)
    hit = ((gap > 0) == (s.actual_total > s.market_close))[m]
    return f"{int(hit.sum())}-{int((~hit).sum())} ({hit.mean():.1%})" if len(hit) else "-"


for label, sub in [("all weeks", df), ("weeks 1-4", df[df.week <= 4]), ("weeks 5+", df[df.week >= 5])]:
    print(f"\n=== {label}  (n={len(sub)}) ===")
    mk = sub.dropna(subset=["market_close"])
    print(f"  market close: r={mk.market_close.corr(mk.actual_total):.3f}  MAE={(mk.market_close - mk.actual_total).abs().mean():.2f}  std={mk.market_close.std():.1f}")
    for name in VARIANTS:
        c = f"cal_{name}"
        print(f"  {name:9s}: r={sub[c].corr(sub.actual_total):.3f}  MAE={(sub[c] - sub.actual_total).abs().mean():.2f}  "
              f"std={sub[c].std():.1f} | O/U any {ou(sub, c)}  3+ {ou(sub, c, 3)}  6+ {ou(sub, c, 6)}")

print("\n=== weeks 5+, O/U by season (any gap / 3+) ===")
late = df[df.week >= 5]
for name in VARIANTS:
    print(f"  {name:9s}: " + "   ".join(f"{s}: {ou(late[late.season == s], f'cal_{name}')} / {ou(late[late.season == s], f'cal_{name}', 3)}" for s in SEASONS))
