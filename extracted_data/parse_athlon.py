# -*- coding: utf-8 -*-
import re
import csv

SRC = r"C:\Users\BenTa\AppData\Local\Temp\claude\C--Users-BenTa-OneDrive-Desktop-College-Football\90fc890e-e241-4c6c-a2e5-d4eca96abaec\scratchpad\athlon_2026_ocr.txt"
OUT_CSV = r"C:\Users\BenTa\AppData\Local\Temp\claude\C--Users-BenTa-OneDrive-Desktop-College-Football\90fc890e-e241-4c6c-a2e5-d4eca96abaec\scratchpad\athlon_2026_teams.csv"
OUT_NARRATIVE = r"C:\Users\BenTa\AppData\Local\Temp\claude\C--Users-BenTa-OneDrive-Desktop-College-Football\90fc890e-e241-4c6c-a2e5-d4eca96abaec\scratchpad\athlon_2026_narrative.txt"

with open(SRC, encoding="utf-8") as f:
    text = f.read()

lines = text.split("\n")

forecast_re = re.compile(
    r"NATIONAL FORECAST:\s*(\d+)\s*\|\s*(?:([A-Z0-9 \-]+?)\s*PREDICTION:\s*(\d+)\s*\|\s*)?2025 RECORD:\s*(\d+-\d+)(?:,\s*(\d+-\d+)\s*([A-Z0-9 ]+))?"
)

anchors = []
for i, ln in enumerate(lines):
    m = forecast_re.search(ln)
    if m:
        anchors.append((i, m))

print(f"Found {len(anchors)} team anchors")

# Ground-truth page-number -> team-name map, taken from the magazine's own
# table of contents (pages 4-5), which is far more reliable than OCR'ing
# the stylized team-name header graphic on each team's page.
PAGE_TO_TEAM = {
    52: "Boston College", 53: "Cal", 54: "Clemson", 55: "Duke", 56: "Florida State",
    57: "Georgia Tech", 58: "Louisville", 59: "Miami (Fla.)", 60: "North Carolina",
    61: "NC State", 62: "Pitt", 63: "SMU", 64: "Stanford", 65: "Syracuse",
    66: "Virginia", 67: "Virginia Tech", 68: "Wake Forest",
    72: "Army", 73: "Charlotte", 74: "East Carolina", 75: "Florida Atlantic",
    76: "Memphis", 77: "Navy", 78: "North Texas", 79: "Rice", 80: "South Florida",
    81: "Temple", 82: "Tulane", 83: "Tulsa", 84: "UAB", 85: "UTSA",
    88: "Arizona", 89: "Arizona State", 90: "Baylor", 91: "BYU", 92: "Cincinnati",
    93: "Colorado", 94: "Houston", 95: "Iowa State", 96: "Kansas", 97: "Kansas State",
    98: "Oklahoma State", 99: "TCU", 100: "Texas Tech", 101: "UCF", 102: "Utah",
    103: "West Virginia",
    106: "Illinois", 107: "Indiana", 108: "Iowa", 109: "Maryland", 110: "Michigan",
    111: "Michigan State", 112: "Minnesota", 113: "Nebraska", 114: "Northwestern",
    115: "Ohio State", 116: "Oregon", 117: "Penn State", 118: "Purdue", 119: "Rutgers",
    120: "UCLA", 121: "USC", 122: "Washington", 123: "Wisconsin",
    126: "Delaware", 127: "FIU", 128: "Jacksonville State", 129: "Kennesaw State",
    130: "Liberty", 131: "Middle Tennessee", 132: "Missouri State",
    133: "New Mexico State", 134: "Sam Houston", 135: "WKU",
    136: "Notre Dame", 137: "UConn",
    140: "Akron", 141: "Ball State", 142: "Bowling Green", 143: "Buffalo",
    144: "Central Michigan", 145: "Eastern Michigan", 146: "Kent State",
    147: "Miami (Ohio)", 148: "Ohio", 149: "Sacramento State", 150: "Toledo",
    151: "UMass", 152: "Western Michigan",
    156: "Air Force", 157: "Hawai'i", 158: "Nevada", 159: "New Mexico",
    160: "North Dakota State", 161: "Northern Illinois", 162: "San Jose State",
    163: "UNLV", 164: "UTEP", 165: "Wyoming",
    168: "Boise State", 169: "Colorado State", 170: "Fresno State",
    171: "Oregon State", 172: "San Diego State", 173: "Texas State",
    174: "Utah State", 175: "Washington State",
    178: "Alabama", 179: "Arkansas", 180: "Auburn", 181: "Florida", 182: "Georgia",
    183: "Kentucky", 184: "LSU", 185: "Mississippi State", 186: "Missouri",
    187: "Oklahoma", 188: "Ole Miss", 189: "South Carolina", 190: "Tennessee",
    191: "Texas", 192: "Texas A&M", 193: "Vanderbilt",
    196: "Appalachian State", 197: "Coastal Carolina", 198: "Georgia Southern",
    199: "Georgia State", 200: "James Madison", 201: "Marshall", 202: "Old Dominion",
    203: "Arkansas State", 204: "Louisiana", 205: "Louisiana Tech",
    206: "South Alabama", 207: "Southern Miss", 208: "Troy", 209: "ULM",
}

