"""
Build the 2026 power rating / projected margin file.

Bottom-up model: refit the backtest regression (avg_margin ~ prior season
quality + incoming roster indicators) on 2022-2025 transitions, using only
the predictors we can actually populate for 2026 (talent composite isn't
published yet for 2026, so it's dropped from both the refit and the
application). Apply the fitted model to 2025-final-season stats + 2026
recruiting/returning production to get each team's projected 2026 margin
vs. an average FBS opponent.

Then lay that bottom-up estimate side by side with the two existing
top-down preseason composites (SP+, FPI) and Athlon's qualitative national
rank, blended into one z-score composite — agreement across the three
quantitative sources is the signal to trust, disagreement is where the
Athlon qualitative layer (coaching change, portal churn, etc.) earns its
keep as a manual adjustment.
"""
import numpy as np
import pandas as pd

# Athlon's team-name spelling -> CFBD's team-name spelling, for the handful
# of schools where they diverge (abbreviations, accents, parenthetical
# campus tags). 'North Dakota State' and 'Sacramento State' are NOT aliased
# here: both are FCS programs and their appearance in athlon_2026_teams.csv
# (tagged MWC / Mac respectively) is almost certainly a leftover OCR error
# from the original PDF extraction, not real 2026 FBS teams — see notes
# printed below and the README. Left unmapped on purpose so they don't
# silently get fake stats merged in.
ATHLON_TO_CFBD = {
    "Cal": "California",
    "Miami (Fla.)": "Miami",
    "Pitt": "Pittsburgh",
    "FIU": "Florida International",
    "WKU": "Western Kentucky",
    "Miami (Ohio)": "Miami (OH)",
    "UMass": "Massachusetts",
    "San Jose State": "San José State",
    "Appalachian State": "App State",
    "ULM": "UL Monroe",
}

# ---------------------------------------------------------------------------
# 1. Refit the margin-prediction model on 2022-2025 transitions, dropping
#    incoming_talent (unavailable for 2026).
# ---------------------------------------------------------------------------
trans = pd.read_csv("backtest_transitions.csv")
predictors = ["prior_avg_margin", "prior_sp_rating", "prior_net_havoc",
              "incoming_recruit_points", "incoming_ret_percentPPA"]
sub = trans[predictors + ["outcome_avg_margin"]].dropna()

means = sub[predictors].mean()
stds = sub[predictors].std()
Xz = (sub[predictors] - means) / stds
X = np.column_stack([np.ones(len(Xz)), Xz.values])
y = sub["outcome_avg_margin"].values
beta, *_ = np.linalg.lstsq(X, y, rcond=None)
pred = X @ beta
r2 = 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()
print(f"Refit margin model (talent dropped): n={len(sub)}  R^2={r2:.3f}")
print("Standardized coefficients:", dict(zip(["intercept"] + predictors, np.round(beta, 3))))

# ---------------------------------------------------------------------------
# 2. Assemble 2026 inputs: prior = 2025 final season, incoming = 2026 class
# ---------------------------------------------------------------------------
team_season = pd.read_csv("cfbd_team_season_fbs.csv")
prior_2025 = team_season[team_season.season == 2025][
    ["team", "avg_margin", "sp_rating", "net_havoc"]
].rename(columns={"avg_margin": "prior_avg_margin", "sp_rating": "prior_sp_rating",
                   "net_havoc": "prior_net_havoc"})

import json
rec = json.load(open("cfbd_raw/recruiting_2026.json", encoding="utf-8"))
recruiting_2026 = pd.DataFrame([{"team": r["team"], "incoming_recruit_points": r.get("points")} for r in rec])
ret = json.load(open("cfbd_raw/returning_2026.json", encoding="utf-8"))
returning_2026 = pd.DataFrame([{"team": r["team"], "incoming_ret_percentPPA": r.get("percentPPA")} for r in ret])

model_input = prior_2025.merge(recruiting_2026, on="team", how="left") \
    .merge(returning_2026, on="team", how="left")

missing = model_input[model_input[predictors].isna().any(axis=1)]
print(f"\nTeams missing an input for the bottom-up model (dropped from that column only, see notes): {len(missing)}")
if len(missing):
    print(missing[["team"] + predictors].to_string(index=False))

# Apply fitted model using TRAINING means/stds (not refit on 2026 data) —
# missing inputs fall back to the training mean (z=0), i.e. "assume average"
# for that one factor rather than dropping the team.
Xz_2026 = (model_input[predictors] - means) / stds
Xz_2026 = Xz_2026.fillna(0.0)
X_2026 = np.column_stack([np.ones(len(Xz_2026)), Xz_2026.values])
model_input["model_proj_margin_2026"] = X_2026 @ beta

# ---------------------------------------------------------------------------
# 3. Merge in the top-down composites + Athlon qualitative rank
# ---------------------------------------------------------------------------
sp = pd.read_csv("sp_plus_2026_preseason.csv")[["team", "sp_plus"]]
fpi = pd.read_csv("espn_fpi_2026_preseason.csv")[["team", "fpi"]]
athlon = pd.read_csv("athlon_2026_teams.csv")[["team", "conference", "national_forecast_rank",
                                                "record_2025_overall", "head_coach",
                                                "returning_starters_offense", "returning_starters_defense"]]
athlon["_join_key"] = athlon["team"].replace(ATHLON_TO_CFBD)

final = athlon.merge(model_input[["team", "model_proj_margin_2026"] + predictors].rename(columns={"team": "_join_key"}), on="_join_key", how="left") \
    .merge(sp, on="team", how="left") \
    .merge(fpi, on="team", how="left")

for col, label in [("model_proj_margin_2026", "bottom-up model"), ("sp_plus", "SP+ preseason"), ("fpi", "FPI preseason")]:
    n_missing = final[col].isna().sum()
    if n_missing:
        print(f"\n{n_missing} teams missing {label}: {final[final[col].isna()].team.tolist()}")

# ---------------------------------------------------------------------------
# 4. Blended composite: z-score the three quantitative sources, average
# ---------------------------------------------------------------------------
for col in ["model_proj_margin_2026", "sp_plus", "fpi"]:
    final[f"z_{col}"] = (final[col] - final[col].mean()) / final[col].std()

final["blended_score"] = final[["z_model_proj_margin_2026", "z_sp_plus", "z_fpi"]].mean(axis=1, skipna=True)
final["blended_rank"] = final["blended_score"].rank(ascending=False, method="min").astype("Int64")

# Spread across the 3 sources (disagreement flag): std of the 3 z-scores per team
final["source_disagreement"] = final[["z_model_proj_margin_2026", "z_sp_plus", "z_fpi"]].std(axis=1)

final = final.sort_values("blended_score", ascending=False)
out_cols = ["blended_rank", "team", "conference", "blended_score", "source_disagreement",
            "model_proj_margin_2026", "sp_plus", "fpi", "national_forecast_rank",
            "record_2025_overall", "head_coach", "returning_starters_offense",
            "returning_starters_defense", "incoming_recruit_points", "incoming_ret_percentPPA"]
final[out_cols].to_csv("cfb_2026_power_ratings.csv", index=False)

print(f"\nSaved cfb_2026_power_ratings.csv — {len(final)} teams")
print("\n=== Top 15 ===")
print(final[out_cols].head(15).to_string(index=False))
print("\n=== Biggest 3-source disagreements (worth a manual/Athlon-qualitative look) ===")
print(final.sort_values("source_disagreement", ascending=False)[["team", "blended_rank", "model_proj_margin_2026", "sp_plus", "fpi", "source_disagreement"]].head(10).to_string(index=False))
