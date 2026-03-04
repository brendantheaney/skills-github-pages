#!/usr/bin/env python3
"""
fetch_nass.py — Fetch USDA NASS Quick Stats crop data and write two wide CSVs:
  - yields.csv        county-level data (one row per county)
  - state-totals.csv  state-level totals (one row per state)

Usage:
    python scripts/fetch_nass.py --api-key YOUR_KEY [--output farmyields/data/yields.csv]

Requires no third-party packages (stdlib only: urllib, json, csv, argparse).

NASS returns HTTP 413 if a query matches >50,000 records, so county data is fetched
one year at a time (~1,000-3,000 county records each). State data is fetched in one
request per crop×metric (~1,350 records each) using year__GE / year__LE params.
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
# Configuration
# ---------------------------------------------------------------------------

NASS_ENDPOINT = "https://quickstats.nass.usda.gov/api/api_GET/"

CROPS = [
    {"id": "corn",     "commodity_desc": "CORN",     "units": {"prod": "BU",           "yield": "BU / ACRE"}},
    {"id": "soybeans", "commodity_desc": "SOYBEANS", "units": {"prod": "BU",           "yield": "BU / ACRE"}},
    {"id": "wheat",    "commodity_desc": "WHEAT",    "units": {"prod": "BU",           "yield": "BU / ACRE"}},
    {"id": "cotton",   "commodity_desc": "COTTON",   "units": {"prod": "480 LB BALES", "yield": "LB / ACRE"}},
    {"id": "sorghum",  "commodity_desc": "SORGHUM",  "units": {"prod": "BU",           "yield": "BU / ACRE"}},
    {"id": "barley",   "commodity_desc": "BARLEY",   "units": {"prod": "BU",           "yield": "BU / ACRE"}},
    {"id": "oats",     "commodity_desc": "OATS",     "units": {"prod": "BU",           "yield": "BU / ACRE"}},
    {"id": "rice",     "commodity_desc": "RICE",     "units": {"prod": "CWT",          "yield": "LB / ACRE"}},
]

METRICS = [
    {"id": "prod",  "statisticcat_desc": "PRODUCTION"},
    {"id": "yield", "statisticcat_desc": "YIELD"},
]

YEAR_GE = 1997
YEAR_LE = 2023

# Values that NASS uses to suppress confidential data — treat as 0
SUPPRESSED = {"(D)", "(S)", "(NA)", "(Z)", "(L)", "(H)", "(X)"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clean_value(raw: str) -> float:
    """Return a float, treating suppressed / empty strings as 0."""
    raw = raw.strip()
    if not raw or raw in SUPPRESSED:
        return 0.0
    raw = raw.replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return 0.0


def nass_get_year(api_key: str, commodity_desc: str, statisticcat_desc: str, year: int,
                  extra_params: dict = None) -> list[dict]:
    """Fetch all county records for one crop x metric x year, with retry backoff."""
    params = {
        "key": api_key,
        "commodity_desc": commodity_desc,
        "statisticcat_desc": statisticcat_desc,
        "agg_level_desc": "COUNTY",
        "domain_desc": "TOTAL",
        "year": year,
        "format": "JSON",
    }
    if extra_params:
        params.update(extra_params)
    url = NASS_ENDPOINT + "?" + urllib.parse.urlencode(params)
    print(f"  {year} GET {url[:100]}{'...' if len(url) > 100 else ''}", flush=True)

    body = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                body = resp.read().decode("utf-8")
            break  # success
        except urllib.error.HTTPError as exc:
            if exc.code == 400:
                # NASS returns HTTP 400 when a filter combo matches no records
                # (e.g. class_desc=ALL CLASSES for a year that only has
                # class-specific survey rows). Treat as empty — do not retry.
                print(f"    -> 0 records (HTTP 400 — no data for this filter/year)", flush=True)
                return []
            wait = 10 * (2 ** attempt)
            print(f"  ERROR year={year} attempt {attempt+1}: {exc} — retrying in {wait}s", file=sys.stderr, flush=True)
            if attempt == 4:
                raise
            time.sleep(wait)
        except Exception as exc:
            wait = 10 * (2 ** attempt)
            print(f"  ERROR year={year} attempt {attempt+1}: {exc} — retrying in {wait}s", file=sys.stderr, flush=True)
            if attempt == 4:
                raise
            time.sleep(wait)

    data = json.loads(body)

    if "error" in data:
        err = data["error"]
        # "no records found" is not a fatal error — return empty
        if isinstance(err, list) and any("no records" in str(e).lower() for e in err):
            return []
        raise RuntimeError(f"NASS API error: {err}")

    return data.get("data", [])


def nass_get_state(api_key: str, commodity_desc: str, statisticcat_desc: str) -> list[dict]:
    """Fetch all state-level records for one crop×metric across all years (single request)."""
    params = {
        "key": api_key,
        "commodity_desc": commodity_desc,
        "statisticcat_desc": statisticcat_desc,
        "agg_level_desc": "STATE",
        "domain_desc": "TOTAL",
        "year__GE": YEAR_GE,
        "year__LE": YEAR_LE,
        "format": "JSON",
    }
    url = NASS_ENDPOINT + "?" + urllib.parse.urlencode(params)
    print(f"  STATE GET {url[:100]}{'...' if len(url) > 100 else ''}", flush=True)

    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                body = resp.read().decode("utf-8")
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 400:
                print("    -> 0 records (HTTP 400)", flush=True)
                return []
            wait = 10 * (2 ** attempt)
            print(f"  ERROR attempt {attempt+1}: {exc} — retrying in {wait}s", file=sys.stderr, flush=True)
            if attempt == 4:
                raise
            time.sleep(wait)
        except Exception as exc:
            wait = 10 * (2 ** attempt)
            print(f"  ERROR attempt {attempt+1}: {exc} — retrying in {wait}s", file=sys.stderr, flush=True)
            if attempt == 4:
                raise
            time.sleep(wait)

    data = json.loads(body)
    if "error" in data:
        err = data["error"]
        if isinstance(err, list) and any("no records" in str(e).lower() for e in err):
            return []
        raise RuntimeError(f"NASS API error: {err}")
    return data.get("data", [])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Fetch USDA NASS county crop data.")
    parser.add_argument("--api-key", required=True, help="NASS Quick Stats API key")
    parser.add_argument(
        "--output",
        default="farmyields/data/yields.csv",
        help="Output CSV path (default: farmyields/data/yields.csv)",
    )
    parser.add_argument(
        "--state-output",
        default=None,
        help="State totals CSV path (default: same dir as --output, state-totals.csv)",
    )
    args = parser.parse_args()

    state_output = args.state_output or os.path.join(
        os.path.dirname(args.output) or ".", "state-totals.csv"
    )

    years = list(range(YEAR_GE, YEAR_LE + 1))

    # Resume cache: stores completed combos and their data
    cache_path = args.output + ".cache.json"
    if os.path.exists(cache_path):
        print(f"Resuming from cache: {cache_path}", flush=True)
        with open(cache_path, encoding="utf-8") as f:
            cache = json.load(f)
        county_data = defaultdict(dict, {k: v for k, v in cache["county_data"].items()})
        county_names = {k: tuple(v) for k, v in cache["county_names"].items()}
        done_combos = set(cache["done_combos"])
        state_data = defaultdict(dict, {k: v for k, v in cache.get("state_data", {}).items()})
    else:
        county_data: dict[str, dict] = defaultdict(dict)
        county_names: dict[str, tuple[str, str]] = {}
        done_combos: set[str] = set()
        state_data: dict[str, dict] = defaultdict(dict)

    def save_cache():
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({
                "county_data": dict(county_data),
                "county_names": county_names,
                "done_combos": list(done_combos),
                "state_data": dict(state_data),
            }, f)

    total_combos = len(CROPS) * len(METRICS)
    combo_num = 0

    for crop in CROPS:
        for metric in METRICS:
            combo_num += 1
            combo_key = f"{crop['id']}_{metric['id']}"
            label = f"{crop['id']} {metric['id']}"

            if combo_key in done_combos:
                print(f"\n[{combo_num}/{total_combos}] Skipping (cached): {label}", flush=True)
                continue

            print(f"\n[{combo_num}/{total_combos}] Fetching: {label}", flush=True)

            is_wheat = crop["id"] == "wheat"

            for year in years:
                records = nass_get_year(
                    args.api_key,
                    crop["commodity_desc"],
                    metric["statisticcat_desc"],
                    year,
                )
                print(f"    -> {len(records)} records", flush=True)

                # Accumulate: geoid -> value
                # Wheat needs special handling: NASS may return class-specific
                # rows (WINTER/SPRING/DURUM), an ALL CLASSES aggregate, or both.
                # Strategy: if ANY record for a geoid has class_desc=ALL CLASSES,
                # use only that value (it's the authoritative county total).
                # Otherwise sum class-specific prod values / take max yield.
                temp: dict[str, float] = {}       # geoid -> final value
                wheat_all: dict[str, float] = {}  # geoid -> ALL CLASSES value
                wheat_sum: dict[str, float] = {}  # geoid -> class-specific sum/max

                for rec in records:
                    state_fips = rec.get("state_fips_code", "").strip().zfill(2)
                    county_code = rec.get("county_code", "").strip().zfill(3)

                    if county_code in ("000", "998", "999", "") or not state_fips:
                        continue

                    geoid = state_fips + county_code
                    val = clean_value(rec.get("Value", ""))

                    state_alpha = rec.get("state_alpha", "").strip()
                    county_name = rec.get("county_name", "").strip()
                    if state_alpha and county_name:
                        county_names[geoid] = (state_alpha, county_name)

                    if is_wheat:
                        class_desc = rec.get("class_desc", "").strip().upper()
                        if class_desc == "ALL CLASSES":
                            wheat_all[geoid] = val
                        else:
                            if metric["id"] == "prod":
                                wheat_sum[geoid] = wheat_sum.get(geoid, 0.0) + val
                            else:
                                wheat_sum[geoid] = max(wheat_sum.get(geoid, 0.0), val)
                    else:
                        temp[geoid] = val

                # Resolve wheat: prefer ALL CLASSES when present
                if is_wheat:
                    all_geoids_year = set(wheat_all) | set(wheat_sum)
                    for geoid in all_geoids_year:
                        temp[geoid] = wheat_all[geoid] if geoid in wheat_all else wheat_sum[geoid]

                field = f"{combo_key}{year}"
                for geoid, val in temp.items():
                    county_data[geoid][field] = val

                time.sleep(0.25)  # be polite to the API

            done_combos.add(combo_key)
            save_cache()
            print(f"  Saved cache ({len(done_combos)}/{total_combos} combos done)", flush=True)

    # ---------------------------------------------------------------------------
    # Phase 2: State-level totals (one request per crop×metric, all years at once)
    # ---------------------------------------------------------------------------

    print(f"\n=== Fetching state-level totals ===", flush=True)
    state_combo_num = 0

    for crop in CROPS:
        for metric in METRICS:
            state_combo_num += 1
            state_key = f"state_{crop['id']}_{metric['id']}"
            label = f"{crop['id']} {metric['id']}"

            if state_key in done_combos:
                print(f"[{state_combo_num}/{total_combos}] Skipping (cached): state {label}", flush=True)
                continue

            print(f"\n[{state_combo_num}/{total_combos}] Fetching state totals: {label}", flush=True)

            is_wheat = crop["id"] == "wheat"
            all_records = nass_get_state(args.api_key, crop["commodity_desc"], metric["statisticcat_desc"])
            # Filter to the target unit only — NASS state records mix grain/silage/dollar
            # variants (e.g. corn returns BU, TONS for silage, $ for value). We want
            # only the unit that matches our visualizer's unit for that crop×metric.
            expected_unit = crop["units"][metric["id"]]
            records = [r for r in all_records if r.get("unit_desc", "").strip() == expected_unit]
            print(f"    -> {len(records)} records (of {len(all_records)}, unit={expected_unit!r})", flush=True)

            combo_key = f"{crop['id']}_{metric['id']}"
            # State-level NASS records mix ALL CLASSES aggregates with class-specific
            # rows (e.g. rice: ALL CLASSES + LONG GRAIN + MEDIUM GRAIN + SHORT GRAIN).
            # Apply the same dedup as county-level wheat: prefer ALL CLASSES when
            # present; otherwise sum class-specific prod values / max yield values.
            st_all: dict[tuple, float] = {}  # (state_alpha, year) -> ALL CLASSES value
            st_sum: dict[tuple, float] = {}  # (state_alpha, year) -> class-specific sum/max

            for rec in records:
                state_alpha = rec.get("state_alpha", "").strip()
                try:
                    year = int(rec.get("year", 0))
                except (ValueError, TypeError):
                    continue
                if not state_alpha or year < YEAR_GE or year > YEAR_LE:
                    continue

                val = clean_value(rec.get("Value", ""))
                k = (state_alpha, year)
                class_desc = rec.get("class_desc", "").strip().upper()

                if class_desc == "ALL CLASSES":
                    st_all[k] = val
                else:
                    if metric["id"] == "prod":
                        st_sum[k] = st_sum.get(k, 0.0) + val
                    else:
                        st_sum[k] = max(st_sum.get(k, 0.0), val)

            st_val: dict[tuple, float] = {}
            for k in set(st_all) | set(st_sum):
                st_val[k] = st_all[k] if k in st_all else st_sum[k]

            for (state_alpha, year), val in st_val.items():
                state_data[state_alpha][f"{combo_key}{year}"] = val

            done_combos.add(state_key)
            save_cache()
            print(f"  Saved cache.", flush=True)
            time.sleep(0.5)

    # ---------------------------------------------------------------------------
    # Build column list (shared by both output CSVs)
    # ---------------------------------------------------------------------------

    value_cols = []
    for crop in CROPS:
        for metric in METRICS:
            for yr in years:
                value_cols.append(f"{crop['id']}_{metric['id']}{yr}")

    # Write county CSV
    all_geoids = sorted(county_data.keys())
    print(f"\nWriting {len(all_geoids)} county rows to {args.output} ...", flush=True)
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["geoid", "state", "county"] + value_cols)
        for geoid in all_geoids:
            state_alpha, county_name = county_names.get(geoid, ("", ""))
            row = [geoid, state_alpha, county_name]
            for col in value_cols:
                row.append(county_data[geoid].get(col, 0.0))
            writer.writerow(row)

    # Write state-totals CSV
    all_states = sorted(state_data.keys())
    print(f"Writing {len(all_states)} state rows to {state_output} ...", flush=True)
    with open(state_output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["state"] + value_cols)
        for state_alpha in all_states:
            row = [state_alpha]
            for col in value_cols:
                row.append(state_data[state_alpha].get(col, 0.0))
            writer.writerow(row)

    print("Done.", flush=True)


if __name__ == "__main__":
    main()