page_marker_re = re.compile(r"===== PAGE (\d+) =====")

def page_for_anchor(idx):
    for j in range(idx, -1, -1):
        m = page_marker_re.search(lines[j])
        if m:
            return int(m.group(1))
    return None

def find_team_name(idx):
    for back in range(1, 6):
        j = idx - back
        if j < 0:
            break
        candidate = lines[j].strip()
        if not candidate:
            continue
        if candidate.startswith("====="):
            continue
        cleaned = candidate
        if "|" in cleaned:
            cleaned = cleaned.rsplit("|", 1)[-1]
        cleaned = re.sub(r"^[:\s]+", "", cleaned).strip()
        letters = re.sub(r"[^A-Za-z]", "", cleaned)
        if len(letters) >= 4 and letters == letters.upper() and cleaned == cleaned.upper():
            return cleaned
        # not a name candidate -> keep scanning upward (could be a stray junk line)
    return ""

def block_text(start, end):
    return "\n".join(lines[start:end])

depth_offense_re = re.compile(r"OFFENSE\s*\((\d+)\)")
depth_defense_re = re.compile(r"DEFENSE\s*\((\d+)\)")

LABELS = [
    "Coach", "Record at School", "Career Record",
    "Offensive Coordinators?", "Defensive Coordinators?",
    "Location", "Stadium",
]
label_alt = "|".join(LABELS)
split_re = re.compile(rf"(?=(?:{label_alt}):)")
seg_re = re.compile(rf"^({label_alt}):\s*(.*)$", re.S)
stadium_cap_re = re.compile(r"(.+?)\s*\(([\d,\.]+)\)")
first_digit_re = re.compile(r"\d")
coach_anchor_re = re.compile(r"Coach:")

def parse_coach_block(block):
    flat = re.sub(r"\s+", " ", block)
    m0 = coach_anchor_re.search(flat)
    idx = m0.start() if m0 else -1
    if idx == -1:
        return {}
    # bound the region: stop at next page marker or ~500 chars
    region = flat[idx: idx + 600]
    cut = region.find("SHOP.ATHLONSPORTS.COM")
    if cut != -1:
        region = region[:cut]
    cut2 = region.find("=====")
    if cut2 != -1:
        region = region[:cut2]

    segments = split_re.split(region)
    out = {}
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        m = seg_re.match(seg)
        if not m:
            continue
        label = m.group(1).lower().replace("?", "")
        value = m.group(2).strip().rstrip("-").strip()
        if label.startswith("coach"):
            out["head_coach"] = value
        elif label.startswith("record at school"):
            out["hc_record_at_school"] = value
        elif label.startswith("career record"):
            out["hc_career_record"] = value
        elif label.startswith("offensive coordinator"):
            out["offensive_coordinator"] = truncate_at_digit(value)
        elif label.startswith("defensive coordinator"):
            out["defensive_coordinator"] = truncate_at_digit(value)
        elif label.startswith("location"):
            out["location"] = truncate_at_digit(value)
        elif label.startswith("stadium"):
            sm = stadium_cap_re.match(value)
            if sm:
                out["stadium"] = sm.group(1).strip()
                out["stadium_capacity"] = sm.group(2).replace(",", "").replace(".", "")
            else:
                out["stadium"] = value
    return out

