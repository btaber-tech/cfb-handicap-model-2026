"""Sportsbook (DraftKings, via sportsbettingdime.com) preseason win-total lines,
web-sourced 2026-08-11. 2025 is a full ~134-team table; 2023/2024 pages only
surfaced Power-conference teams (G5 rows were missing from the fetch), so
those two seasons are Power-conference-only samples -- noted explicitly in
the edge-test output, not silently treated as complete.
"""

LINES_2025 = {
    "Air Force": 5.5, "Akron": 4.5, "Alabama": 9.5, "Appalachian State": 5.5, "Arizona": 4.5,
    "Arizona State": 8.5, "Arkansas": 5.5, "Arkansas State": 5.5, "Auburn": 7.5, "Ball State": 3.5,
    "Baylor": 7.5, "Boise State": 9.5, "Boston College": 5.5, "Bowling Green": 6.5, "BYU": 6.5,
    "California": 5.5, "Central Michigan": 5.5, "Charlotte": 2.5, "Cincinnati": 6.5, "Clemson": 9.5,
    "Coastal Carolina": 5.5, "Colorado": 6.5, "Colorado State": 6.5, "Delaware": 4.5, "Duke": 6.5,
    "East Carolina": 6.5, "Eastern Michigan": 4.5, "FIU": 5.5, "Florida": 7.5, "Florida Atlantic": 4.5,
    "Florida State": 6.5, "Fresno State": 6.5, "Georgia": 9.5, "Georgia Southern": 7.5,
    "Georgia State": 3.5, "Georgia Tech": 7.5, "Hawaii": 6.5, "Houston": 6.5, "Illinois": 7.5,
    "Indiana": 8.5, "Iowa": 7.5, "Iowa State": 7.5, "Jacksonville State": 5.5, "James Madison": 7.5,
    "Kansas": 6.5, "Kansas State": 8.5, "Kennesaw State": 3.5, "Kent State": 1.5, "Kentucky": 4.5,
    "Liberty": 9.5, "Louisiana": 7.5, "Louisiana Tech": 5.5, "Louisville": 8.5, "LSU": 8.5,
    "Marshall": 5.5, "Maryland": 4.5, "Memphis": 8.5, "Miami": 9.5, "Miami (OH)": 6.5, "Michigan": 8.5,
    "Michigan State": 5.5, "Middle Tennessee": 4.5, "Minnesota": 7.5, "Mississippi State": 3.5,
    "Missouri": 7.5, "Missouri State": 4.5, "Navy": 8.5, "NC State": 6.5, "Nebraska": 7.5, "Nevada": 3.5,
    "New Mexico": 3.5, "New Mexico State": 4.5, "North Carolina": 7.5, "North Texas": 6.5,
    "Northern Illinois": 6.5, "Northwestern": 3.5, "Notre Dame": 10.5, "Ohio": 7.5, "Ohio State": 10.5,
    "Oklahoma": 6.5, "Oklahoma State": 4.5, "Old Dominion": 6.5, "Ole Miss": 8.5, "Oregon": 10.5,
    "Oregon State": 6.5, "Penn State": 10.5, "Pittsburgh": 6.5, "Purdue": 2.5, "Rice": 3.5,
    "Rutgers": 5.5, "Sam Houston": 4.5, "San Diego State": 4.5, "San Jose State": 7.5, "SMU": 8.5,
    "South Alabama": 7.5, "South Carolina": 7.5, "South Florida": 6.5, "Southern Miss": 4.5,
    "Stanford": 3.5, "TCU": 6.5, "Temple": 3.5, "Tennessee": 8.5, "Texas": 9.5, "Texas A&M": 8.5,
    "Texas State": 7.5, "Texas Tech": 8.5, "Toledo": 8.5, "Troy": 5.5, "Tulane": 8.5, "Tulsa": 2.5,
    "UAB": 4.5, "UCF": 5.5, "UCLA": 5.5, "UConn": 7.5, "UL Monroe": 4.5, "UMass": 3.5, "UNLV": 8.5,
    "USC": 7.5, "Utah": 7.5, "Utah State": 4.5, "UTEP": 5.5, "UTSA": 7.5, "Vanderbilt": 5.5,
    "Virginia": 6.5, "Virginia Tech": 6.5, "Wake Forest": 4.5, "Washington": 7.5,
    "Washington State": 5.5, "West Virginia": 5.5, "Western Kentucky": 7.5, "Western Michigan": 5.5,
    "Wisconsin": 5.5, "Wyoming": 5.5,
}

