#!/usr/bin/env python3
"""
fetch_eia_coal.py — Fetch EIA county-level coal production data and write a wide CSV.

Usage:
    python scripts/fetch_eia_coal.py --api-key YOUR_KEY [--output coal/data/production.csv]

Get a free EIA API key at: https://www.eia.gov/opendata/register.php
The DEMO_KEY also works for this small dataset (~24 requests total).

Data source: EIA Form EIA-7A, /v2/coal/mine-production/
  - Mine-level annual production, aggregated to county level by FIPS code
  - Coverage: 2001–2024
  - Mine types: SUR (surface), UND (underground), REF (refuse, counted in total only)

Output CSV columns:
  geoid,state,county,coal2001,...,coal2024,surface2001,...,surface2024,underground2001,...,underground2024
  - coal = total production (all mine types summed)
  - surface = surface mining (SUR)
  - underground = underground mining (UND)
  - units: short tons
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict

# ---------------------------------------------------------------------------
# State abbreviation → FIPS lookup (lower 48 only)
# ---------------------------------------------------------------------------

STATE_FIPS = {
    "AL": "01", "AZ": "04", "AR": "05", "CA": "06", "CO": "08",
    "CT": "09", "DE": "10", "FL": "12", "GA": "13", "ID": "16",
    "IL": "17", "IN": "18", "IA": "19", "KS": "20", "KY": "21",
    "LA": "22", "ME": "23", "MD": "24", "MA": "25", "MI": "26",
    "MN": "27", "MS": "28", "MO": "29", "MT": "30", "NE": "31",
    "NV": "32", "NH": "33", "NJ": "34", "NM": "35", "NY": "36",
    "NC": "37", "ND": "38", "OH": "39", "OK": "40", "OR": "41",
    "PA": "42", "RI": "44", "SC": "45", "SD": "46", "TN": "47",
    "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53",
    "WV": "54", "WI": "55", "WY": "56",
}

ENDPOINT = "https://api.eia.gov/v2/coal/mine-production/data/"
YEAR_START = 2001
YEAR_END = 2024

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clean_value(raw) -> float:
    if raw is None:
        return 0.0
    s = str(raw).strip().replace(",", "")
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def eia_get_year(api_key: str, year: int) -> list[dict]:
    """Fetch all mine-production records for one year (fits in a single 5000-record page)."""
    params = {
        "api_key": api_key,
        "frequency": "annual",
        "data[0]": "production",
        "start": str(year),
        "end": str(year),
        "length": "5000",
        "offset": "0",
    }
    url = ENDPOINT + "?" + urllib.parse.urlencode(params)
    print(f"  {year} GET {url[:100]}{'...' if len(url) > 100 else ''}", flush=True)

    body = None
    for attempt in range(8):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                body = resp.read().decode("utf-8")
            break
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 404):
                print(f"    -> 0 records (HTTP {exc.code})", flush=True)
                return []
            if exc.code == 429:
                wait = 90  # DEMO_KEY rate limit: ~5 req/min, back off 90s
                print(f"  Rate limited (429) — waiting {wait}s ...", file=sys.stderr, flush=True)
                time.sleep(wait)
                continue
            wait = 10 * (2 ** min(attempt, 4))
            print(f"  ERROR year={year} attempt {attempt+1}: {exc} — retrying in {wait}s", file=sys.stderr, flush=True)
            if attempt == 7:
                raise
            time.sleep(wait)
        except Exception as exc:
            wait = 10 * (2 ** min(attempt, 4))
            print(f"  ERROR year={year} attempt {attempt+1}: {exc} — retrying in {wait}s", file=sys.stderr, flush=True)
            if attempt == 7:
                raise
            time.sleep(wait)

    if body is None:
        print(f"  ERROR: all retry attempts exhausted for {year}, skipping.", file=sys.stderr, flush=True)
        return []
    obj = json.loads(body)
    response = obj.get("response", obj)
    records = response.get("data", [])
    total = int(response.get("total", len(records)))

    if total > 5000:
        # Shouldn't happen for coal, but handle gracefully
        print(f"  WARNING: {total} records, only fetched first 5000. Increase page size if needed.", flush=True)

    print(f"    -> {len(records)} mine records (of {total} total)", flush=True)
    return records


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Fetch EIA county-level coal production data.")
    parser.add_argument("--api-key", default="DEMO_KEY",
                        help="EIA API key (default: DEMO_KEY). Get your own free key at "
                             "https://www.eia.gov/opendata/register.php")
    parser.add_argument("--output", default="coal/data/production.csv",
                        help="Output CSV path (default: coal/data/production.csv)")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)

    cache_path = args.output + ".cache.json"
    if os.path.exists(cache_path):
        print(f"Resuming from cache: {cache_path}", flush=True)
        with open(cache_path, encoding="utf-8") as f:
            cache = json.load(f)
        county_data = defaultdict(dict, cache.get("county_data", {}))
        county_names = dict(cache.get("county_names", {}))
        done_years = set(cache.get("done_years", []))
    else:
        county_data = defaultdict(dict)
        county_names = {}
        done_years = set()

    def save_cache():
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({
                "county_data": dict(county_data),
                "county_names": county_names,
                "done_years": list(done_years),
            }, f)

    years = list(range(YEAR_START, YEAR_END + 1))

    for year in years:
        if year in done_years:
            print(f"[{year}] Skipping (cached)", flush=True)
            continue

        print(f"\n[{year}] Fetching...", flush=True)
        records = eia_get_year(args.api_key, year)

        # Aggregate mine records → county totals
        # mineCountyId = county FIPS code (without state prefix, no leading zeros)
        # stateId = 2-letter state abbreviation
        # mineTypeId = SUR, UND, REF
        county_year: dict[str, dict[str, float]] = defaultdict(
            lambda: {"coal": 0.0, "surface": 0.0, "underground": 0.0}
        )
        county_name_year: dict[str, list] = {}

        for rec in records:
            state_abbr = rec.get("stateId", "").strip().upper()
            county_code = str(rec.get("mineCountyId", "")).strip()
            mine_type = rec.get("mineTypeId", "").strip().upper()
            county_name_raw = rec.get("mineCountyName", "").strip()
            prod_val = clean_value(rec.get("production", 0))

            if state_abbr not in STATE_FIPS:
                continue  # skip AK, HI, territories
            if not county_code or county_code in ("0", "000"):
                continue

            state_fips = STATE_FIPS[state_abbr]
            fips = state_fips + county_code.zfill(3)

            county_year[fips]["coal"] += prod_val
            if mine_type == "SUR":
                county_year[fips]["surface"] += prod_val
            elif mine_type == "UND":
                county_year[fips]["underground"] += prod_val
            # REF (refuse recovery) goes in total only

            if county_name_raw and fips not in county_name_year:
                county_name_year[fips] = [state_abbr, county_name_raw]

        # Merge into main store
        for fips, vals in county_year.items():
            county_data[fips][f"coal{year}"] = vals["coal"]
            county_data[fips][f"surface{year}"] = vals["surface"]
            county_data[fips][f"underground{year}"] = vals["underground"]

        for fips, name_info in county_name_year.items():
            county_names[fips] = name_info

        print(f"  Aggregated {len(county_year)} producing counties", flush=True)
        done_years.add(year)
        save_cache()
        time.sleep(13)  # DEMO_KEY limit: ~5 req/min → wait 13s between requests

    # ---------------------------------------------------------------------------
    # Write CSV
    # ---------------------------------------------------------------------------

    coal_cols = [f"coal{y}" for y in years]
    surface_cols = [f"surface{y}" for y in years]
    underground_cols = [f"underground{y}" for y in years]
    all_value_cols = coal_cols + surface_cols + underground_cols

    all_geoids = sorted(county_data.keys())
    print(f"\nWriting {len(all_geoids)} county rows to {args.output} ...", flush=True)

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["geoid", "state", "county"] + all_value_cols)
        for geoid in all_geoids:
            name_info = county_names.get(geoid, ["", ""])
            state_abbr = name_info[0] if len(name_info) > 0 else ""
            county_nm = name_info[1] if len(name_info) > 1 else ""
            row = [geoid, state_abbr, county_nm]
            for col in all_value_cols:
                row.append(county_data[geoid].get(col, 0.0))
            writer.writerow(row)

    if os.path.exists(cache_path):
        os.remove(cache_path)
        print("Cache removed.", flush=True)

    print("Done.", flush=True)


if __name__ == "__main__":
    main()
