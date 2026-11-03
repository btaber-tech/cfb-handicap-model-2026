"""
Pull Bill Connelly's public SP+ weekly picks sheet (FBS tabs) into spplus_picks_2026.csv.

Sheet: https://docs.google.com/spreadsheets/d/1vwoVl-Dxy0es87Z9I1RTvFzr72Lb1fAkREfbLxbK-eg
Tabs are discovered from the sheet's htmlview ("FBS Week N"), each exported as CSV.
Sheet Week 0 and Week 1 both map to CFBD week 1. Team names are aliased to CFBD spelling.

Usage:
    py -3.14 fetch_spplus_picks.py                      # 2026 sheet
    py -3.14 fetch_spplus_picks.py --year 2025          # 2025 sheet (regular season FBS Week 0-15)
"""
import argparse
import io
import re
import subprocess

import numpy as np
import pandas as pd

SHEETS = {2026: "1vwoVl-Dxy0es87Z9I1RTvFzr72Lb1fAkREfbLxbK-eg",
          2025: "1a6hboWNnPeUzx5oUEjwJwf9vw4DuAV7lTaW4Q92Zpls"}
ALIAS = {"Miami-FL": "Miami", "Miami-OH": "Miami (OH)", "Hawaii": "Hawai'i", "San Jose State": "San José State",
         "UMass": "Massachusetts", "USF": "South Florida", "UL-Lafayette": "Louisiana", "ULM": "UL Monroe", "UL-Monroe": "UL Monroe",
         "Louisiana-Monroe": "UL Monroe", "FIU": "Florida International", "FAU": "Florida Atlantic",
         "Appalachian State": "App State", "Sam Houston State": "Sam Houston", "Connecticut": "UConn"}


def get(url):
    # curl: Windows Python TLS verification fails on some hosts on this machine (see cfbd_fetch.py)
    r = subprocess.run(["curl", "-sL", "--ssl-no-revoke", url], capture_output=True, check=True)
    return r.stdout.decode("utf-8")


def norm(n):
    n = str(n).strip()
    return ALIAS.get(n, n)


def num(x):
    try:
        return float(str(x).replace("%", ""))
    except ValueError:
        return np.nan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--sheet", help="override sheet id")
    a = ap.parse_args()
    SHEET = a.sheet or SHEETS[a.year]
    OUT = f"spplus_picks_{a.year}.csv"
    html = get(f"https://docs.google.com/spreadsheets/d/{SHEET}/htmlview")
    tabs = {int(w): gid for w, gid in re.findall(r'name: "FBS Week (\d+)", pageUrl: "[^"]*?gid=(\d+)', html)}
    rows = []
    for wk, gid in sorted(tabs.items()):
        raw = pd.read_csv(io.StringIO(get(f"https://docs.google.com/spreadsheets/d/{SHEET}/export?format=csv&gid={gid}")),
                          header=None, dtype=str)
        hdr = [i for i in range(min(len(raw), 10)) if {"Game", "ATS Pick"} <= set(raw.iloc[i].dropna().str.strip())]
        if not hdr:
            print(f"FBS Week {wk}: no Game/ATS Pick header found, skipped")
            continue
        d = raw.iloc[hdr[0] + 1:].copy()
        d.columns = [str(c).strip() for c in raw.iloc[hdr[0]]]
        d = d.loc[:, ~pd.Index(d.columns).duplicated()]
        d = d[d["Game"].notna() & d["ATS Pick"].notna()]
        for _, r in d.iterrows():
            m = re.match(r"(.+?) (at|vs\.) (.+)$", str(r["Game"]))
            if not m:
                continue
            rows.append(dict(
                sheet_week=wk, week=max(wk, 1), date=r["Date"], away=norm(m.group(1)), home=norm(m.group(3)),
                neutral_listed=m.group(2) == "vs.",
                sp_proj_winner=norm(r["Proj. winner"]), sp_proj_margin=num(r["Proj. margin"]),
                sp_spread=r["Spread"], sp_ats_pick=norm(r["ATS Pick"]), sp_spread_diff=num(r["Spread diff"]),
                sp_ou_line=num(r["O/U"]), sp_ou_pick=str(r["O/U pick"]).strip().lower(), sp_ou_diff=num(r["O/U diff"])))
        print(f"FBS Week {wk}: {len(d)} games")
    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False)
    print(f"wrote {OUT}: {len(out)} rows, weeks {sorted(tabs)}")


if __name__ == "__main__":
    main()
