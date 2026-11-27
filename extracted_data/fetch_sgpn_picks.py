"""
Pull the Sports Gambling Podcast Network (SGPN) college football expert ATS picks.

SGPN's own site (sportsgamblingpodcast.com/college-football-picks/) sits behind
Cloudflare and refuses scripts. The picks grid on that page is an embedded
Tallysight widget, and tallysight.com serves the same widget (data included as
Next.js __NEXT_DATA__) to a plain request. Each past week is reachable by
swapping in an `event:<season>-week-<n>` path segment.

Output: sgpn_picks_{year}.csv, one row per analyst spread pick:
    week, game_date, away, home, analyst, side (home/away), picked_team,
    line (picked team's spread), odds, book, pick_time, correct (1/0/blank)

Usage:
    python fetch_sgpn_picks.py --year 2026              # first run: every week; after that: latest 2 weeks
    python fetch_sgpn_picks.py --year 2026 --all        # re-pull every week
    python fetch_sgpn_picks.py --year 2026 --weeks 13   # refresh only these weeks

Re-running merges: rows for the fetched weeks are replaced and other weeks are kept.
"""
import argparse
import json
import os
import re
import time
import urllib.request

import pandas as pd

ORG = "sports-gambling-podcast-network"
# The analyst id list from SGPN's embed. The widget shows whoever on this list
# made picks that week.
ANALYSTS = "5455,6b3f,dabd,16ff,78a0,4eca,21c4,4922,94c2,7011"
URL = ("https://tallysight.com/new/widget/staff-picks/" + ORG + "/cfb/default:ats/types:ml,ats/"
       "{event}/extras:condensed,showodds,customOrder/analysts:" + ANALYSTS)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36"
COLS = ["week", "game_date", "away", "home", "analyst", "side", "picked_team", "line", "odds",
        "book", "pick_time", "correct"]


def page_props(event_segment):
    req = urllib.request.Request(URL.format(event=event_segment), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        html = r.read().decode("utf-8")
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise RuntimeError(f"no __NEXT_DATA__ for {event_segment}")
    return json.loads(m.group(1))["props"]["pageProps"]


def school(team):
    return team.get("market") or team["name"]


def week_rows(pp, week):
    rows = []
    for p in pp.get("picks", []):
        if p["market"]["type"] != "SpreadMarket":
            continue
        t = p["topic"]
        home, away = t.get("home"), t.get("away")
        if not home or not away:
            continue
        ent = p["pickedOutcome"]["entity"]["_id"]
        side = "home" if ent == home["_id"] else "away" if ent == away["_id"] else None
        if side is None:
            continue
        sb = p["pickedOutcome"].get("sportsbook") or {}
        rows.append({
            "week": week,
            "game_date": (t.get("startTime") or "")[:10],
            "away": school(away), "home": school(home),
            "analyst": p["analyst"]["name"],
            "side": side,
            "picked_team": school(home if side == "home" else away),
            "line": sb.get("line"), "odds": sb.get("odds"),
            "book": (sb.get("sportsbook") or {}).get("name"),
            "pick_time": p.get("pickDate"),
            "correct": {True: 1, False: 0}.get(p.get("correct")),
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--weeks", type=int, nargs="*", help="only these weeks")
    ap.add_argument("--all", action="store_true", help="re-pull every listed week")
    args = ap.parse_args()
    season = f"{args.year}-{str(args.year + 1)[-2:]}"

    # The default (autopilot) view lists every event of the season.
    pp = page_props("cfb/autopilot:games")
    listed = sorted({int(m.group(1)) for e in pp.get("allEvents", [])
                     if (m := re.fullmatch(rf"{season}-week-(\d+)", e.get("slug", "")))})
    out = f"sgpn_picks_{args.year}.csv"
    # Scheduled runs: once the file exists, refresh only the latest two weeks
    # (current picks plus last week's grading). --all forces a full re-pull.
    weeks = args.weeks or (listed[-2:] if os.path.exists(out) and not args.all else listed)
    print(f"SGPN/Tallysight weeks listed: {listed}; fetching {weeks}")

    rows = []
    for w in weeks:
        wpp = page_props(f"event:{season}-week-{w}")
        r = week_rows(wpp, w)
        print(f"  week {w}: {len(r)} spread picks, {len({(x['away'], x['home']) for x in r})} games, "
              f"analysts: {', '.join(sorted({x['analyst'] for x in r}))}")
        rows.extend(r)
        time.sleep(1)

    new = pd.DataFrame(rows, columns=COLS)
    if os.path.exists(out) and set(weeks) != set(listed):
        old = pd.read_csv(out)
        new = pd.concat([old[~old.week.isin(weeks)], new], ignore_index=True)
    new = new.sort_values(["week", "game_date", "home", "analyst"])
    new.to_csv(out, index=False)
    print(f"wrote {out}: {len(new)} picks")


if __name__ == "__main__":
    main()