# Power-conference-only (G5 rows were absent from the fetched page)
LINES_2024 = {
    "Alabama": 9.5, "Arizona": 8, "Arizona State": 4.5, "Arkansas": 4.5, "Auburn": 7.5, "Baylor": 5.5,
    "Boston College": 5, "BYU": 4.5, "California": 6, "Cincinnati": 5, "Clemson": 9.5, "Colorado": 5.5,
    "Duke": 5.5, "Florida": 4.5, "Florida State": 9.5, "Georgia": 10.5, "Georgia Tech": 5,
    "Houston": 3.5, "Illinois": 5.5, "Indiana": 5.5, "Iowa": 8, "Iowa State": 7.5, "Kansas": 8,
    "Kansas State": 9.5, "Kentucky": 6.5, "Louisville": 8.5, "LSU": 9, "Maryland": 6.5, "Miami": 9,
    "Michigan": 9, "Michigan State": 5, "Minnesota": 5, "Mississippi State": 4, "Missouri": 9.5,
    "Nebraska": 7.5, "North Carolina": 7.5, "NC State": 8.5, "Northwestern": 4.5, "Notre Dame": 10,
    "Ohio State": 10.5, "Oklahoma": 7.5, "Oklahoma State": 8, "Ole Miss": 9.5, "Oregon": 10.5,
    "Oregon State": 7.5, "Penn State": 10.5, "Pittsburgh": 5.5, "Purdue": 4.5, "Rutgers": 4.5,
    "South Carolina": 5.5, "Stanford": 3.5, "Syracuse": 7, "TCU": 7.5, "Tennessee": 8.5, "Texas": 10.5,
    "Texas A&M": 8.5, "Texas Tech": 7.5, "UCF": 7.5, "UCLA": 5, "USC": 7, "Utah": 9.5, "Vanderbilt": 3,
    "Virginia": 4.5, "Virginia Tech": 8.5, "Wake Forest": 4.5, "Washington": 6.5,
    "Washington State": 7.5, "West Virginia": 6.5, "Wisconsin": 7,
}

# Power-conference-only (G5 rows were absent from the fetched page)
LINES_2023 = {
    "Alabama": 10.5, "Arizona": 5, "Arizona State": 5, "Arkansas": 7, "Auburn": 6.5, "Baylor": 7,
    "Boston College": 5.5, "BYU": 5.5, "California": 5, "Cincinnati": 5.5, "Clemson": 10,
    "Colorado": 3.5, "Duke": 6.5, "Florida": 5.5, "Florida State": 10, "Georgia": 11.5,
    "Georgia Tech": 4.5, "Houston": 4.5, "Illinois": 6.5, "Indiana": 3.5, "Iowa": 8, "Iowa State": 5.5,
    "Kansas": 6.5, "Kansas State": 8.5, "Kentucky": 7, "Louisville": 8, "LSU": 9.5, "Maryland": 7,
    "Miami": 7.5, "Michigan": 10.5, "Michigan State": 5.5, "Minnesota": 7, "Mississippi State": 6.5,
    "Missouri": 6.5, "Nebraska": 6, "North Carolina": 8, "NC State": 6.5, "Northwestern": 3,
    "Notre Dame": 8.5, "Ohio State": 10.5, "Oklahoma": 9.5, "Oklahoma State": 6.5, "Ole Miss": 7.5,
    "Oregon": 9.5, "Oregon State": 8.5, "Penn State": 9.5, "Pittsburgh": 6.5, "Purdue": 5.5,
    "Rutgers": 4.5, "South Carolina": 6.5, "Stanford": 3, "Syracuse": 6.5, "TCU": 7.5, "Tennessee": 9.5,
    "Texas": 9.5, "Texas A&M": 8, "Texas Tech": 7.5, "UCF": 6.5, "UCLA": 8.5, "USC": 10, "Utah": 8.5,
    "Vanderbilt": 3.5, "Virginia": 3.5, "Virginia Tech": 5, "Wake Forest": 6, "Washington": 9.5,
    "Washington State": 6.5, "West Virginia": 4.5, "Wisconsin": 8.5,
}