def truncate_at_digit(value):
    # Coordinator/location fields never legitimately contain digits; a digit
    # means depth-chart or schedule text bled in via column-order OCR noise.
    m = first_digit_re.search(value)
    if m:
        value = value[: m.start()]
    value = value.split("#")[0]  # bowl-game notation always starts with '#'
    value = re.sub(r"\s+[A-Z]$", "", value)  # trailing lone specialist-position letter (K/P)
    return value.strip(" -,'\"|")

def split_years(record_field):
    # "9-16 (2 years)" -> ("9-16", "2") ; "27-20 (3+ years)" -> ("27-20", "3+")
    # "First Season" -> ("0-0", "0")
    m = re.match(r"([\d]+-[\d]+)\s*\((\d+\+?)\s*years?\)", record_field)
    if m:
        return m.group(1), m.group(2)
    if "first season" in record_field.lower():
        return "0-0", "0"
    # fallback: pull just the W-L if present, drop the rest as noise
    m2 = re.match(r"([\d]+-[\d]+)", record_field)
    if m2:
        return m2.group(1), ""
    return record_field, ""

rows = []
narrative_chunks = []

for k, (idx, m) in enumerate(anchors):
    start = idx
    end = anchors[k + 1][0] if k + 1 < len(anchors) else len(lines)
    block = block_text(start, end)

    national_rank = int(m.group(1))
    conf_label = (m.group(2) or "").strip()
    conf_pred = m.group(3) or ""
    rec_overall = m.group(4)
    rec_conf = m.group(5) or ""
    conf_from_record = (m.group(6) or "").strip()

    page_num = page_for_anchor(idx)
    team_name = PAGE_TO_TEAM.get(page_num) or find_team_name(idx)

    if conf_label:
        conference = re.sub(r"\s+", " ", conf_label).title()
        conference = (conference.replace("Mwc", "MWC").replace("Cusa", "CUSA")
                      .replace("Acc", "ACC").replace("Sec", "SEC").replace("Sbc", "SBC")
                      .replace("Usa", "USA"))
    else:
        conference = "Independent"

    coach_info = parse_coach_block(block)
    hc_record_raw, hc_years = split_years(coach_info.get("hc_record_at_school", ""))
    career_record_raw, career_years = split_years(coach_info.get("hc_career_record", ""))

    off_m = depth_offense_re.search(block)
    def_m = depth_defense_re.search(block)
    ret_off = off_m.group(1) if off_m else ""
    ret_def = def_m.group(1) if def_m else ""

    rows.append({
        "team": team_name,
        "conference": conference,
        "conference_predicted_finish": conf_pred,
        "national_forecast_rank": national_rank,
        "record_2025_overall": rec_overall,
        "record_2025_conference": rec_conf,
        "record_2025_conference_label": conf_from_record,
        "returning_starters_offense": ret_off,
        "returning_starters_defense": ret_def,
        "head_coach": coach_info.get("head_coach", ""),
        "hc_record_at_school": hc_record_raw,
        "hc_years_at_school": hc_years,
        "hc_career_record": career_record_raw,
        "hc_career_years": career_years,
        "offensive_coordinator": coach_info.get("offensive_coordinator", ""),
        "defensive_coordinator": coach_info.get("defensive_coordinator", ""),
        "location": coach_info.get("location", ""),
        "stadium": coach_info.get("stadium", ""),
        "stadium_capacity": coach_info.get("stadium_capacity", ""),
    })

    narrative_chunks.append(f"===== {team_name} =====\n{block}\n")

fieldnames = list(rows[0].keys())
with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    for r in rows:
        w.writerow(r)

with open(OUT_NARRATIVE, "w", encoding="utf-8") as f:
    f.write("\n".join(narrative_chunks))

print(f"Wrote {len(rows)} rows to {OUT_CSV}")
missing_coach = sum(1 for r in rows if not r["head_coach"])
missing_starters_off = sum(1 for r in rows if not r["returning_starters_offense"])
missing_starters_def = sum(1 for r in rows if not r["returning_starters_defense"])
missing_team = sum(1 for r in rows if not r["team"])
missing_stadium = sum(1 for r in rows if not r["stadium"])
print(f"Missing team name: {missing_team}")
print(f"Missing head_coach: {missing_coach}")
print(f"Missing returning_starters_offense: {missing_starters_off}")
print(f"Missing returning_starters_defense: {missing_starters_def}")
print(f"Missing stadium: {missing_stadium}")

if missing_team:
    print("Teams with missing name (by rank):", [r["national_forecast_rank"] for r in rows if not r["team"]])
