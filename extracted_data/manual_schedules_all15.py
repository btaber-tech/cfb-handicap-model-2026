# -*- coding: utf-8 -*-
"""All 15 originally-problematic teams' 2026 schedules, transcribed directly
from the rendered page images (visually verified, not OCR'd) after the
automated extraction proved unreliable for these specific pages (colored
header banners that don't OCR, and/or column-bleed noise in the data rows).
"""
import csv, difflib, os

SCRATCH = r"C:\Users\BenTa\AppData\Local\Temp\claude\C--Users-BenTa-OneDrive-Desktop-College-Football\219ab1a4-16a9-41b1-bed9-02f025818d0f\scratchpad"
OUT_CSV = os.path.join(SCRATCH, "athlon_2026_schedules_manual_all15.csv")

FBS_TEAMS = sorted(set([
    "Boston College", "Cal", "Clemson", "Duke", "Florida State", "Georgia Tech",
    "Louisville", "Miami (Fla.)", "North Carolina", "NC State", "Pitt", "SMU",
    "Stanford", "Syracuse", "Virginia", "Virginia Tech", "Wake Forest",
    "Army", "Charlotte", "East Carolina", "Florida Atlantic", "Memphis", "Navy",
    "North Texas", "Rice", "South Florida", "Temple", "Tulane", "Tulsa", "UAB", "UTSA",
    "Arizona", "Arizona State", "Baylor", "BYU", "Cincinnati", "Colorado", "Houston",
    "Iowa State", "Kansas", "Kansas State", "Oklahoma State", "TCU", "Texas Tech",
    "UCF", "Utah", "West Virginia",
    "Illinois", "Indiana", "Iowa", "Maryland", "Michigan", "Michigan State",
    "Minnesota", "Nebraska", "Northwestern", "Ohio State", "Oregon", "Penn State",
    "Purdue", "Rutgers", "UCLA", "USC", "Washington", "Wisconsin",
    "Delaware", "FIU", "Jacksonville State", "Kennesaw State", "Liberty",
    "Middle Tennessee", "Missouri State", "New Mexico State", "Sam Houston", "WKU",
    "Notre Dame", "UConn",
    "Akron", "Ball State", "Bowling Green", "Buffalo", "Central Michigan",
    "Eastern Michigan", "Kent State", "Miami (Ohio)", "Ohio", "Sacramento State",
    "Toledo", "UMass", "Western Michigan",
    "Air Force", "Hawai'i", "Nevada", "New Mexico", "North Dakota State",
    "Northern Illinois", "San Jose State", "UNLV", "UTEP", "Wyoming",
    "Boise State", "Colorado State", "Fresno State", "Oregon State", "San Diego State",
    "Texas State", "Utah State", "Washington State",
    "Alabama", "Arkansas", "Auburn", "Florida", "Georgia", "Kentucky", "LSU",
    "Mississippi State", "Missouri", "Oklahoma", "Ole Miss", "South Carolina",
    "Tennessee", "Texas", "Texas A&M", "Vanderbilt",
    "Appalachian State", "Coastal Carolina", "Georgia Southern", "Georgia State",
    "James Madison", "Marshall", "Old Dominion", "Arkansas State", "Louisiana",
    "Louisiana Tech", "South Alabama", "Southern Miss", "Troy", "ULM",
]))