LINES_2026 = {
    "Air Force": 7.5, "Akron": 4.5, "Alabama": 8.5, "Appalachian State": 5.5, "Arizona": 7.5,
    "Arizona State": 6.5, "Arkansas": 4.5, "Arkansas State": 6.5, "Army": 7.5, "Auburn": 6.5,
    "BYU": 8.5, "Ball State": 3.5, "Baylor": 6.5, "Boise State": 7.5, "Boston College": 3.5,
    "Bowling Green": 4.5, "Buffalo": 5.5, "California": 6.5, "Central Michigan": 6.5, "Charlotte": 2.5,
    "Cincinnati": 5.5, "Clemson": 7.5, "Coastal Carolina": 4.5, "Colorado": 4.5, "Colorado State": 3.5,
    "Delaware": 6.5, "Duke": 5.5, "East Carolina": 7.5, "Eastern Michigan": 5.5, "FIU": 6.5,
    "Florida": 7.5, "Florida Atlantic": 5.5, "Florida State": 6.5, "Fresno State": 6.5, "Georgia": 9.5,
    "Georgia Southern": 4.5, "Georgia State": 4.5, "Georgia Tech": 6.5, "Hawaii": 7.5, "Houston": 8.5,
    "Illinois": 7.5, "Indiana": 10.5, "Iowa": 7.5, "Iowa State": 4.5, "Jacksonville State": 7.5,
    "James Madison": 8.5, "Kansas": 5.5, "Kansas State": 8.5, "Kennesaw State": 6.5, "Kent State": 3.5,
    "Kentucky": 4.5, "LSU": 8.5, "Liberty": 8.5, "Louisiana": 7.5, "Louisiana Tech": 5.5,
    "Louisville": 8.5, "Marshall": 7.5, "Maryland": 5.5, "Memphis": 7.5, "Miami": 10.5,
    "Miami (OH)": 7.5, "Michigan": 8.5, "Michigan State": 4.5, "Middle Tennessee": 3.5,
    "Minnesota": 6.5, "Mississippi State": 4.5, "Missouri": 6.5, "Missouri State": 4.5, "NC State": 7.5,
    "Navy": 7.5, "Nebraska": 6.5, "Nevada": 4.5, "New Mexico": 7.5, "New Mexico State": 4.5,
    "North Carolina": 4.5, "North Texas": 5.5, "Northern Illinois": 3.5, "Northwestern": 5.5,
    "Notre Dame": 11.5, "Ohio": 6.5, "Ohio State": 9.5, "Oklahoma": 7.5, "Oklahoma State": 6.5,
    "Old Dominion": 7.5, "Ole Miss": 7.5, "Oregon": 10.5, "Oregon State": 4.5, "Penn State": 8.5,
    "Pittsburgh": 7.5, "Purdue": 3.5, "Rice": 3.5, "Rutgers": 4.5, "SMU": 8.5, "Sacramento State": 4.5,
    "Sam Houston": 3.5, "San Diego State": 6.5, "San Jose State": 4.5, "South Alabama": 5.5,
    "South Carolina": 6.5, "South Florida": 8.5, "Southern Miss": 3.5, "Stanford": 3.5,
    "Syracuse": 4.5, "TCU": 6.5, "Temple": 5.5, "Tennessee": 7.5, "Texas": 9.5, "Texas A&M": 8.5,
    "Texas State": 6.5, "Texas Tech": 10.5, "Toledo": 7.5, "Troy": 6.5, "Tulane": 7.5, "Tulsa": 5.5,
    "UAB": 3.5, "UCF": 5.5, "UCLA": 6.5, "UConn": 5.5, "UL Monroe": 3.5, "UMass": 2.5, "UNLV": 7.5,
    "USC": 8.5, "UTEP": 3.5, "UTSA": 7.5, "Utah": 8.5, "Utah State": 4.5, "Vanderbilt": 5.5,
    "Virginia": 7.5, "Virginia Tech": 6.5, "Wake Forest": 5.5, "Washington": 7.5,
    "Washington State": 4.5, "West Virginia": 5.5, "Western Kentucky": 6.5, "Western Michigan": 7.5,
    "Wisconsin": 6.5, "Wyoming": 5.5,
}

# Aliases: market-table name -> internal CFBD team-season name
MARKET_TO_INTERNAL = {
    "North Carolina State": "NC State",
    "San Jose State": "San José State",
}
