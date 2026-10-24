"""
Walk-forward fit + backtest for build_q1_matchups.py on 2025 and 2026
(CFBD games, lines and cached play-by-play). Each week's team stats use
only earlier weeks.

1. Single-stat correlations with the actual Q1 margin (home perspective)
2. Fits WEIGHTS (OLS on team-games: Q1 points ~ matchup features) on one
   season and tests the projected margin on the other, both directions,
   against the market's spread-implied Q1 margin
3. Most lopsided matchups per week: did the edge team actually lead?
4. Prints the final WEIGHTS fitted on both seasons -- paste into
   build_q1_matchups.py
5. Fits TAIL: logistic P(a side leads by X+ after Q1 | its projected
   margin) for each LEAD_THRESHOLDS, checks calibration on the held-out
   season, and prints the final TAIL to paste into build_q1_matchups.py
"""
import glob
import json
import os

import numpy as np

from build_q1_matchups import LEAD_THRESHOLDS, MARKET_Q1_SHARE, MIN_GAMES, side_features, team_table
from build_q1_projections import PROVIDERS
from cfbd_fetch import cfbd_get

SEASONS = {2025: range(4, 16), 2026: range(4, 9)}
# rz_match fitted to a small negative weight (noise), so it is left out of the fit.
FEATURES = ("pts_match", "q1_match", "home")
TOP_PER_WEEK = 10


def season_data(year):
    if year == 2025:
        games = json.load(open("cfbd_raw/games_2025.json", encoding="utf-8"))
        lines = json.load(open("cfbd_raw/lines_2025.json", encoding="utf-8"))
    else:
        games = cfbd_get("/games", params={"year": year, "seasonType": "regular"})
        lines = [l for f in sorted(glob.glob(f"cfbd_raw/lines_{year}_wk*_final.json"))
                 for l in json.load(open(f, encoding="utf-8"))]
    games = [g for g in games if g.get("seasonType") == "regular"]
    lines = {l["id"]: l for l in lines}
    plays = {}
    for w in range(0, 16):
        path = f"cfbd_raw/plays_{year}_wk{w}.json"
        plays[w] = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else []
    return games, lines, plays


def market(lines, gid):
    ls = [l for l in lines.get(gid, {}).get("lines", []) if l.get("spread") is not None]
    if not ls:
        return None
    ls.sort(key=lambda l: PROVIDERS.index(l["provider"]) if l["provider"] in PROVIDERS else len(PROVIDERS))
    return -MARKET_Q1_SHARE * ls[0]["spread"]


def game_rows(year):
    """One row per FBS-vs-FBS game: both sides' features, actual Q1 points, market Q1 margin."""
    games, lines, plays = season_data(year)
    rows = []
    for week in SEASONS[year]:
        prior = [g for g in games if g["week"] < week]
        table, league_rz = team_table(prior, [p for w in range(0, week) for p in plays[w]])
        for g in games:
            if g["week"] != week or g.get("homeClassification") != "fbs" or g.get("awayClassification") != "fbs":
                continue
            h, a = g.get("homeLineScores"), g.get("awayLineScores")
            m = market(lines, g["id"])
            if not (h and a) or m is None or g["homeTeam"] not in table.index or g["awayTeam"] not in table.index:
                continue
            H, A = table.loc[g["homeTeam"]], table.loc[g["awayTeam"]]
            if H["games"] < MIN_GAMES or A["games"] < MIN_GAMES:
                continue
            rows.append({"year": year, "week": week, "home_q1": h[0], "away_q1": a[0], "mkt": m,
                         "hf": side_features(H, A, league_rz, not g["neutralSite"]),
                         "af": side_features(A, H, league_rz, False)})
    return rows


def fit(rows):
    X = np.array([[r[s][k] for k in FEATURES] for r in rows for s in ("hf", "af")])
    y = np.array([r[q] for r in rows for q in ("home_q1", "away_q1")])
    beta = np.linalg.lstsq(np.c_[np.ones(len(X)), X], y, rcond=None)[0]
    return {"intercept": beta[0], **dict(zip(FEATURES, beta[1:])), "rz_match": 0.0}


def predict(rows, w):
    def pts(f):
        return w["intercept"] + sum(w[k] * f[k] for k in FEATURES)
    return np.array([pts(r["hf"]) - pts(r["af"]) for r in rows])


def logistic(x, event, iters=50):
    """(a, b) for P(event) = 1 / (1 + exp(-(a + b x))), by Newton's method."""
    X = np.c_[np.ones(len(x)), x]
    beta = np.zeros(2)
    for _ in range(iters):
        p = 1 / (1 + np.exp(-X @ beta))
        beta += np.linalg.solve(X.T @ (X * (p * (1 - p))[:, None]), X.T @ (event - p))
    return beta


