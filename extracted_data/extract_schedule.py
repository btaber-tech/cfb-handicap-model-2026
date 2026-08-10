# -*- coding: utf-8 -*-
"""
Column-aware extraction of the '2026 SCHEDULE' box from each team's Athlon
preview page. Renders each page at high DPI, runs Tesseract in TSV mode to
get word-level bounding boxes, then uses the x/y coordinates of the
'2025 RESULTS / 2026 SCHEDULE / TOP 10 RECRUITS' header row to isolate just
the schedule column -- avoiding the column-bleed that full-page linear OCR
produces.
"""
import re
import csv
import subprocess
import tempfile
import os
import difflib
import fitz

PDF = r"C:\Users\BenTa\OneDrive\Desktop\College Football\Athlon Sports College Football Preview 2026.pdf"
TESSERACT = r"C:\Users\BenTa\scoop\shims\tesseract.exe"
TSV_CONFIG = r"C:\Users\BenTa\scoop\apps\tesseract\current\tessdata\configs\tsv"
os.environ["TESSDATA_PREFIX"] = r"C:\Users\BenTa\scoop\apps\tesseract-languages\current"
OUT_CSV = r"C:\Users\BenTa\AppData\Local\Temp\claude\C--Users-BenTa-OneDrive-Desktop-College-Football\90fc890e-e241-4c6c-a2e5-d4eca96abaec\scratchpad\athlon_2026_schedules.csv"

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
FBS_TEAMS = sorted(set(PAGE_TO_TEAM.values()))

MONTH_FIX = {"uct": "oct", "lan": "jan", "aug": "aug", "sept": "sept", "sep": "sept",
             "nov": "nov", "dec": "dec", "jan": "jan", "feb": "feb"}

def render_page(page_num, dpi=400):
    doc = fitz.open(PDF)
    page = doc.load_page(page_num - 1)
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    pix.save(path)
    doc.close()
    return path

def run_tsv(img_path):
    fd, base = tempfile.mkstemp(suffix="")
    os.close(fd)
    os.remove(base)
    subprocess.run([TESSERACT, img_path, base, TSV_CONFIG], capture_output=True, text=True)
    tsv_path = base + ".tsv"
    words = []
    with open(tsv_path, encoding="utf-8") as f:
        r = csv.DictReader(f, delimiter="\t")
        for row in r:
            t = row["text"].strip()
            if not t:
                continue
            try:
                words.append({
                    "left": int(row["left"]), "top": int(row["top"]),
                    "width": int(row["width"]), "text": t,
                })
            except (ValueError, KeyError):
                continue
    os.remove(tsv_path)
    return words

def find_word(words, pattern, min_top=0):
    for w in words:
        if w["top"] >= min_top and re.fullmatch(pattern, w["text"], re.I):
            return w
    return None

def cluster_rows(words, gap=40):
    words = sorted(words, key=lambda w: w["top"])
    rows = []
    cur = []
    last_top = None
    for w in words:
        if last_top is not None and w["top"] - last_top > gap:
            rows.append(cur)
            cur = []
        cur.append(w)
        last_top = w["top"]
    if cur:
        rows.append(cur)
    return rows

DATE_RE = re.compile(
    r"(aug|sept|sep|oct|uct|nov|dec|jan|lan|feb)\.?\s*(\d{1,2})", re.I
)

def parse_date(text):
    m = DATE_RE.search(text)
    if not m:
        return ""
    mon = m.group(1).lower()
    mon = MONTH_FIX.get(mon, mon)
    return f"{mon.capitalize()}. {m.group(2)}"

