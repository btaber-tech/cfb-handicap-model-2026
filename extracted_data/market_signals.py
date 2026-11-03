"""
Market signals per game: open/close spread, line move relative to the
model's ATS side, closing-line value (CLV), and reverse line movement (RLM).

Tracked, NOT tiered. The 2025-26 backtest found "line moved toward the model"
flips sign between seasons (cfb-backtest-findings-2026, 2026-11-03), and true
RLM has no history yet. These columns build a forward sample; revisit once a
few hundred graded games exist.

Inputs (all optional -- missing data just leaves columns blank):
  line_snapshots_{year}.csv  CFBD per-provider lines every 6h (capture_line_snapshots.py)
  cfbd_raw/lines_{year}_wk{N}_final.json / lines_{year}_wk{N}.json  fallback for open/close
  public_betting_{year}.csv  Action Network ticket/money % snapshots (capture_public_betting.py)

Conventions: spreads are HOME spreads (negative = home favoured), same as CFBD.
  line_move_model  open -> close, + = moved toward the model's side (the side got pricier)
  clv_pts          pick-time line -> close, + = we beat the close
  rlm_side         team the line moved toward while most tickets were on the other side
                   (tickets >= 55% on one side, AN open -> latest consensus moved >= 0.5 against them)
"""
import json
import os
import re

import numpy as np
import pandas as pd

RLM_TICKET_MIN = 55
RLM_MOVE_MIN = 0.5

# Action Network "location" -> CFBD team name, where they differ after normalising.
AN_ALIASES = {
    "miami fl": "miami", "miami florida": "miami", "app state": "appalachian state",
    "southern miss": "southern mississippi", "ul monroe": "louisiana monroe", "ulm": "louisiana monroe",
    "uconn": "connecticut", "umass": "massachusetts", "fiu": "florida international",
    "fau": "florida atlantic", "utsa": "ut san antonio", "ut martin": "ut martin",
    "louisiana lafayette": "louisiana", "sam houston state": "sam houston", "hawaii": "hawaii",
    "san jose st": "san jose state", "nc state": "nc state", "north carolina state": "nc state",
    "ole miss": "ole miss", "mississippi": "ole miss", "usf": "south florida",
    "texas am": "texas am", "byu": "byu", "smu": "smu", "tcu": "tcu", "ucf": "ucf", "ucla": "ucla",
    "usc": "usc", "lsu": "lsu", "utep": "utep", "unlv": "unlv",
}


def norm(name):
    s = str(name).lower().replace("&", "").replace("é", "e").replace("ʻ", "").replace("'", "")
    s = re.sub(r"[().\-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\bst$", "state", s)
    return AN_ALIASES.get(s, s)


def _median(xs):
    xs = [float(x) for x in xs if x is not None and not (isinstance(x, float) and np.isnan(x))]
    return float(np.median(xs)) if xs else None


