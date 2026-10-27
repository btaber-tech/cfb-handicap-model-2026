"""Build first-td-week{N}.html from the picks CSV + tpl.html. Usage: py -3.14 make_first_td_page.py 9"""
import json, os, sys
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = HERE
week = int(sys.argv[1])
d = pd.read_csv(os.path.join(DATA_DIR, f"first_td_picks_week{week}_2026.csv"), keep_default_na=False)
games = []
for gid, g in d.groupby("game_id", sort=False):
    g = g.sort_values("p_first_td", ascending=False)
    away, home = g.game.iloc[0].split(" @ ")
    pt = {r.team: r.p_team_first for r in g.itertuples()}
    games.append(dict(id=int(gid), t=g.start_utc.iloc[0] + "Z", away=away, home=home,
        pa=round(pt.get(away, 1 - pt.get(home, 0.5)), 3), old=bool(g.built_at.iloc[0] < "2026-10-21"),
        p=[dict(n=r.player, tm=r.team, pos=r.pos, td=int(r.tds), sh=r.share, pf=r.p_first_td, k=r.pick in (True, "True"),
                rz=None if r.rz_opps == "" else int(float(r.rz_opps))) for r in g.itertuples()]))
games.sort(key=lambda x: x["t"])
s = pd.read_csv(os.path.join(DATA_DIR, "first_td_scorecard_2026.csv"))
pk = s[s.pick]
data = json.dumps(dict(games=games, rec=dict(w=int(pk.hit.sum()), n=len(pk)), built=d.built_at.max()))
t = open(os.path.join(HERE, "first_td_page_tpl.html"), encoding="utf-8").read().replace("Week 8", f"Week {week}")
open(os.path.join(HERE, f"first_td_week{week}_2026.html"), "w", encoding="utf-8").write(t.replace("__DATA__", data))
print("ok", len(games))