def match_opponent(raw):
    # strip date fragments and punctuation noise
    cleaned = DATE_RE.sub("", raw)
    away = bool(re.search(r"\bat\b", cleaned, re.I)) or re.search(r"\bat[A-Z]", cleaned)
    neutral = bool(re.search(r"\bvs\.?\b", cleaned, re.I))
    cleaned = re.sub(r"\bat\b", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\bvs\.?\b", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"^[Aa]t(?=[A-Z])", " ", cleaned)  # "atRutgers" -> " Rutgers"
    cleaned = re.sub(r"[|#%$&*.,]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return "", "", 0.0
    side = "away" if away else ("neutral" if neutral else "home")
    # Many opponents are FCS "buy games" not in our 138-team FBS list; a low
    # cutoff would force-fit those onto the nearest-spelled FBS name, which
    # is worse than leaving them blank. Require a fairly high similarity
    # before trusting the match.
    matches = difflib.get_close_matches(cleaned, FBS_TEAMS, n=1, cutoff=0.55)
    if matches:
        conf = round(difflib.SequenceMatcher(None, cleaned.lower(), matches[0].lower()).ratio(), 2)
        if conf >= 0.75:
            return matches[0], side, conf
        return "", side, conf  # below threshold: don't guess, leave for manual review
    return "", side, 0.0

def extract_schedule_for_page(page_num, team):
    img_path = render_page(page_num)
    try:
        words = run_tsv(img_path)
    finally:
        os.remove(img_path)

    hdr_sched = find_word(words, r"SCHEDULE")
    header_scope = hdr_sched["top"] - 50 if hdr_sched else 0
    hdr_2026 = find_word(words, r"2026", min_top=header_scope)
    hdr_top_word = find_word(words, r"TOP", min_top=header_scope)
    hdr_recruits = find_word(words, r"RECRUITS\**", min_top=header_scope)
    hdr_coach = None
    for w in words:
        if w["text"].strip(":").lower() == "coach" and hdr_2026 and w["top"] > hdr_2026["top"] + 200:
            hdr_coach = w
            break

    if not (hdr_2026 and hdr_sched):
        return [], "no_header_found"

    left_bound = hdr_2026["left"] - 30
    if hdr_top_word:
        right_bound = hdr_top_word["left"] - 30
    elif hdr_recruits:
        right_bound = hdr_recruits["left"] - 30
    else:
        right_bound = hdr_sched["left"] + hdr_sched["width"] + 900  # fallback guess

    top_start = hdr_sched["top"] + 60
    top_end = hdr_coach["top"] - 20 if hdr_coach else hdr_sched["top"] + 3500

    col_words = [
        w for w in words
        if top_start <= w["top"] <= top_end and left_bound <= w["left"] < right_bound
    ]
    rows = cluster_rows(col_words)

    results = []
    game_num = 0
    for row in rows:
        row_sorted = sorted(row, key=lambda w: w["left"])
        text = " ".join(w["text"] for w in row_sorted)
        text_clean = text.strip(" |:,.")
        if not text_clean or len(text_clean) < 2:
            continue
        if re.fullmatch(r"(team\s*)?information", text_clean, re.I):
            continue  # coach-info sidebar bled into the column
        date = parse_date(text_clean)
        opp, ha, conf = match_opponent(text_clean)
        game_num += 1
        results.append({
            "team": team, "game_number": game_num, "date_raw": date,
            "opponent_raw": text_clean, "opponent_matched": opp,
            "home_away": ha, "match_confidence": conf,
        })
    return results, "ok"

def main():
    all_rows = []
    status_log = []
    for page_num, team in sorted(PAGE_TO_TEAM.items()):
        try:
            rows, status = extract_schedule_for_page(page_num, team)
        except Exception as e:
            rows, status = [], f"error: {e}"
        all_rows.extend(rows)
        status_log.append((team, status, len(rows)))
        print(f"{team:25s} page={page_num:3d} status={status:15s} games={len(rows)}", flush=True)

    fieldnames = ["team", "game_number", "date_raw", "opponent_raw", "opponent_matched", "home_away", "match_confidence"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in all_rows:
            w.writerow(r)
    print(f"\nWrote {len(all_rows)} schedule rows to {OUT_CSV}")

    bad = [s for s in status_log if s[1] != "ok" or s[2] < 8]
    print(f"\nTeams with issues (status!=ok or <8 games found): {len(bad)}")
    for t, s, n in bad:
        print(f"  {t}: {s}, {n} games")

if __name__ == "__main__":
    main()
