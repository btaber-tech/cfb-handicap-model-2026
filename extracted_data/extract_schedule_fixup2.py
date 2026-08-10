# -*- coding: utf-8 -*-
"""
Second-pass fixup for the 7 teams still failing: North Carolina, Wake
Forest, Oklahoma State, UCF, Bowling Green, Missouri, Vanderbilt.

Root cause: their "2025 RESULTS | 2026 SCHEDULE | TOP 10 RECRUITS" banner is
white text reverse-printed on the team's (light) brand color. Grayscale
conversion washes out the contrast and Tesseract drops the whole banner row
-- so there's no 'SCHEDULE' token to anchor on at all. But the data rows
below the banner (dates, opponents, scores) are plain black-on-white text
and OCR fine.

Fix: don't anchor on the header. Anchor on the reliable "Coach:" line at the
bottom of the box (plain black text, present on every page) for the bottom
edge, and a generous fixed look-back for the top edge. Cluster words into
full-width rows (no column restriction), then split each row into segments
by horizontal gap -- the table is always laid out
results | schedule | recruits, so the middle segment (of 3) is the schedule
column. For rows with only 2 segments (one list ran out early), use the
segment whose date matches -- both keep 'schedule' by position heuristics
documented inline.
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
SCRATCH = r"C:\Users\BenTa\AppData\Local\Temp\claude\C--Users-BenTa-OneDrive-Desktop-College-Football\219ab1a4-16a9-41b1-bed9-02f025818d0f\scratchpad"
OUT_CSV = os.path.join(SCRATCH, "athlon_2026_schedules_fixup2.csv")
LOG_PATH = os.path.join(SCRATCH, "schedule_extract_fixup2_log.txt")
DEBUG_PATH = os.path.join(SCRATCH, "schedule_extract_fixup2_debug.txt")

PAGES = {
    60: "North Carolina", 68: "Wake Forest", 98: "Oklahoma State", 101: "UCF",
    142: "Bowling Green", 186: "Missouri", 193: "Vanderbilt",
}

PAGE_TO_TEAM_FULL = {
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
FBS_TEAMS = sorted(set(PAGE_TO_TEAM_FULL.values()))

MONTH_FIX = {"uct": "oct", "lan": "jan", "aug": "aug", "sept": "sept", "sep": "sept",
             "nov": "nov", "dec": "dec", "jan": "jan", "feb": "feb"}
DATE_RE = re.compile(r"(aug|sept|sep|oct|uct|nov|dec|jan|lan|feb)\.?\s*(\d{1,2})", re.I)

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
        r = csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        for row in r:
            t = (row.get("text") or "").strip()
            if not t:
                continue
            try:
                words.append({"left": int(row["left"]), "top": int(row["top"]),
                              "width": int(row["width"]), "text": t})
            except (ValueError, KeyError, TypeError):
                continue
    os.remove(tsv_path)
    return words

def cluster_rows(words, gap=40):
    words = sorted(words, key=lambda w: w["top"])
    rows, cur, last_top = [], [], None
    for w in words:
        if last_top is not None and w["top"] - last_top > gap:
            rows.append(cur)
            cur = []
        cur.append(w)
        last_top = w["top"]
    if cur:
        rows.append(cur)
    return rows

def split_segments(row_words, gap_px=350):
    row_sorted = sorted(row_words, key=lambda w: w["left"])
    segments = []
    cur = [row_sorted[0]]
    for prev, w in zip(row_sorted, row_sorted[1:]):
        if w["left"] - (prev["left"] + prev["width"]) > gap_px:
            segments.append(cur)
            cur = []
        cur.append(w)
    segments.append(cur)
    return segments

def parse_date(text):
    m = DATE_RE.search(text)
    if not m:
        return ""
    mon = MONTH_FIX.get(m.group(1).lower(), m.group(1).lower())
    return f"{mon.capitalize()}. {m.group(2)}"

def match_opponent(raw):
    cleaned = DATE_RE.sub("", raw)
    away = bool(re.search(r"\bat\b", cleaned, re.I)) or re.search(r"\bat[A-Z]", cleaned)
    neutral = bool(re.search(r"\bvs\.?\b", cleaned, re.I))
    cleaned = re.sub(r"\bat\b", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\bvs\.?\b", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"^[Aa]t(?=[A-Z])", " ", cleaned)
    cleaned = re.sub(r"[|#%$&*.,]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return "", "", 0.0
    side = "away" if away else ("neutral" if neutral else "home")
    matches = difflib.get_close_matches(cleaned, FBS_TEAMS, n=1, cutoff=0.55)
    if matches:
        conf = round(difflib.SequenceMatcher(None, cleaned.lower(), matches[0].lower()).ratio(), 2)
        if conf >= 0.75:
            return matches[0], side, conf
        return "", side, conf
    return "", side, 0.0

def looks_like_score_row(text):
    """RESULTS column rows end in a score like 'W 66-10' / 'L 14-48'."""
    return bool(re.search(r"\b[WL]\b.*\d+-\d+", text, re.I))

def extract(page_num, team, dbg):
    img = render_page(page_num)
    try:
        words = run_tsv(img)
    finally:
        os.remove(img)

    hdr_coach = None
    for w in words:
        if w["text"].strip(":").lower() == "coach":
            hdr_coach = w
            break
    if not hdr_coach:
        return [], "no_coach_anchor"

    # generous look-back window above "Coach:" -- observed gaps ranged
    # ~3300-5800px; use a wide net and just filter out obvious non-table
    # rows (prose paragraphs) via row word-count/shape downstream.
    top_end = hdr_coach["top"] - 20
    top_start = max(0, top_end - 6200)
    band = [w for w in words if top_start <= w["top"] <= top_end and w["left"] < 6900]

    rows = cluster_rows(band)
    dbg.write(f"\n=== {team} page={page_num} coach_top={hdr_coach['top']} "
              f"band=({top_start},{top_end}) rows={len(rows)} ===\n")

    results = []
    game_num = 0
    for row in rows:
        segs = split_segments(row)
        texts = [" ".join(w["text"] for w in seg) for seg in segs]
        dbg.write(f"  row top~{row[0]['top']}: {len(segs)} segs: {texts}\n")

        if len(segs) >= 3:
            sched_text = texts[1]
        elif len(segs) == 2:
            # Ambiguous: results ran out (2 segs = schedule|recruits) or
            # recruits ran out (2 segs = results|schedule). A RESULTS row
            # always has a W/L + score; a SCHEDULE row never does.
            if looks_like_score_row(texts[0]):
                sched_text = texts[1]
            else:
                sched_text = texts[0]
        else:
            continue

        text_clean = sched_text.strip(" |:,.")
        if not text_clean or len(text_clean) < 4:
            continue
        if not DATE_RE.search(text_clean):
            continue  # not a schedule row (e.g. stray prose/photo caption)
        if re.fullmatch(r"(team\s*)?information", text_clean, re.I):
            continue

        date = parse_date(text_clean)
        opp, ha, conf = match_opponent(text_clean)
        game_num += 1
        results.append({
            "team": team, "game_number": game_num, "date_raw": date,
            "opponent_raw": text_clean, "opponent_matched": opp,
            "home_away": ha, "match_confidence": conf,
        })
    status = "ok" if results else "no_rows_matched"
    return results, status

def main():
    all_rows, status_log, log_lines = [], [], []
    with open(DEBUG_PATH, "w", encoding="utf-8") as dbg:
        for page_num, team in sorted(PAGES.items()):
            try:
                rows, status = extract(page_num, team, dbg)
            except Exception as e:
                rows, status = [], f"error: {e}"
            all_rows.extend(rows)
            status_log.append((team, status, len(rows)))
            line = f"{team:25s} page={page_num:3d} status={status:20s} games={len(rows):3d}"
            print(line, flush=True)
            log_lines.append(line)

    fieldnames = ["team", "game_number", "date_raw", "opponent_raw", "opponent_matched", "home_away", "match_confidence"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in all_rows:
            w.writerow(r)
    summary = f"\nWrote {len(all_rows)} schedule rows to {OUT_CSV}"
    print(summary, flush=True)
    log_lines.append(summary)

    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines) + "\n")

if __name__ == "__main__":
    main()
