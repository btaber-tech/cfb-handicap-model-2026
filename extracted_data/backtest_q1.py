"""
Backtest for build_q1_projections.py on cached CFBD 2022-25 games + lines
(FBS vs FBS, regular season, closing line).

Prints:
  1. Q1 margin vs. full-game market margin (slope, r, residual SD), tie rate
  2. Whether team "fast/slow starter" tendencies persist (prior season,
     in-season rolling, within-season split-half) -- they don't
  3. Leave-one-season-out log loss by kernel bandwidth, and calibration of
     P(favorite leads after Q1) at the production bandwidth
"""
import collections

import numpy as np

from build_q1_projections import HIST_YEARS, SPREAD_BW, history_games, q1_distribution


def main():
    rows = []
    for y in HIST_YEARS:
        rows += history_games([f"cfbd_raw/games_{y}.json"], [f"cfbd_raw/lines_{y}.json"])
    years = np.array([r[0] for r in rows])
    hist = np.array([r[1:5] for r in rows], dtype=float)
    mkt, q1 = hist[:, 0], hist[:, 2] - hist[:, 3]
    print(f"{len(rows)} games, {HIST_YEARS[0]}-{HIST_YEARS[-1]}")

    b, a = np.polyfit(mkt, q1, 1)
    resid = q1 - (a + b * mkt)
    print(f"Q1 margin = {a:.2f} + {b:.3f} x market margin | r={np.corrcoef(mkt, q1)[0, 1]:.3f} | resid SD {resid.std():.2f}")
    print(f"Q1 tie rate {np.mean(q1 == 0):.3f} | scoreless {np.mean(hist[:, 2] + hist[:, 3] == 0):.3f}")

    # Team tendency = Q1 residual (beyond the spread) from that team's perspective.
    team_games = collections.defaultdict(list)
    for (y, _, _, _, _, wk, home, away), e in sorted(zip(rows, resid), key=lambda x: (x[0][0], x[0][5])):
        team_games[(y, home)].append((wk, e))
        team_games[(y, away)].append((wk, -e))
    season_mean = {k: np.mean([e for _, e in g]) for k, g in team_games.items()}

    def corr_test(tendency):
        xs, ys = [], []
        for (y, _, _, _, _, wk, home, away), e in zip(rows, resid):
            th, ta = tendency(y, wk, home), tendency(y, wk, away)
            if th is not None and ta is not None:
                xs.append(th - ta)
                ys.append(e)
        return np.corrcoef(xs, ys)[0, 1], len(xs)

    r, n = corr_test(lambda y, wk, t: season_mean.get((y - 1, t)))
    print(f"\nTeam start tendency -> next Q1 residual:\n  prior season: r={r:.3f} (n={n})")
    for min_games in (3, 5):
        def rolling(y, wk, t):
            prev = [e for w, e in team_games[(y, t)] if w < wk]
            return np.mean(prev) if len(prev) >= min_games else None
        r, n = corr_test(rolling)
        print(f"  in-season rolling (>= {min_games} games): r={r:.3f} (n={n})")
    halves = [(np.mean([e for _, e in g[0::2]]), np.mean([e for _, e in g[1::2]]))
              for g in team_games.values() if len(g) >= 10]
    print(f"  within-season split-half: r={np.corrcoef(*zip(*halves))[0, 1]:.3f} ({len(halves)} team-seasons)")

    print("\nLeave-one-season-out log loss (3-way: home lead / tie / away lead):")
    for sbw, tbw in ((2, None), (3, None), (4, None), (6, None), (3, 6), (4, 8), (6, 12)):
        ll = []
        for y in HIST_YEARS:
            train = hist[years != y]
            for (hm, tot, hq, aq) in hist[years == y]:
                m, _, w = q1_distribution(hm, tot, train, sbw, tbw)
                actual = np.sign(hq - aq)
                ll.append(-np.log(max((w * (np.sign(m) == actual)).sum(), 1e-6)))
        label = f"spread bw {sbw:g}" + ("" if tbw is None else f", total bw {tbw:g}")
        print(f"  {label:>28}: {np.mean(ll):.4f}")

    print(f"\nCalibration, P(favorite leads after Q1), spread bw {SPREAD_BW:g}:")
    cal = np.zeros((10, 3))
    for y in HIST_YEARS:
        train = hist[years != y]
        for (hm, tot, hq, aq) in hist[years == y]:
            m, _, w = q1_distribution(hm, tot, train)
            fav_m = m if hm >= 0 else -m
            p = (w * (fav_m > 0)).sum()
            won = (hq - aq) * (1 if hm >= 0 else -1) > 0
            cal[min(9, int(p * 10))] += (1, p, won)
    for i, (n, ps, ws) in enumerate(cal):
        if n >= 20:
            print(f"  {i / 10:.1f}-{(i + 1) / 10:.1f}: n={int(n):4d} pred {ps / n:.3f} actual {ws / n:.3f}")


if __name__ == "__main__":
    main()
