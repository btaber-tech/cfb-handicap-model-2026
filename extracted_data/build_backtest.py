"""
Build team-season tables from raw CFBD JSON (2022-2025) and run a backtest:
does year-N-end quality (SP+, advanced stats) + year-N+1 incoming indicators
(returning production, recruiting, talent) correlate with year-N+1 actual
performance (win%, ATS cover%)?

Outputs:
  cfbd_team_season.csv        - one row per team-season with all raw metrics
  cfbd_outcomes.csv           - one row per team-season with win%/ATS%
  backtest_transitions.csv    - year N -> year N+1 merged predictor/outcome table
  backtest_correlations.csv   - correlation of each predictor vs each outcome
"""
import json
import os
import pandas as pd
import numpy as np

RAW = "cfbd_raw"
YEARS = [2022, 2023, 2024, 2025]


def load(name, year):
    with open(os.path.join(RAW, f"{name}_{year}.json"), encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. Advanced stats (per team-season) -> flatten selected offense/defense fields
# ---------------------------------------------------------------------------
adv_rows = []
for y in YEARS:
    for t in load("adv_stats", y):
        off, deff = t.get("offense", {}), t.get("defense", {})
        adv_rows.append({
            "season": y, "team": t["team"], "conference": t.get("conference"),
            "off_ppa": off.get("ppa"), "off_successRate": off.get("successRate"),
            "off_explosiveness": off.get("explosiveness"),
            "off_havoc_total": (off.get("havoc") or {}).get("total"),
            "off_lineYards": off.get("lineYards"), "off_stuffRate": off.get("stuffRate"),
            "def_ppa": deff.get("ppa"), "def_successRate": deff.get("successRate"),
            "def_explosiveness": deff.get("explosiveness"),
            "def_havoc_total": (deff.get("havoc") or {}).get("total"),
            "def_lineYards": deff.get("lineYards"), "def_stuffRate": deff.get("stuffRate"),
        })
adv_df = pd.DataFrame(adv_rows)
# net efficiency = off - def (havoc/successRate/ppa all "higher offense is good,
# lower defense allowed is good" so net = off - def works directly)
adv_df["net_ppa"] = adv_df["off_ppa"] - adv_df["def_ppa"]
adv_df["net_successRate"] = adv_df["off_successRate"] - adv_df["def_successRate"]
adv_df["net_havoc"] = adv_df["def_havoc_total"] - adv_df["off_havoc_total"]  # defense forcing havoc is good, offense avoiding it is good

# ---------------------------------------------------------------------------
# 2. SP+ ratings
# ---------------------------------------------------------------------------
sp_rows = []
for y in YEARS:
    for t in load("sp", y):
        off, deff, st = t.get("offense") or {}, t.get("defense") or {}, t.get("specialTeams") or {}
        sp_rows.append({
            "season": y, "team": t["team"],
            "sp_rating": t.get("rating"), "sp_ranking": t.get("ranking"),
            "sp_off_rating": off.get("rating"), "sp_def_rating": deff.get("rating"),
            "sp_st_rating": st.get("rating"),
        })
sp_df = pd.DataFrame(sp_rows)

# ---------------------------------------------------------------------------
# 3. Returning production
# ---------------------------------------------------------------------------
ret_rows = []
for y in YEARS:
    for t in load("returning", y):
        ret_rows.append({
            "season": y, "team": t["team"],
            "ret_percentPPA": t.get("percentPPA"),
            "ret_usage": t.get("usage"),
        })
ret_df = pd.DataFrame(ret_rows)

# ---------------------------------------------------------------------------
# 4. Recruiting (team class rank/points)
# ---------------------------------------------------------------------------
rec_rows = []
for y in YEARS:
    for t in load("recruiting", y):
        rec_rows.append({"season": y, "team": t["team"], "recruit_rank": t.get("rank"),
                          "recruit_points": t.get("points")})
rec_df = pd.DataFrame(rec_rows)

# ---------------------------------------------------------------------------
# 5. Talent composite
# ---------------------------------------------------------------------------
tal_rows = []
for y in YEARS:
    for t in load("talent", y):
        tal_rows.append({"season": y, "team": t["team"], "talent": t.get("talent")})
tal_df = pd.DataFrame(tal_rows)

# ---------------------------------------------------------------------------
# 6. Games -> win/loss record per team-season (all games, incl. vs non-FBS)
# ---------------------------------------------------------------------------
win_rows = []
for y in YEARS:
    games = load("games", y)
    rec = {}  # team -> [wins, losses, points_for, points_against]
    for g in games:
        if not g.get("completed"):
            continue
        home, away = g["homeTeam"], g["awayTeam"]
        hp, ap = g.get("homePoints"), g.get("awayPoints")
        if hp is None or ap is None:
            continue
        for team, pf, pa in [(home, hp, ap), (away, ap, hp)]:
            r = rec.setdefault(team, {"w": 0, "l": 0, "pf": 0, "pa": 0, "g": 0})
            r["g"] += 1
            r["pf"] += pf
            r["pa"] += pa
            if pf > pa:
                r["w"] += 1
            elif pf < pa:
                r["l"] += 1
    for team, r in rec.items():
        win_rows.append({
            "season": y, "team": team, "games": r["g"], "wins": r["w"], "losses": r["l"],
            "win_pct": r["w"] / r["g"] if r["g"] else np.nan,
            "avg_margin": (r["pf"] - r["pa"]) / r["g"] if r["g"] else np.nan,
        })
win_df = pd.DataFrame(win_rows)

# ---------------------------------------------------------------------------
# 7. Lines -> ATS cover % per team-season (consensus = mean spread across books)
# ---------------------------------------------------------------------------
ats_rows = []
for y in YEARS:
    lines = load("lines", y)
    rec = {}  # team -> [covers, pushes, total]
    for g in lines:
        home, away = g["homeTeam"], g["awayTeam"]
        hp, ap = g.get("homeScore"), g.get("awayScore")
        if hp is None or ap is None:
            continue
        spreads = [ln["spread"] for ln in g.get("lines", []) if ln.get("spread") is not None]
        if not spreads:
            continue
        spread = sum(spreads) / len(spreads)  # consensus, home-team-relative (negative = home favored)
        margin = hp - ap  # home margin
        ats_result = margin + spread  # >0 home covers, <0 away covers, 0 push
        for team, side_result in [(home, ats_result), (away, -ats_result)]:
            r = rec.setdefault(team, {"cover": 0, "push": 0, "total": 0})
            r["total"] += 1
            if abs(side_result) < 1e-9:
                r["push"] += 1
            elif side_result > 0:
                r["cover"] += 1
    for team, r in rec.items():
        denom = r["total"] - r["push"]
        ats_rows.append({
            "season": y, "team": team, "ats_games": r["total"],
            "ats_cover_pct": r["cover"] / denom if denom else np.nan,
        })
ats_df = pd.DataFrame(ats_rows)

# ---------------------------------------------------------------------------
# Merge everything into one team-season table
# ---------------------------------------------------------------------------
team_season = adv_df.merge(sp_df, on=["season", "team"], how="outer") \
    .merge(ret_df, on=["season", "team"], how="outer") \
    .merge(rec_df, on=["season", "team"], how="outer") \
    .merge(tal_df, on=["season", "team"], how="outer") \
    .merge(win_df, on=["season", "team"], how="outer") \
    .merge(ats_df, on=["season", "team"], how="outer")

# Keep only rows that have at least advanced stats (i.e., actually FBS that season)
team_season_fbs = team_season[team_season["off_ppa"].notna()].copy()
team_season.to_csv("cfbd_team_season.csv", index=False)
team_season_fbs.to_csv("cfbd_team_season_fbs.csv", index=False)

outcomes = team_season_fbs[["season", "team", "win_pct", "ats_cover_pct", "avg_margin"]].copy()
outcomes.to_csv("cfbd_outcomes.csv", index=False)

# ---------------------------------------------------------------------------
# Build year N -> year N+1 transition table
# ---------------------------------------------------------------------------
PRIOR_COLS = ["off_ppa", "def_ppa", "net_ppa", "off_successRate", "def_successRate",
              "net_successRate", "off_havoc_total", "def_havoc_total", "net_havoc",
              "sp_rating", "sp_off_rating", "sp_def_rating", "win_pct", "ats_cover_pct", "avg_margin"]
INCOMING_COLS = ["ret_percentPPA", "ret_usage", "recruit_points", "talent"]
OUTCOME_COLS = ["win_pct", "ats_cover_pct", "avg_margin"]

prior = team_season_fbs[["season", "team"] + PRIOR_COLS].copy()
prior["season"] = prior["season"] + 1  # shift so it aligns as "N+1's predictor from year N"
prior = prior.rename(columns={c: f"prior_{c}" for c in PRIOR_COLS})

incoming = team_season_fbs[["season", "team"] + INCOMING_COLS].copy()
incoming = incoming.rename(columns={c: f"incoming_{c}" for c in INCOMING_COLS})

outcome = team_season_fbs[["season", "team"] + OUTCOME_COLS].copy()
outcome = outcome.rename(columns={c: f"outcome_{c}" for c in OUTCOME_COLS})

transitions = outcome.merge(prior, on=["season", "team"], how="inner") \
    .merge(incoming, on=["season", "team"], how="inner")
transitions.to_csv("backtest_transitions.csv", index=False)

# ---------------------------------------------------------------------------
# Correlations: each predictor vs each outcome, pooled across all transition years
# ---------------------------------------------------------------------------
predictor_cols = [c for c in transitions.columns if c.startswith("prior_") or c.startswith("incoming_")]
outcome_cols = [c for c in transitions.columns if c.startswith("outcome_")]

corr_rows = []
for p in predictor_cols:
    for o in outcome_cols:
        sub = transitions[[p, o]].dropna()
        if len(sub) < 20:
            continue
        pearson = sub[p].corr(sub[o], method="pearson")
        spearman = sub[p].corr(sub[o], method="spearman")
        corr_rows.append({"predictor": p, "outcome": o, "n": len(sub),
                           "pearson_r": pearson, "spearman_r": spearman})
corr_df = pd.DataFrame(corr_rows).sort_values(["outcome", "pearson_r"], key=lambda s: s.abs() if s.name == "pearson_r" else s, ascending=False)
corr_df.to_csv("backtest_correlations.csv", index=False)

print(f"team_season rows: {len(team_season)}  (FBS-only: {len(team_season_fbs)})")
print(f"transitions rows: {len(transitions)}  (years covered: {sorted(transitions['season'].unique())})")
print()
print("=== Correlation with outcome_win_pct (sorted by |pearson_r|) ===")
w = corr_df[corr_df.outcome == "outcome_win_pct"].sort_values("pearson_r", key=abs, ascending=False)
print(w[["predictor", "n", "pearson_r", "spearman_r"]].to_string(index=False))
print()
print("=== Correlation with outcome_ats_cover_pct (sorted by |pearson_r|) ===")
a = corr_df[corr_df.outcome == "outcome_ats_cover_pct"].sort_values("pearson_r", key=abs, ascending=False)
print(a[["predictor", "n", "pearson_r", "spearman_r"]].to_string(index=False))