def sides(rows, w):
    """Each game from both sides: (projected margin for that side, actual margin for that side)."""
    p = predict(rows, w)
    actual = np.array([r["home_q1"] - r["away_q1"] for r in rows])
    return np.r_[p, -p], np.r_[actual, -actual]


def fit_tail(rows, w):
    m, a = sides(rows, w)
    return {t: logistic(m, (a >= t).astype(float)) for t in LEAD_THRESHOLDS}


def tail_prob(beta, m):
    return 1 / (1 + np.exp(-(beta[0] + beta[1] * m)))


def main():
    data = {y: game_rows(y) for y in SEASONS}
    for y, rows in data.items():
        print(f"{y}: {len(rows)} games (weeks {SEASONS[y].start}-{SEASONS[y].stop - 1})")

    print("\n1. Single-stat correlation with actual Q1 margin (home side minus away side):")
    print(f"   {'':12s} " + "  ".join(f"{y:>6}" for y in data))
    for k in ("pts_match", "q1_match", "rz_match"):
        rs = []
        for rows in data.values():
            x = np.array([r["hf"][k] - r["af"][k] for r in rows])
            rs.append(np.corrcoef(x, [r["home_q1"] - r["away_q1"] for r in rows])[0, 1])
        print(f"   {k:12s} " + "  ".join(f"{v:6.3f}" for v in rs))
    rs = [np.corrcoef([r["mkt"] for r in rows], [r["home_q1"] - r["away_q1"] for r in rows])[0, 1]
          for rows in data.values()]
    print(f"   {'market':12s} " + "  ".join(f"{v:6.3f}" for v in rs))

    print("\n2. Fit on one season, test on the other (r with actual Q1 margin, MAE):")
    years = list(data)
    for tr, te in ((years[0], years[1]), (years[1], years[0])):
        w = fit(data[tr])
        rows = data[te]
        p = predict(rows, w)
        actual = np.array([r["home_q1"] - r["away_q1"] for r in rows])
        mkt = np.array([r["mkt"] for r in rows])
        print(f"   fit {tr} -> test {te}: weighted model r={np.corrcoef(p, actual)[0, 1]:.3f} "
              f"MAE {np.abs(p - actual).mean():.2f} | market r={np.corrcoef(mkt, actual)[0, 1]:.3f} "
              f"MAE {np.abs(mkt - actual).mean():.2f} | model-vs-market gap r="
              f"{np.corrcoef(p - mkt, actual - mkt)[0, 1]:.3f}")
        top = []
        for week in SEASONS[te]:
            idx = [i for i, r in enumerate(rows) if r["week"] == week]
            top += sorted(idx, key=lambda i: -abs(p[i]))[:TOP_PER_WEEK]
        side = np.sign(p[top])
        a = actual[top] * side
        print(f"     top {TOP_PER_WEEK}/week ({len(top)} games): projected {np.abs(p[top]).mean():.1f}, "
              f"actual {a.mean():.1f}, edge team led {np.mean(a > 0):.0%} / tied {np.mean(a == 0):.0%} / "
              f"trailed {np.mean(a < 0):.0%}")

    w = fit([r for rows in data.values() for r in rows])
    print("\n3. Final WEIGHTS, fitted on both seasons:")
    print("WEIGHTS = {" + ", ".join(f'"{k}": {v:.3f}' for k, v in w.items()) + "}")

    print("\n4. P(side leads by X+ after Q1), fit on one season, test on the other:")
    for tr, te in ((years[0], years[1]), (years[1], years[0])):
        wt = fit(data[tr])
        tail = fit_tail(data[tr], wt)
        m, a = sides(data[te], wt)
        for t in LEAD_THRESHOLDS:
            p = tail_prob(tail[t], m)
            print(f"   fit {tr} -> test {te}, {t}+: predicted {p.mean():.3f} vs actual {(a >= t).mean():.3f} overall")
            for lo, hi in ((0, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 1)):
                sel = (p >= lo) & (p < hi)
                if sel.sum() >= 15:
                    print(f"      pred {lo:.1f}-{hi:.1f}: n={sel.sum():4d} predicted {p[sel].mean():.3f} "
                          f"actual {(a[sel] >= t).mean():.3f}")

    tail = fit_tail([r for rows in data.values() for r in rows], w)
    print("\n5. Final TAIL, fitted on both seasons:")
    print("TAIL = {" + ", ".join(f"{t}: ({b[0]:.3f}, {b[1]:.3f})" for t, b in tail.items()) + "}")


if __name__ == "__main__":
    main()