SCHEDULES = {
    "North Carolina": [
        ("Aug. 29", "vs. TCU #", "neutral"),
        ("Sept. 12", "East Tennessee St.", "home"),
        ("Sept. 19", "at Clemson", "away"),
        ("Oct. 3", "Notre Dame", "home"),
        ("Oct. 10", "at Pitt", "away"),
        ("Oct. 17", "at Duke", "away"),
        ("Oct. 24", "Syracuse", "home"),
        ("Oct. 31", "Miami (Fla.)", "home"),
        ("Nov. 7", "at UConn", "away"),
        ("Nov. 14", "Louisville", "home"),
        ("Nov. 21", "at Virginia", "away"),
        ("Nov. 28", "NC State", "home"),
    ],
    "Wake Forest": [
        ("Sept. 3", "Akron", "home"),
        ("Sept. 12", "at Purdue", "away"),
        ("Sept. 18", "Miami (Fla.)", "home"),
        ("Sept. 26", "at Louisville", "away"),
        ("Oct. 3", "Stanford", "home"),
        ("Oct. 10", "at NC State", "away"),
        ("Oct. 17", "at Cal", "away"),
        ("Oct. 31", "Virginia", "home"),
        ("Nov. 7", "Merrimack", "home"),
        ("Nov. 14", "at SMU", "away"),
        ("Nov. 21", "at Georgia Tech", "away"),
        ("Nov. 28", "Duke", "home"),
    ],
    "Oklahoma State": [
        ("Sept. 5", "at Tulsa", "away"),
        ("Sept. 12", "Oregon", "home"),
        ("Sept. 19", "Murray State", "home"),
        ("Sept. 26", "at West Virginia", "away"),
        ("Oct. 10", "UCF", "home"),
        ("Oct. 17", "at Houston", "away"),
        ("Oct. 24", "Colorado", "home"),
        ("Oct. 31", "at Iowa State", "away"),
        ("Nov. 7", "at Kansas State", "away"),
        ("Nov. 14", "Texas Tech", "home"),
        ("Nov. 21", "at Arizona State", "away"),
        ("Nov. 28", "Kansas", "home"),
    ],
    "UCF": [
        ("Sept. 3", "Bethune-Cookman", "home"),
        ("Sept. 12", "at Pitt", "away"),
        ("Sept. 19", "Georgia State", "home"),
        ("Sept. 26", "TCU", "home"),
        ("Oct. 3", "at Houston", "away"),
        ("Oct. 10", "at Oklahoma State", "away"),
        ("Oct. 24", "BYU", "home"),
        ("Oct. 31", "Baylor", "home"),
        ("Nov. 7", "at Kansas", "away"),
        ("Nov. 14", "Arizona State", "home"),
        ("Nov. 21", "Iowa State", "home"),
        ("Nov. 28", "at Colorado", "away"),
    ],
    "Bowling Green": [
        ("Sept. 5", "Tarleton State", "home"),
        ("Sept. 12", "at Nebraska", "away"),
        ("Sept. 19", "at Iowa State", "away"),
        ("Sept. 26", "South Florida", "home"),
        ("Oct. 3", "at Miami (Ohio)", "away"),
        ("Oct. 10", "Sacramento State", "home"),
        ("Oct. 17", "Ball State", "home"),
        ("Oct. 24", "at Buffalo", "away"),
        ("Oct. 31", "at Western Michigan", "away"),
        ("Nov. 10", "Kent State", "home"),
        ("Nov. 18", "at Toledo", "away"),
        ("Nov. 28", "UMass", "home"),
    ],
    "Missouri": [
        ("Sept. 5", "Arkansas-Pine Bluff", "home"),
        ("Sept. 12", "at Kansas", "away"),
        ("Sept. 19", "Troy", "home"),
        ("Sept. 26", "at Mississippi State", "away"),
        ("Oct. 3", "Florida", "home"),
        ("Oct. 10", "Texas A&M", "home"),
        ("Oct. 17", "at Ole Miss", "away"),
        ("Oct. 31", "Arkansas", "home"),
        ("Nov. 7", "Texas", "home"),
        ("Nov. 14", "at Georgia", "away"),
        ("Nov. 21", "Kentucky", "home"),
        ("Nov. 28", "Oklahoma", "home"),
    ],
    "Vanderbilt": [
        ("Sept. 5", "Austin Peay", "home"),
        ("Sept. 12", "Delaware", "home"),
        ("Sept. 19", "NC State", "home"),
        ("Sept. 26", "at Auburn", "away"),
        ("Oct. 3", "at Georgia", "away"),
        ("Oct. 10", "Ole Miss", "home"),
        ("Oct. 17", "Arkansas", "home"),
        ("Oct. 24", "at Kentucky", "away"),
        ("Nov. 7", "at Mississippi State", "away"),
        ("Nov. 14", "Alabama", "home"),
        ("Nov. 21", "at Florida", "away"),
        ("Nov. 28", "Tennessee", "home"),
    ],
    "Louisville": [
        ("Sept. 6", "vs. Ole Miss #", "neutral"),
        ("Sept. 11", "Villanova", "home"),
        ("Sept. 19", "SMU", "home"),
        ("Sept. 26", "Wake Forest", "home"),
        ("Oct. 3", "at NC State", "away"),
        ("Oct. 9", "Florida State", "home"),
        ("Oct. 17", "at Syracuse", "away"),
        ("Oct. 31", "Stanford", "home"),
        ("Nov. 7", "at Georgia Tech", "away"),
        ("Nov. 14", "at North Carolina", "away"),
        ("Nov. 21", "Pitt", "home"),
        ("Nov. 28", "at Kentucky", "away"),
    ],
    "Virginia Tech": [
        ("Sept. 5", "VMI", "home"),
        ("Sept. 12", "Old Dominion", "home"),
        ("Sept. 19", "at Maryland", "away"),
        ("Sept. 26", "at Boston College", "away"),
        ("Oct. 2", "Pitt", "home"),
        ("Oct. 10", "at Cal", "away"),
        ("Oct. 17", "Georgia Tech", "home"),
        ("Oct. 24", "at Clemson", "away"),
        ("Nov. 7", "at SMU", "away"),
        ("Nov. 14", "Stanford", "home"),
        ("Nov. 20", "at Miami (Fla.)", "away"),
        ("Nov. 28", "Virginia", "home"),
    ],
    "Purdue": [
        ("Sept. 5", "Indiana State", "home"),
        ("Sept. 12", "Wake Forest", "home"),
        ("Sept. 19", "at UCLA", "away"),
        ("Sept. 26", "Notre Dame", "home"),
        ("Oct. 3", "at Illinois", "away"),
        ("Oct. 10", "Minnesota", "home"),
        ("Oct. 17", "Washington", "home"),
        ("Oct. 31", "at Penn State", "away"),
        ("Nov. 7", "Maryland", "home"),
        ("Nov. 14", "at Iowa", "away"),
        ("Nov. 21", "Wisconsin", "home"),
        ("Nov. 28", "at Indiana", "away"),
    ],
    "Buffalo": [
        ("Sept. 3", "UAlbany", "home"),
        ("Sept. 12", "at FIU", "away"),
        ("Sept. 19", "at Penn State", "away"),
        ("Sept. 26", "Robert Morris", "home"),
        ("Oct. 3", "Western Michigan", "home"),
        ("Oct. 10", "at Toledo", "away"),
        ("Oct. 17", "UMass", "home"),
        ("Oct. 24", "Bowling Green", "home"),
        ("Nov. 3", "at Miami (Ohio)", "away"),
        ("Nov. 11", "at Ball State", "away"),
        ("Nov. 18", "Central Michigan", "home"),
        ("Nov. 27", "at Akron", "away"),
    ],
    "UTEP": [
        ("Sept. 5", "at Oklahoma", "away"),
        ("Sept. 12", "Texas Southern", "home"),
        ("Sept. 19", "at Michigan", "away"),
        ("Sept. 26", "Oregon State", "home"),
        ("Oct. 3", "at New Mexico", "away"),
        ("Oct. 10", "Nevada", "home"),
        ("Oct. 17", "San Jose State", "home"),
        ("Oct. 31", "at North Dakota State", "away"),
        ("Nov. 7", "Hawai'i", "home"),
        ("Nov. 14", "Wyoming", "home"),
        ("Nov. 21", "at Air Force", "away"),
        ("Nov. 28", "at Northern Illinois", "away"),
    ],
    "Boise State": [
        ("Sept. 5", "at Oregon", "away"),
        ("Sept. 12", "Memphis", "home"),
        ("Sept. 19", "South Dakota", "home"),
        ("Sept. 26", "at Western Michigan", "away"),
        ("Oct. 3", "Utah State", "home"),
        ("Oct. 10", "at Fresno State", "away"),
        ("Oct. 24", "at Washington State", "away"),
        ("Oct. 31", "Texas State", "home"),
        ("Nov. 7", "at Colorado State", "away"),
        ("Nov. 14", "Oregon State", "home"),
        ("Nov. 21", "San Diego State", "home"),
        ("Nov. 28", "at Utah State #", "away"),
    ],
    "Fresno State": [
        ("Sept. 5", "at USC", "away"),
        ("Sept. 12", "Sacramento State", "home"),
        ("Sept. 19", "at San Jose State", "away"),
        ("Sept. 26", "Rice", "home"),
        ("Oct. 3", "at Washington State", "away"),
        ("Oct. 10", "Boise State", "home"),
        ("Oct. 17", "at San Diego State", "away"),
        ("Oct. 31", "Oregon State", "home"),
        ("Nov. 7", "at Utah State", "away"),
        ("Nov. 14", "at Texas State", "away"),
        ("Nov. 21", "Colorado State", "home"),
        ("Nov. 28", "San Diego State #", "home"),
    ],
    "Tennessee": [
        ("Sept. 5", "Furman", "home"),
        ("Sept. 12", "at Georgia Tech", "away"),
        ("Sept. 19", "Kennesaw State", "home"),
        ("Sept. 26", "Texas", "home"),
        ("Oct. 3", "Auburn", "home"),
        ("Oct. 10", "at Arkansas", "away"),
        ("Oct. 17", "Alabama", "home"),
        ("Oct. 24", "at South Carolina", "away"),
        ("Nov. 7", "Kentucky", "home"),
        ("Nov. 14", "at Texas A&M", "away"),
        ("Nov. 21", "LSU", "home"),
        ("Nov. 28", "at Vanderbilt", "away"),
    ],
}

def match_opponent(raw):
    cleaned = raw.replace("at ", "").replace("vs. ", "").replace("#", "").strip()
    matches = difflib.get_close_matches(cleaned, FBS_TEAMS, n=1, cutoff=0.55)
    if matches:
        conf = round(difflib.SequenceMatcher(None, cleaned.lower(), matches[0].lower()).ratio(), 2)
        if conf >= 0.75:
            return matches[0]
    return ""

def main():
    fieldnames = ["team", "game_number", "date_raw", "opponent_raw", "opponent_matched", "home_away", "match_confidence"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for team, games in SCHEDULES.items():
            for i, (date_raw, opp_raw, ha) in enumerate(games, 1):
                matched = match_opponent(opp_raw)
                conf = 1.0 if matched else ""
                w.writerow({
                    "team": team, "game_number": i, "date_raw": date_raw,
                    "opponent_raw": opp_raw, "opponent_matched": matched,
                    "home_away": ha, "match_confidence": conf,
                })
    total = sum(len(v) for v in SCHEDULES.values())
    print(f"Wrote {total} manually-verified rows for {len(SCHEDULES)} teams to {OUT_CSV}")

if __name__ == "__main__":
    main()
