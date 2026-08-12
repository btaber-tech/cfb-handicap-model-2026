"""
Shared CollegeFootballData.com (CFBD) API fetch helper.

Handles a Windows-local TLS quirk found earlier in this project: CFBD's
cert fails Windows Python's default certificate-revocation check
(`requests`/urllib3 throw CERTIFICATE_VERIFY_FAILED there), while plain
`requests` works fine on Linux/cloud. `cfbd_get` tries `requests` first and
falls back to `curl --ssl-no-revoke` only if that specific SSL error shows
up, so this same script works unmodified on this machine and in the cloud
automation environment.
"""
import datetime
import json
import os
import subprocess
import urllib.parse

import requests

BASE_URL = "https://api.collegefootballdata.com"


def load_api_key(key_path=None):
    if key_path is None:
        key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cfbd_api_key")
    env_key = os.environ.get("CFBD_API_KEY")
    if env_key:
        return env_key.strip()
    with open(key_path, encoding="utf-8") as f:
        return f.read().strip()


def cfbd_get(endpoint, params=None, api_key=None):
    """GET a CFBD endpoint (e.g. '/games'), returning parsed JSON."""
    if api_key is None:
        api_key = load_api_key()
    url = BASE_URL + endpoint
    headers = {"Authorization": f"Bearer {api_key}", "accept": "application/json"}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.SSLError:
        query = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None})
        full_url = url + (f"?{query}" if query else "")
        result = subprocess.run(
            ["curl", "--ssl-no-revoke", "-s",
             "-H", f"Authorization: Bearer {api_key}",
             "-H", "accept: application/json", full_url],
            capture_output=True, check=True,
        )
        return json.loads(result.stdout.decode("utf-8"))


def cfbd_get_save(endpoint, out_path, params=None, api_key=None):
    data = cfbd_get(endpoint, params=params, api_key=api_key)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return data


def get_current_week(year, api_key=None, today=None):
    """
    Use CFBD's /calendar?year=Y to find the regular-season week whose game
    range contains (or is the next one after) today. Returns an int week
    number, or None if the calendar isn't published yet for that year or
    the regular season is already over.
    """
    if today is None:
        today = datetime.date.today()
    calendar = cfbd_get("/calendar", params={"year": year}, api_key=api_key)
    reg = sorted((w for w in calendar if w.get("seasonType") == "regular"), key=lambda w: w["week"])
    for w in reg:
        last = datetime.date.fromisoformat(w["lastGameStart"][:10])
        if today <= last:
            return w["week"]
    return None
