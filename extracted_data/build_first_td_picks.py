"""
First-TD-scorer prop picks for a week's slate, built on top of that week's
model projections (week{N}_{year}_projections.csv from
build_week_projections.py).

Per game, for each side:
  p_team_first = pts^FIRST_TEAM_POWER / (home pts^FIRST_TEAM_POWER + away pts^FIRST_TEAM_POWER)
      where pts = team implied points
      -- implied points from the market spread + total when a line exists
         (projections' market_home_margin / market_total), else the
         model's own margin + total.
  share        = player's blended TD score / team's blended TD score, where
                 each player's score = XTD_WEIGHT * expected TDs + (1 -
                 XTD_WEIGHT) * actual TDs, season to date. Expected TDs come
                 from play-by-play usage: every carry and target is worth the
                 league-wide TD rate for its play type and distance to goal,
                 so red-zone and goal-line work counts for far more than
                 midfield touches. A team's last RECENT_GAMES games count
                 RECENT_WEIGHT times as much as earlier ones, and a player
                 with no carries or targets in the team's last INACTIVE_GAMES
                 games gets no share (stand-in for injuries/role changes,
                 which CFBD doesn't report).
  p_first_td   = p_team_first * share * OFFENSE_SHARE
      -- OFFENSE_SHARE leaves ~14% for defensive/special-teams/other TDs.
Top TOP_N players per team are listed; the single highest p_first_td in
each game is flagged pick=True.

Backtested walk-forward on 2025 (backtest_first_td.py, 1,281 games): top
pick hit 14.1% vs. 14.7% expected, against 11.0% hit / 16.6% expected for
the original method. OFFENSE_SHARE (0.857 of 2025 first TDs were offensive)
and FIRST_TEAM_POWER (best of 0.5-2.0) are fitted; the share settings sit
within noise of the best fit (first_td_backtest_2025.csv) and were kept. Started 2026-10-17 (week 7) as a one-off;
grade_first_td_picks.py tracks the live record. Week 7 used the original
method (win prob flattened toward 50/50, raw season TD share); week 8 games
that kicked off before 2026-10-21 also kept it, since locked rows are never
rebuilt. Known blind spot: QB passing TDs (only a QB's own carries count
toward his share, which is right for a scorer prop).

Completed weeks' play-by-play is cached in cfbd_raw/plays_{year}_wk{N}.json
so the 6-hourly re-runs don't re-download it.

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
import json
import os

import pandas as pd

from cfbd_fetch import cfbd_get, get_current_week
from grade_first_td_picks import ball_carrier, player_key

OFFENSE_SHARE = 0.86
FIRST_TEAM_POWER = 1.5
XTD_WEIGHT = 0.6
RECENT_GAMES = 3
RECENT_WEIGHT = 2.0
INACTIVE_GAMES = 2
TOP_N = 3
MIN_IMPLIED_PTS = 3.0
# Yards-to-goal buckets for the league TD-rate table (upper bounds, inclusive).
YTG_BUCKETS = (2, 5, 10, 20, 40, 100)


def week_plays(year, week, cache):
    path = os.path.join("cfbd_raw", f"plays_{year}_wk{week}.json")
    if cache and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    plays = cfbd_get("/plays", params={"year": year, "week": week, "seasonType": "regular"})
    plays += cfbd_get("/plays", params={"year": year, "week": week, "seasonType": "regular", "classification": "fcs"})
    # The FCS call also returns FBS-vs-FCS games, so those plays arrive twice.
    plays = list({p["id"]: p for p in plays}.values())
    if cache:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(plays, f)
    return plays


def opportunity_rows(plays, week):
    """One row per carry or target: team, player key, kind, yards to goal, TD, game."""
    rows = []
    for p in plays:
        text, ptype = p.get("playText") or "", p.get("playType")
        if ptype in ("Rush", "Rushing Touchdown"):
            kind = "rush"
        elif ptype in ("Pass Reception", "Pass Incompletion", "Passing Touchdown"):
            kind = "target"
        else:
            continue
        _, key = ball_carrier(text, kind)
        if not key or not p.get("yardsToGoal"):
            continue
        rows.append({"team": p["offense"], "key": key, "kind": kind,
                     "ytg": p["yardsToGoal"], "td": ptype.endswith("Touchdown"),
                     "game_id": p["gameId"], "week": week})
    return rows


def opportunities(year, week):
    """Every carry and target in weeks before `week`."""
    rows = []
    for w in range(0, week):
        # Last week can still be filling in (late Saturday games, stat corrections), so only older weeks are cached.
        rows += opportunity_rows(week_plays(year, w, cache=w < week - 1), w)
    df = pd.DataFrame(rows)
    df["bucket"] = pd.cut(df["ytg"], [0, *YTG_BUCKETS], labels=False)
    return df


def score_table(opp, xtd_weight=XTD_WEIGHT, recent_weight=RECENT_WEIGHT,
                recent_games=RECENT_GAMES, inactive_games=INACTIVE_GAMES):
    """Per (team, key): blended TD score, raw TDs, carries+targets inside the 10. Keyword args are for the backtest."""
    rate = opp.groupby(["kind", "bucket"])["td"].mean()
    opp = opp.assign(xtd=[rate[(k, b)] for k, b in zip(opp["kind"], opp["bucket"])])

    # Recency: rank each team's games newest-first.
    order = opp[["team", "game_id", "week"]].drop_duplicates().sort_values("week", ascending=False)
    order["recent_rank"] = order.groupby("team").cumcount()
    opp = opp.merge(order[["team", "game_id", "recent_rank"]], on=["team", "game_id"])
    opp["w"] = (opp["recent_rank"] < recent_games).map({True: recent_weight, False: 1.0})
    opp["wx"], opp["wtd"] = opp["w"] * opp["xtd"], opp["w"] * opp["td"]

    agg = opp.groupby(["team", "key"]).agg(xtd=("wx", "sum"), wtd=("wtd", "sum"), tds=("td", "sum"),
                                           rz=("ytg", lambda s: int((s <= 10).sum())),
                                           last_seen=("recent_rank", "min")).reset_index()
    if inactive_games:
        agg = agg[agg["last_seen"] < inactive_games]
    agg["score"] = xtd_weight * agg["xtd"] + (1 - xtd_weight) * agg["wtd"]
    return agg


def player_scores(year, week):
    """(team, full name) -> {score, tds, rz} from recency-weighted usage + TDs."""
    agg = score_table(opportunities(year, week))

    # Play-by-play only gives "F.Lastname"; map back to the full names CFBD's season stats use.
    full = collections.defaultdict(dict)  # (team, key) -> full name -> touches
    for cat, stat in (("rushing", "CAR"), ("receiving", "REC")):
        for s in cfbd_get("/stats/player/season", params={"year": year, "category": cat}):
            if s["statType"] == stat:
                names = full[(s["team"], player_key(s["player"]))]
                names[s["player"]] = names.get(s["player"], 0) + float(s["stat"])
    out = {}
    for r in agg.itertuples():
        names = full.get((r.team, r.key))
        if names:
            out[(r.team, max(names, key=names.get))] = {"score": r.score, "tds": int(r.tds), "rz": r.rz}
    return out


def positions(year):
    """(team, name key) -> roster position; skill positions win when two players share a key."""
    skill = {"QB", "RB", "WR", "TE", "FB"}
    out = {}
    for r in cfbd_get("/roster", params={"year": year}):
        key = player_key(f"{r.get('firstName') or ''} {r.get('lastName') or ''}")
        pos = r.get("position")
        if key and pos and ((r["team"], key) not in out or pos in skill):
            out[(r["team"], key)] = pos
    return out


def implied_points(r):
    """(home, away) implied points: market spread/total when posted, else the model's."""
    if pd.notna(r.get("market_home_margin")) and pd.notna(r.get("market_total")):
        margin, total = r["market_home_margin"], r["market_total"]
    else:
        # model_margin is from model_pick's side, not the home side.
        margin = r["model_margin"] if r["model_pick"] == r["home"] else -r["model_margin"]
        total = r["model_total"]
    return max((total + margin) / 2, MIN_IMPLIED_PTS), max((total - margin) / 2, MIN_IMPLIED_PTS)


