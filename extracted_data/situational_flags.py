"""
Situational "conflict" angles used to mark an ATS pick SKIP (2026-11-03 analysis,
see ats_tiers_README.md). Both angles were the only situational spots that held up
out of sample (2022-25) in the exhaustive spot search; they are used only to SKIP
a pick that runs into them, never to create a pick on their own.

  - letdown:          team's previous game was a win as the market underdog, and
                      this game is P4 vs P4. Team covers ~43% (2022-25, n=279).
  - losing home fav:  team is at home (non-neutral), favoured, with a losing
                      record entering the game. Team covers ~43% (2022-25, n=364).

Built from the *_final.json game/line files that team_records.compute_team_records
already saves for weeks 1..through_week, so calling it after that costs no CFBD calls.
"""
import json
import os

P4 = {"ACC", "Big Ten", "Big 12", "SEC", "Pac-12"}


def _median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else None


def team_situations(year, through_week):
    """{cfbd_team: {"w","l","last_won_as_dog","conf"}} from games in weeks 1..through_week."""
    log = {}
    for wk in range(1, through_week + 1):
        gp, lp = f"cfbd_raw/games_{year}_wk{wk}_final.json", f"cfbd_raw/lines_{year}_wk{wk}_final.json"
        if not os.path.exists(gp):
            continue
        games = json.load(open(gp, encoding="utf-8"))
        lines = json.load(open(lp, encoding="utf-8")) if os.path.exists(lp) else []
        spread = {l["id"]: _median([x["spread"] for x in l.get("lines", []) if x.get("spread") is not None]) for l in lines}
        for g in games:
            hp, ap = g.get("homePoints"), g.get("awayPoints")
            if g.get("week") != wk or not g.get("completed") or hp is None or ap is None:
                continue
            s = spread.get(g["id"])  # home perspective, negative = home favoured
            for side, pf, pa, dog in (("home", hp, ap, s is not None and s > 0),
                                      ("away", ap, hp, s is not None and s < 0)):
                t = log.setdefault(g[f"{side}Team"], {"games": []})
                t["games"].append((g["startDate"], pf > pa, pf < pa, dog, g.get(f"{side}Conference")))
    out = {}
    for team, t in log.items():
        gs = sorted(t["games"])
        last = gs[-1]
        out[team] = {"w": sum(x[1] for x in gs), "l": sum(x[2] for x in gs),
                     "last_won_as_dog": bool(last[1] and last[3]), "conf": last[4]}
    return out


def conflict_reasons(side, opp, side_is_home, neutral, side_is_fav, sit, side_conf=None, opp_conf=None):
    """List of situational reasons that run against backing `side` ATS."""
    s, o = sit.get(side, {}), sit.get(opp, {})
    sc = side_conf or s.get("conf")
    oc = opp_conf or o.get("conf")
    reasons = []
    if s.get("last_won_as_dog") and sc in P4 and oc in P4:
        reasons.append("letdown after upset win")
    if side_is_home and not neutral and side_is_fav and s and s["l"] > s["w"]:
        reasons.append("losing-record home favourite")
    return reasons
