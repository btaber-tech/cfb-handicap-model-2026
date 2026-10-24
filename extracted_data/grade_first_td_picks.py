"""
Grades every first_td_picks_week{N}_{year}.csv on disk (from
build_first_td_picks.py) against CFBD play-by-play: finds each game's first
scoring touchdown, parses the scorer out of the play text, and marks every
listed candidate hit/miss.

The scorer is the last "#NN F.Lastname" before "TOUCHDOWN" in the play
text -- the rusher on a run, the receiver on a pass, the returner on a
fumble/interception/kick return. Candidates match on last name + first
initial (suffixes like Jr./III ignored).

Output: first_td_scorecard_{year}.csv (all graded candidate rows, all
weeks, overwritten each run like season_scorecard_2026.csv) plus a summary
of the flagged picks: hits vs. model-expected hits, and units at the
model's fair odds (actual book prices aren't captured, so real P/L will be
lower by the book's margin).

Usage:
    python grade_first_td_picks.py --year 2026
"""
import argparse
import glob
import re

import pandas as pd

from cfbd_fetch import cfbd_get

SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def name_key(first_initial, last):
    return (first_initial[:1].lower(), re.sub(r"[^a-z]", "", last.lower()))


def player_key(full_name):
    parts = [p for p in full_name.replace(".", ". ").split() if p.strip(".").lower() not in SUFFIXES]
    return name_key(parts[0], parts[-1]) if parts else None


# CFBD play text comes in several formats, depending on the feed:
#   "#5 K.Lacy rush middle ...", "#3 C.Pierre Jr. rush ...", "G. Davidson run for 75 yd",
#   "Jaylen Raynor 8 Yd Run (...)", "... pass complete short right to #81 W.Rodriguez",
#   "J. Potts pass to J. West for 7 yds", "Allen Middleton 18 Yd pass from Jake Curry".
_L = r"(?:[^\W\d_]|['\-])"  # a letter (accented ones included), apostrophe or hyphen
_NAME = rf"([A-Z]{_L}*\.?(?:,?\s?[A-Z]{_L}*\.?){{0,3}})(?!\w)"
_PREFIX = re.compile(r"^\s*(?:\(\d+:\d+\)\s*)?(?:No Huddle-?\s*)?(?:Shotgun\s*)?")
_RUSH = [re.compile(r"(?:#\d+\s+)?" + _NAME + r"\s+(?:rush|run)\b"),
         re.compile(_NAME + r"\s+\d+\s+Yd\s+Run\b")]
_TARGET = [re.compile(r"\bpass(?: complete| incomplete)?\b[^#]*?\bto\s+(?:#\d+\s+)?" + _NAME),
           re.compile(_NAME + r"\s+\d+\s+Yd\s+pass from\b")]


def ball_carrier(text, kind):
    """(display name, name key) of the rusher (kind='rush') or target (kind='target'), or (None, None)."""
    text = _PREFIX.sub("", text)
    for pat in (_RUSH if kind == "rush" else _TARGET):
        m = pat.search(text)
        if m and player_key(m.group(1)):
            return m.group(1), player_key(m.group(1))
    return None, None


def scorer_from_text(text):
    before = text.split("TOUCHDOWN")[0]
    hits = re.findall(r"#\d+\s+([A-Za-z'\-]+)\.\s?([A-Za-z'\-]+)", before)
    if hits:
        first, last = hits[-1]
        return f"{first}.{last}", name_key(first, last)
    # Summary-style text with no jersey numbers: the target on a pass, else the rusher.
    for kind in ("target", "rush"):
        name, key = ball_carrier(text, kind)
        if key:
            return name, key
    return None, None


def first_tds(year, week):
    plays = cfbd_get("/plays", params={"year": year, "week": week, "seasonType": "regular"})
    plays += cfbd_get("/plays", params={"year": year, "week": week, "seasonType": "regular", "classification": "fcs"})
    by_game = {}
    for p in plays:
        if not p.get("scoring") or "TOUCHDOWN" not in p.get("playText", "").upper():
            continue
        order = (p["period"], -(p["clock"]["minutes"] * 60 + p["clock"]["seconds"]))
        if p["gameId"] not in by_game or order < by_game[p["gameId"]][0]:
            by_game[p["gameId"]] = (order, p)
    return {gid: p for gid, (_, p) in by_game.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    args = ap.parse_args()
    year = args.year

    graded = []
    for path in sorted(glob.glob(f"first_td_picks_week*_{year}.csv"), key=lambda p: int(re.search(r"week(\d+)_", p).group(1))):
        week = int(re.search(r"week(\d+)_", path).group(1))
        picks = pd.read_csv(path)
        games = {g["id"]: g for g in cfbd_get("/games", params={"year": year, "week": week, "seasonType": "regular"})}
        tds = first_tds(year, week)
        for _, r in picks.iterrows():
            g = games.get(r["game_id"])
            if not g or not g.get("completed"):
                continue  # not played yet -- skip, not an error
            play = tds.get(r["game_id"])
            scorer, key = scorer_from_text(play["playText"]) if play else ("no TD", None)
            row = r.to_dict()
            row.update(week=week, first_td_scorer=scorer, first_td_play=play["playText"][:160] if play else "",
                       hit=key is not None and key == player_key(r["player"]))
            graded.append(row)

    if not graded:
        print("No completed games with first-TD picks yet.")
        return
    df = pd.DataFrame(graded)
    df.to_csv(f"first_td_scorecard_{year}.csv", index=False)

    unparsed = df[df["first_td_scorer"].isna()]["game"].unique()
    if len(unparsed):
        print(f"WARNING: couldn't parse a scorer for: {', '.join(unparsed)} -- check first_td_play")

    picks = df[df["pick"]].copy()
    picks["odds"] = picks["fair_odds"].astype(str).str.lstrip("+").astype(float)
    picks["units"] = picks.apply(lambda r: r["odds"] / 100 if r["hit"] else -1.0, axis=1)
    summary = picks.groupby("week").agg(picks=("hit", "size"), hits=("hit", "sum"),
                                        expected=("p_first_td", "sum"), units_at_fair=("units", "sum"))
    summary.loc["total"] = summary.sum()
    print(summary.round(2).to_string())
    print("\nHits:")
    print(picks[picks["hit"]][["week", "game", "player", "fair_odds"]].to_string(index=False))


if __name__ == "__main__":
    main()