def cfbd_open_close(year, week):
    """{game_id: (open, close)} -- last pre-kickoff 6h snapshot, else the cached CFBD lines file."""
    out = {}
    snap_path = f"line_snapshots_{year}.csv"
    if os.path.exists(snap_path):
        s = pd.read_csv(snap_path)
        s = s[(s["year"] == year) & (s["week"] == week)]
        if not s.empty:
            st = pd.to_datetime(s["snapshot_time_utc"], utc=True)
            ko = pd.to_datetime(s["start_date"], utc=True)
            s = s[st < ko].assign(_t=st[st < ko])
            for gid, g in s.groupby("game_id"):
                last = g[g["_t"] == g["_t"].max()]
                out[int(gid)] = (_median(g["spread_open"].tolist()), _median(last["spread"].tolist()))
    for fn in (f"cfbd_raw/lines_{year}_wk{week}_final.json", f"cfbd_raw/lines_{year}_wk{week}.json"):
        if not os.path.exists(fn):
            continue
        try:
            data = json.load(open(fn, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        for g in data:
            L = g.get("lines") or []
            o = _median([l.get("spreadOpen") for l in L])
            c = _median([l.get("spread") for l in L])
            prev = out.get(g["id"], (None, None))
            out[g["id"]] = (prev[0] if prev[0] is not None else o, prev[1] if prev[1] is not None else c)
    return out


def public_betting(year):
    """Latest pre-kickoff Action Network snapshot per game, keyed by (norm home, norm away, date)."""
    path = f"public_betting_{year}.csv"
    if not os.path.exists(path):
        return {}
    d = pd.read_csv(path)
    if d.empty:
        return {}
    st = pd.to_datetime(d["snapshot_time_utc"], utc=True)
    ko = pd.to_datetime(d["start_time"], utc=True)
    d = d[st < ko].assign(_t=st[st < ko], _ko=ko[st < ko])
    out = {}
    for gid, g in d.groupby("an_game_id"):
        # latest row that has splits; else latest row at all
        withs = g[g["home_tickets_pct"].notna()]
        last = (withs if not withs.empty else g).sort_values("_t").iloc[-1]
        first = g.sort_values("_t").iloc[0]
        rec = last.to_dict()
        if pd.isna(rec.get("home_spread_open")):
            rec["home_spread_open"] = first.get("home_spread")
        out[(norm(last["home_an"]), norm(last["away_an"]))] = out.get((norm(last["home_an"]), norm(last["away_an"])), [])
        out[(norm(last["home_an"]), norm(last["away_an"]))].append(rec)
    return out


def rlm_side_for(home, away, rec):
    """Team the line moved toward against the ticket majority, or None."""
    if rec is None:
        return None
    tix = rec.get("home_tickets_pct")
    o, c = rec.get("home_spread_open"), rec.get("home_spread")
    if any(pd.isna(x) for x in (tix, o, c)):
        return None
    move = c - o  # negative = home got more favoured
    if tix >= RLM_TICKET_MIN and move >= RLM_MOVE_MIN:
        return away  # public on home, line moved toward away
    if tix <= 100 - RLM_TICKET_MIN and move <= -RLM_MOVE_MIN:
        return home
    return None


def _toward(side_is_home, a, b):
    if a is None or b is None or pd.isna(a) or pd.isna(b):
        return None
    d = b - a
    return round(-d if side_is_home else d, 1)


def signals_for_week(proj, year, week):
    """DataFrame indexed like proj with market-signal columns. proj needs game_id, home, away,
    date, market_home_margin, and ats_side (or model side via model_margin)."""
    oc = cfbd_open_close(year, week)
    pb = public_betting(year)
    rows = []
    for _, r in proj.iterrows():
        home, away = r["home"], r["away"]
        side = r.get("ats_side")
        if not isinstance(side, str) or not side:
            # older projection files: model side of the number
            mhm = r.get("market_home_margin")
            if pd.notna(mhm):
                signed = r["model_margin"] if r["model_pick"] == home else -r["model_margin"]
                side = home if signed > mhm else (away if signed < mhm else None)
            else:
                side = None
        side_home = side == home if side else None
        o, c = oc.get(int(r["game_id"]), (None, None))
        pick_line = -r["market_home_margin"] if pd.notna(r.get("market_home_margin")) else None

        rec = None
        cands = pb.get((norm(home), norm(away))) or pb.get((norm(away), norm(home)))
        flipped = bool(pb.get((norm(away), norm(home)))) and not pb.get((norm(home), norm(away)))
        if cands:
            gd = pd.Timestamp(r["date"]).tz_localize("UTC")
            cands = sorted(cands, key=lambda x: abs(x["_ko"] - gd))
            if abs(cands[0]["_ko"] - gd) <= pd.Timedelta(days=2):
                rec = dict(cands[0])
                if flipped:  # AN lists neutral-site home/away the other way round
                    for k in ("home_spread_open", "home_spread"):
                        rec[k] = -rec[k] if pd.notna(rec.get(k)) else rec.get(k)
                    for k in ("home_tickets_pct", "home_money_pct"):
                        rec[k] = 100 - rec[k] if pd.notna(rec.get(k)) else rec.get(k)

        rlm = rlm_side_for(home, away, rec)
        rows.append({
            "open_home_spread": o, "close_home_spread": c,
            "line_move_model": _toward(side_home, o, c) if side else None,
            "clv_pts": _toward(side_home, pick_line, c) if side else None,
            "home_tickets_pct": rec.get("home_tickets_pct") if rec else None,
            "home_money_pct": rec.get("home_money_pct") if rec else None,
            "an_open_home_spread": rec.get("home_spread_open") if rec else None,
            "an_home_spread": rec.get("home_spread") if rec else None,
            "rlm_side": rlm,
            "rlm_with_model": (rlm == side) if (rlm and side) else None,
        })
    return pd.DataFrame(rows, index=proj.index)
