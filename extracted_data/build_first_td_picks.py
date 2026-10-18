"""
First-TD-scorer prop picks for a week's slate, built on top of that week's
model projections (week{N}_{year}_projections.csv from
build_week_projections.py).

Per game, for each side:
  p_team_first = 0.5 + (team win prob - 0.5) * FIRST_TD_FLATTEN
      -- the first TD is far noisier than the final result, so the model's
         win probability is pulled toward a coin flip.
  share        = player's rushing + receiving TDs / team's rushing +
                 receiving TDs, season to date (CFBD /stats/player/season).
  p_first_td   = p_team_first * share * OFFENSE_SHARE
      -- OFFENSE_SHARE leaves ~8% for defensive/special-teams/other TDs.
Top TOP_N players per team are listed; the single highest p_first_td in
each game is flagged pick=True.

NOT backtested -- FIRST_TD_FLATTEN and OFFENSE_SHARE are priors, not fitted.
Started 2026-10-17 (week 7) as a one-off; grade_first_td_picks.py tracks
the live record so the method can be judged on a real sample before stakes
go up. Known blind spots: injuries/inactives, goal-line roles, and QB
passing TDs (only a QB's rushing TDs count toward his share).

Re-runs are safe and intended (the scheduled task calls this every 6
hours): rows for games that have already kicked off are kept exactly as
first written, so a pick can never be revised after the fact; only
not-yet-started games are rebuilt with the latest stats/projections.

Usage:
    python build_first_td_picks.py --year 2026            # auto-detect the upcoming week
    python build_first_td_picks.py --year 2026 --week 8
"""
import argparse
import collections
import datetime
import os

import pandas as pd

from cfbd_fetch import cfbd_get, get_current_week

FIRST_TD_FLATTEN = 0.55
OFFENSE_SHARE = 0.92
TOP_N = 3


def season_td_counts(year):
    td = collections.defaultdict(float)  # (team, player) -> rush+rec TDs
    for cat in ("rushing", "receiving"):
        for s in cfbd_get("/stats/player/season", params={"year": year, "category": cat}):
            if s["statType"] == "TD":
                td[(s["team"], s["player"])] += float(s["stat"])
    return td


def build_rows(proj, starts, td, built_at):
    team_tot = collections.defaultdict(float)
    for (t, _), v in td.items():
        team_tot[t] += v

    rows = []
    for _, r in proj.iterrows():
        ph = 0.5 + (r["home_win_prob"] - 0.5) * FIRST_TD_FLATTEN
        game_rows = []
        for team, pt in ((r["home"], ph), (r["away"], 1 - ph)):
            tot = team_tot.get(team, 0)
            if tot == 0:
                continue
            players = sorted(((p, v) for (t, p), v in td.items() if t == team), key=lambda x: -x[1])[:TOP_N]
            for p, v in players:
                prob = pt * OFFENSE_SHARE * v / tot
                game_rows.append({
                    "game_id": r["game_id"], "start_utc": starts.get(r["game_id"], ""),
                    "game": f"{r['away']} @ {r['home']}", "team": team, "player": p,
                    "tds": int(v), "team_tds": int(tot), "share": round(v / tot, 3),
                    "p_team_first": round(pt, 3), "p_first_td": round(prob, 4),
                    "fair_odds": f"+{round(100 * (1 - prob) / prob)}", "pick": False,
                    "built_at": built_at,
                })
        if game_rows:
            max(game_rows, key=lambda x: x["p_first_td"])["pick"] = True
            rows += game_rows
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--week", type=int, default=None, help="If omitted, auto-detect the upcoming week via CFBD's calendar")
    args = ap.parse_args()

    year, week = args.year, args.week
    if week is None:
        week = get_current_week(year)
        if week is None:
            raise SystemExit(f"Could not determine the current week for {year} -- pass --week explicitly.")
        print(f"Auto-detected current week: {week}")

    proj_path = f"week{week}_{year}_projections.csv"
    if not os.path.exists(proj_path):
        # Normal state early in the week -- projections are built first.
        print(f"{proj_path} not built yet -- no first-TD picks for week {week} until it is.")
        return
    out_path = f"first_td_picks_week{week}_{year}.csv"

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M")
    games = cfbd_get("/games", params={"year": year, "week": week, "seasonType": "regular"})
    starts = {g["id"]: g["startDate"][:16] for g in games}

    locked = pd.DataFrame()
    if os.path.exists(out_path):
        prev = pd.read_csv(out_path)
        locked = prev[prev["start_utc"] <= now]

    proj = pd.read_csv(proj_path)
    proj = proj[~proj["game_id"].isin(locked["game_id"] if len(locked) else [])]
    proj = proj[proj["game_id"].map(lambda g: starts.get(g, "") > now)]

    new = pd.DataFrame(build_rows(proj, starts, season_td_counts(year), now))
    df = pd.concat([locked, new], ignore_index=True).sort_values(["start_utc", "game", "p_first_td"], ascending=[True, True, False])
    df.to_csv(out_path, index=False)

    picks = df[df["pick"]]
    print(f"Week {week}: {len(picks)} games ({len(locked['game_id'].unique()) if len(locked) else 0} locked, "
          f"{new['game_id'].nunique() if len(new) else 0} rebuilt) -> {out_path}")
    pd.set_option("display.width", 200)
    print(picks[["start_utc", "game", "player", "team", "tds", "team_tds", "p_first_td", "fair_odds"]].to_string(index=False))


if __name__ == "__main__":
    main()