def build_rows(proj, starts, scores, built_at):
    by_team = collections.defaultdict(list)
    for (t, p), v in scores.items():
        by_team[t].append((p, v))
    team_tot = {t: sum(v["score"] for _, v in ps) for t, ps in by_team.items()}
    team_tds = {t: sum(v["tds"] for _, v in ps) for t, ps in by_team.items()}

    rows = []
    for _, r in proj.iterrows():
        hp, ap = implied_points(r)
        ph = hp ** FIRST_TEAM_POWER / (hp ** FIRST_TEAM_POWER + ap ** FIRST_TEAM_POWER)
        game_rows = []
        for team, pt in ((r["home"], ph), (r["away"], 1 - ph)):
            tot = team_tot.get(team, 0)
            if tot == 0:
                continue
            players = sorted(by_team[team], key=lambda x: -x[1]["score"])[:TOP_N]
            for p, v in players:
                share = v["score"] / tot
                prob = pt * OFFENSE_SHARE * share
                game_rows.append({
                    "game_id": r["game_id"], "start_utc": starts.get(r["game_id"], ""),
                    "game": f"{r['away']} @ {r['home']}", "team": team, "player": p,
                    "tds": v["tds"], "team_tds": team_tds[team], "share": round(share, 3),
                    "p_team_first": round(pt, 3), "p_first_td": round(prob, 4),
                    "fair_odds": f"+{round(100 * (1 - prob) / prob)}", "pick": False,
                    "built_at": built_at, "rz_opps": v["rz"],
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

    new = pd.DataFrame(build_rows(proj, starts, player_scores(year, week), now))
    df = pd.concat([locked, new], ignore_index=True)
    # Locked rows read back from CSV lose the "+" (pandas parses "+302" as 302).
    df["fair_odds"] = "+" + df["fair_odds"].astype(str).str.lstrip("+")
    # Display-only, so filled in for locked rows too (doesn't touch their picks).
    pos = positions(year)
    df["pos"] = [pos.get((t, player_key(p)), "") for t, p in zip(df["team"], df["player"])]
    df = df.sort_values(["start_utc", "game", "p_first_td"], ascending=[True, True, False])
    df.to_csv(out_path, index=False)

    picks = df[df["pick"]]
    print(f"Week {week}: {len(picks)} games ({len(locked['game_id'].unique()) if len(locked) else 0} locked, "
          f"{new['game_id'].nunique() if len(new) else 0} rebuilt) -> {out_path}")
    pd.set_option("display.width", 200)
    print(picks[["start_utc", "game", "player", "team", "tds", "team_tds", "p_first_td", "fair_odds"]].to_string(index=False))


if __name__ == "__main__":
    main()
