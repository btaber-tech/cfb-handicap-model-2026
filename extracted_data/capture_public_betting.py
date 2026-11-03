"""
Capture public betting splits (ticket % and money %) for FBS games, for
reverse-line-movement (RLM) tracking.

Source: Action Network's public scoreboard JSON (no login, no key):
  https://api.actionnetwork.com/web/v2/scoreboard/ncaaf?bookIds=15,30&periods=event
  book 15 = consensus line + bet splits, book 30 = opening line.
Splits only appear once a game has enough tickets (usually mid-week on),
so early-week snapshots have blank %s -- that's normal.

Appends one row per FBS game per run to public_betting_{year}.csv. Runs in
the 6h local task (capture_line_snapshots.ps1). market_signals.py turns the
snapshots into RLM flags; build_scorecard.py and build_artifact.py read those.

Usage:
    python capture_public_betting.py --year 2026
"""
import argparse
import csv
import json
import os
import subprocess
from datetime import datetime, timezone

import requests

URL = "https://api.actionnetwork.com/web/v2/scoreboard/ncaaf"
FIELDS = ["snapshot_time_utc", "year", "an_week", "an_game_id", "status", "start_time",
          "home_an", "away_an", "home_spread_open", "home_spread", "home_tickets_pct",
          "home_money_pct", "num_bets"]


def spread_side(markets, book, side):
    for o in markets.get(book, {}).get("event", {}).get("spread", []) or []:
        if o.get("side") == side:
            return o
    return None


def fetch():
    params = {"bookIds": "15,30", "periods": "event", "division": "FBS"}
    try:
        r = requests.get(URL, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.SSLError:
        # Windows Python's revocation check fails on some certs (see cfbd_fetch.py); curl works.
        q = "&".join(f"{k}={v}" for k, v in params.items())
        out = subprocess.run(["curl", "-s", "--ssl-no-revoke", "--compressed", "-A", "Mozilla/5.0",
                              f"{URL}?{q}"], capture_output=True, check=True, timeout=60)
        return json.loads(out.stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    args = ap.parse_args()

    games = fetch().get("games", [])
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    rows = []
    for g in games:
        if g.get("season") != args.year:
            continue
        teams = {t["id"]: t for t in g.get("teams", [])}
        home, away = teams.get(g.get("home_team_id")), teams.get(g.get("away_team_id"))
        if not home or not away:
            continue
        if "FBS" not in (home.get("division_type"), away.get("division_type")):
            continue
        cons = spread_side(g.get("markets", {}), "15", "home")
        opn = spread_side(g.get("markets", {}), "30", "home")
        bi = (cons or {}).get("bet_info") or {}
        tix = (bi.get("tickets") or {}).get("percent")
        money = (bi.get("money") or {}).get("percent")
        rows.append({
            "snapshot_time_utc": now, "year": args.year, "an_week": g.get("week"),
            "an_game_id": g.get("id"), "status": g.get("status"), "start_time": g.get("start_time"),
            "home_an": home.get("location") or home.get("full_name"),
            "away_an": away.get("location") or away.get("full_name"),
            "home_spread_open": opn.get("value") if opn else None,
            "home_spread": cons.get("value") if cons else None,
            # 0/0 means "no splits yet", not a real 0% -- store blank
            "home_tickets_pct": tix if tix else None,
            "home_money_pct": money if money else None,
            "num_bets": g.get("num_bets"),
        })

    out = f"public_betting_{args.year}.csv"
    new = not os.path.exists(out)
    with open(out, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerows(rows)
    with_splits = sum(1 for x in rows if x["home_tickets_pct"])
    print(f"{len(rows)} FBS games captured ({with_splits} with bet splits) -> {out}")


if __name__ == "__main__":
    main()
