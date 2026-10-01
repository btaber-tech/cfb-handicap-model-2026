"""
Season-to-date team records for the weekly projections page: straight-up
W-L and ATS W-L(-P), from every completed regular-season game in weeks
1..through_week (inclusive). CFBD files "week 0" games under week 1, and
a week=0 query is ignored and returns the whole season -- so start at 1.

  - W-L counts every completed game, including vs. FCS/non-FBS opponents.
  - ATS counts only games CFBD has a line for, graded against the median
    spread across the books CFBD reports (same median convention as
    build_week_projections.py). After kickoff CFBD's `spread` field is the
    closing number, so this is effectively ATS vs. the close -- it will not
    always match the number captured at projection time in the scorecard.

Records are keyed by CFBD team name (the names in the games JSON), so
callers look them up with g["homeTeam"] / g["awayTeam"] directly.

Usage (standalone check):
    python team_records.py --year 2026 --through-week 4
"""
import argparse
import json
import os

from cfbd_fetch import cfbd_get_save


def _load_or_fetch(endpoint, path, params, fetch):
    if fetch or not os.path.exists(path):
        return cfbd_get_save(endpoint, path, params=params)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def compute_team_records(year, through_week, fetch=True):
    """Returns {cfbd_team_name: {"w","l","ats_w","ats_l","ats_p"}}."""
    rec = {}

    def team(name):
        return rec.setdefault(name, {"w": 0, "l": 0, "ats_w": 0, "ats_l": 0, "ats_p": 0})

    for wk in range(1, through_week + 1):
        params = {"year": year, "week": wk, "seasonType": "regular"}
        # Separate *_final.json files: the plain games/lines_{year}_wk{N}.json
        # files are the pre-kickoff snapshots build_week_projections.py pulled
        # (the market number at projection time) -- don't overwrite them.
        games = _load_or_fetch("/games", f"cfbd_raw/games_{year}_wk{wk}_final.json", params, fetch)
        lines = _load_or_fetch("/lines", f"cfbd_raw/lines_{year}_wk{wk}_final.json", params, fetch)

        spread_by_id = {}
        for l in lines:
            spreads = sorted(x["spread"] for x in l.get("lines", []) if x.get("spread") is not None)
            if spreads:
                spread_by_id[l["id"]] = spreads[len(spreads) // 2]

        for g in games:
            hp, ap = g.get("homePoints"), g.get("awayPoints")
            if g.get("week") != wk or not g.get("completed") or hp is None or ap is None:
                continue
            home, away = team(g["homeTeam"]), team(g["awayTeam"])
            if hp > ap:
                home["w"] += 1; away["l"] += 1
            elif ap > hp:
                away["w"] += 1; home["l"] += 1

            spread = spread_by_id.get(g["id"])  # home-team perspective, negative = home favored
            if spread is None:
                continue
            ats_margin = (hp - ap) + spread  # >0 home covered, <0 away covered
            if ats_margin > 0:
                home["ats_w"] += 1; away["ats_l"] += 1
            elif ats_margin < 0:
                away["ats_w"] += 1; home["ats_l"] += 1
            else:
                home["ats_p"] += 1; away["ats_p"] += 1
    return rec


def fmt_wl(r):
    return f"{r['w']}-{r['l']}" if r else "0-0"


def fmt_ats(r):
    if not r:
        return "0-0"
    s = f"{r['ats_w']}-{r['ats_l']}"
    return s + f"-{r['ats_p']}" if r["ats_p"] else s


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--through-week", type=int, required=True)
    ap.add_argument("--skip-fetch", action="store_true")
    args = ap.parse_args()
    recs = compute_team_records(args.year, args.through_week, fetch=not args.skip_fetch)
    for name in sorted(recs):
        print(f"{name:28s} {fmt_wl(recs[name]):>6s}  ATS {fmt_ats(recs[name])}")
