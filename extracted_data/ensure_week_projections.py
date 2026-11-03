"""
Build the upcoming week's projections locally, once, as soon as the SP+
weekly tab is posted. Run by the 6h local task (capture_line_snapshots.ps1).

Why: the Monday cloud routine builds and publishes the week but can't push
to GitHub, so without this the repo (and the scorecard) only got a week's
projections when someone ran the chain by hand. With this, the committed
week{N}_2026_projections.csv is the record of picks that the scorecard grades,
and the Friday market-refresh routine rebuilds the page from it.

Never overwrites an existing week file (that would regrade picks against a
moved line). Uses the week already recorded in line_snapshots_{year}.csv,
so it costs no extra CFBD call until there's work to do.

Usage:
    python ensure_week_projections.py --year 2026
"""
import argparse
import os
import subprocess
import sys

import pandas as pd


def run(cmd):
    print("$", " ".join(cmd))
    r = subprocess.run([sys.executable] + cmd, capture_output=True, text=True)
    print(r.stdout[-2000:])
    if r.returncode:
        print(r.stderr[-2000:])
    return r.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    args = ap.parse_args()
    y = args.year

    snaps = pd.read_csv(f"line_snapshots_{y}.csv", usecols=["year", "week", "snapshot_time_utc"])
    snaps = snaps[snaps["year"] == y]
    if snaps.empty:
        print("no line snapshots yet -- nothing to do")
        return
    week = int(snaps.sort_values("snapshot_time_utc").iloc[-1]["week"])
    out = f"week{week}_{y}_projections.csv"
    if os.path.exists(out):
        print(f"{out} already exists -- nothing to do")
        return

    if run(["fetch_spplus_picks.py", "--year", str(y)]):
        print("SP+ fetch failed -- will retry next run")
        return
    sp = pd.read_csv(f"spplus_picks_{y}.csv")
    if not (sp["week"] == week).any():
        print(f"SP+ week {week} tab not posted yet -- will retry next run (not building on the fallback formula)")
        return

    if week > 1 and run(["build_in_season_ratings.py", "--year", str(y), "--through-week", str(week - 1)]):
        print("in-season ratings failed -- will retry next run")
        return
    rc = run(["build_week_projections.py", "--year", str(y), "--week", str(week)])
    print("built" if rc == 0 and os.path.exists(out) else "build failed -- will retry next run")


if __name__ == "__main__":
    main()
