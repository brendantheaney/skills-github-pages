#!/usr/bin/env python3
"""
fetch_msha_coal.py — Download MSHA mine data, aggregate coal production to
county level, and write a wide-format CSV suitable for the coal/ visualizer.

Usage:
    python scripts/fetch_msha_coal.py [--output coal/data/production.csv]

No API key needed — MSHA data is publicly available without authentication.
Downloads two zip files and caches them in a local cache directory.

Data sources (updated weekly by MSHA):
  Mines (metadata + county FIPS):
    https://arlweb.msha.gov/OpenGovernmentData/DataSets/Mines.zip
  Employment/Production (yearly, by mine × subunit):
    https://arlweb.msha.gov/OpenGovernmentData/DataSets/MinesProdYearly.zip

Join strategy:
  MinesProdYearly.MINE_ID → Mines.MINE_ID → Mines.FIPS_CNTY_CD
  Aggregate COAL_PRODUCTION (short tons) by county FIPS + calendar year.
  Only coal mines (COAL_METAL_IND == 'C') are included.

Year range: 2000–2023 (coverage of the flat files).
"""

import argparse
import csv
import io
import os
import sys
import urllib.error
import urllib.request
import zipfile
from collections import defaultdict

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

YEAR_START = 2000
YEAR_END = 2023
YEARS = list(range(YEAR_START, YEAR_END + 1))

MINES_URL = "https://arlweb.msha.gov/OpenGovernmentData/DataSets/Mines.zip"
PROD_URL = "https://arlweb.msha.gov/OpenGovernmentData/DataSets/MinesProdYearly.zip"

# EIA Annual Coal Report national totals (million short tons) for rough validation.
# Source: EIA Annual Coal Reports, Table 1.
# Used to sanity-check the aggregated data; tolerance is ±15%.
EIA_NATIONAL_TOTALS_MST = {
    2000: 1074.0,
    2001: 1128.0,
    2002: 1094.0,
    2003: 1072.0,
    2004: 1113.0,
    2005: 1131.0,
    2006: 1163.0,
    2007: 1146.0,
    2008: 1172.0,
    2009: 1075.0,
    2010: 1085.0,
    2011: 1096.0,
    2012: 1016.0,
    2013: 985.0,
    2014: 1000.0,
    2015: 897.0,
    2016: 729.0,
    2017: 775.0,
    2018: 756.0,
    2019: 706.0,
    2020: 536.0,
    2021: 577.0,
    2022: 593.0,
    2023: 578.0,
}

# State FIPS → 2-letter abbreviation (for county name lookup fallback)
STATE_FIPS_TO_ABBR = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO",
    "09": "CT", "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI",
    "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY",
    "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN",
    "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
    "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH",
    "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD",
    "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA",
    "54": "WV", "55": "WI", "56": "WY",
}


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

def download_zip(url: str, cache_path: str) -> bytes:
    """Download url to cache_path if not already cached; return raw bytes."""
    if os.path.exists(cache_path):
        print(f"  [cache] {os.path.basename(cache_path)}", flush=True)
        with open(cache_path, "rb") as f:
            return f.read()

    print(f"  Downloading {url} ...", flush=True)
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "fetch_msha_coal/1.0"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
            with open(cache_path, "wb") as f:
                f.write(data)
            print(f"  Downloaded {len(data):,} bytes → {cache_path}", flush=True)
            return data
        except Exception as exc:
            wait = 2 ** (attempt + 1)
            print(f"  ERROR attempt {attempt+1}: {exc} — retrying in {wait}s", flush=True)
            if attempt == 4:
                raise
            import time
            time.sleep(wait)


def read_csv_from_zip(zip_bytes: bytes, filename_hint: str) -> tuple[list[str], list[list[str]]]:
    """
    Open a zip archive from bytes, find the first .txt or .csv file whose
    name contains filename_hint (case-insensitive), and parse it as a
    delimited file (auto-detects | or , delimiter).

    Returns (headers, rows) where headers are lowercase stripped column names.
    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        target = None
        for n in names:
            if filename_hint.lower() in n.lower() and (n.endswith(".txt") or n.endswith(".csv")):
                target = n
                break
        if target is None:
            # Fall back to first .txt or .csv file
            for n in names:
                if n.endswith(".txt") or n.endswith(".csv"):
                    target = n
                    break
        if target is None:
            raise ValueError(f"No .txt/.csv file found in zip. Contents: {names}")

        print(f"  Reading {target} from zip ...", flush=True)
        raw = zf.read(target)

    # Detect encoding (try utf-8-sig first, fall back to latin-1)
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    # Detect delimiter: use the first line
    first_line = text.split("\n")[0]
    if first_line.count("|") > first_line.count(","):
        delimiter = "|"
    else:
        delimiter = ","

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows_raw = list(reader)

    if not rows_raw:
        raise ValueError("Empty file")

    headers = [h.strip().lower() for h in rows_raw[0]]
    rows = [[cell.strip() for cell in r] for r in rows_raw[1:] if any(c.strip() for c in r)]

    return headers, rows


# ---------------------------------------------------------------------------
# Column name resolution
# ---------------------------------------------------------------------------

def find_col(headers: list[str], *candidates: str) -> int:
    """Return the index of the first candidate found in headers (case-insensitive)."""
    lc_headers = [h.lower() for h in headers]
    for c in candidates:
        try:
            return lc_headers.index(c.lower())
        except ValueError:
            continue
    raise KeyError(f"None of {candidates} found in headers: {headers}")


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_mines(zip_bytes: bytes) -> dict:
    """
    Parse Mines.zip → dict[mine_id_str → {fips, state, county}]
    Only coal mines (COAL_METAL_IND == 'C' or MINE_TYPE contains 'Coal').
    """
    headers, rows = read_csv_from_zip(zip_bytes, "Mines")

    try:
        i_id = find_col(headers, "mine_id", "mineid")
        i_type_ind = find_col(headers, "coal_metal_ind", "coalmetalind", "mine_type_ind")
    except KeyError:
        i_type_ind = None
        i_id = find_col(headers, "mine_id", "mineid")

    try:
        i_mine_type = find_col(headers, "mine_type", "minetype")
    except KeyError:
        i_mine_type = None

    i_fips = find_col(headers, "fips_cnty_cd", "fips_cnty", "fips_county_cd", "county_fips")
    i_state = find_col(headers, "bom_state_cd", "state_abbr", "state_cd", "state")
    try:
        i_county = find_col(headers, "county_nm", "county_name", "cnty_nm")
    except KeyError:
        i_county = None

    mine_meta = {}
    skipped_non_coal = 0
    skipped_bad_fips = 0

    for row in rows:
        if len(row) <= max(i_id, i_fips, i_state):
            continue

        mine_id = row[i_id].strip().zfill(7)

        # Coal filter
        is_coal = False
        if i_type_ind is not None and i_type_ind < len(row):
            is_coal = row[i_type_ind].strip().upper() == "C"
        if not is_coal and i_mine_type is not None and i_mine_type < len(row):
            is_coal = "coal" in row[i_mine_type].strip().lower()
        if not is_coal:
            skipped_non_coal += 1
            continue

        # FIPS
        raw_fips = row[i_fips].strip()
        if not raw_fips or raw_fips in ("00000", "99999", ""):
            skipped_bad_fips += 1
            continue
        fips = raw_fips.zfill(5)
        if len(fips) != 5 or not fips.isdigit():
            skipped_bad_fips += 1
            continue

        state = row[i_state].strip() if i_state < len(row) else ""
        # Fall back to deriving state from FIPS if needed
        if not state:
            state = STATE_FIPS_TO_ABBR.get(fips[:2], "")

        county = ""
        if i_county is not None and i_county < len(row):
            county = row[i_county].strip()

        mine_meta[mine_id] = {"fips": fips, "state": state, "county": county}

    print(f"  Parsed {len(mine_meta)} coal mines "
          f"(skipped {skipped_non_coal} non-coal, {skipped_bad_fips} bad FIPS)", flush=True)
    return mine_meta


def parse_production(zip_bytes: bytes, mine_meta: dict, years: list[int]) -> dict:
    """
    Parse MinesProdYearly.zip → dict[(fips, year) → total_short_tons]
    Sums COAL_PRODUCTION across all subunit codes per mine per year.
    """
    headers, rows = read_csv_from_zip(zip_bytes, "MinesProd")

    i_id = find_col(headers, "mine_id", "mineid")
    i_year = find_col(headers, "cal_yr", "calendar_yr", "year", "cal_year")
    i_prod = find_col(headers, "coal_production", "coal_prod", "production")

    year_set = set(years)
    county_year_prod = defaultdict(float)
    mine_year_mine_prod = defaultdict(float)  # (mine_id, year) → sum across subunits

    skipped_no_meta = 0
    skipped_year = 0
    zero_prod = 0

    for row in rows:
        if len(row) <= max(i_id, i_year, i_prod):
            continue

        mine_id = row[i_id].strip().zfill(7)
        if mine_id not in mine_meta:
            skipped_no_meta += 1
            continue

        try:
            year = int(row[i_year].strip())
        except (ValueError, TypeError):
            continue

        if year not in year_set:
            skipped_year += 1
            continue

        raw_prod = row[i_prod].strip().replace(",", "")
        try:
            prod = float(raw_prod) if raw_prod else 0.0
        except ValueError:
            prod = 0.0

        if prod == 0.0:
            zero_prod += 1
            continue

        mine_year_mine_prod[(mine_id, year)] += prod

    # Aggregate mine-year totals → county-year totals
    for (mine_id, year), total in mine_year_mine_prod.items():
        fips = mine_meta[mine_id]["fips"]
        county_year_prod[(fips, year)] += total

    print(f"  Parsed {len(mine_year_mine_prod)} mine-year records → "
          f"{len(county_year_prod)} county-year totals", flush=True)
    print(f"  (skipped {skipped_no_meta} rows with no coal-mine metadata, "
          f"{skipped_year} outside year range, {zero_prod} zero-production rows)", flush=True)

    return county_year_prod


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(county_year_prod: dict, years: list[int]) -> bool:
    """
    Print national totals per year and compare to EIA benchmarks.
    Returns True if all years pass the ±20% tolerance check.
    """
    print("\n--- Validation: national production totals ---", flush=True)
    print(f"{'Year':>6}  {'MSHA (MSt)':>12}  {'EIA (MSt)':>10}  {'Δ%':>7}  Status", flush=True)
    print("-" * 55, flush=True)

    all_ok = True
    tolerance = 0.20  # 20% tolerance

    for year in years:
        msha_total = sum(v for (f, y), v in county_year_prod.items() if y == year) / 1e6
        eia = EIA_NATIONAL_TOTALS_MST.get(year)

        if eia is not None and eia > 0:
            delta_pct = (msha_total - eia) / eia * 100
            ok = abs(delta_pct) <= tolerance * 100
            status = "OK" if ok else "WARN"
            if not ok:
                all_ok = False
            print(f"  {year}  {msha_total:12.1f}  {eia:10.1f}  {delta_pct:+7.1f}%  {status}",
                  flush=True)
        else:
            print(f"  {year}  {msha_total:12.1f}  {'n/a':>10}  {'':>8}  --", flush=True)

    if not all_ok:
        print("\nWARNING: Some years deviate >20% from EIA benchmarks.", flush=True)
        print("This may indicate missing data or a column mismatch.", flush=True)
        print("Check the CSV carefully before publishing.", flush=True)
    else:
        print("\nAll years within 20% of EIA benchmarks. Data looks good.", flush=True)

    return all_ok


def print_top_counties(county_year_prod: dict, mine_meta: dict, years: list[int], n: int = 10):
    """Print the top-N counties by cumulative production."""
    cumulative = defaultdict(float)
    for (fips, year), val in county_year_prod.items():
        cumulative[fips] += val

    top = sorted(cumulative.items(), key=lambda x: -x[1])[:n]

    print(f"\n--- Top {n} counties by cumulative production ({years[0]}–{years[-1]}) ---", flush=True)
    # Build fips → (state, county) from mine_meta
    fips_names = {}
    for meta in mine_meta.values():
        f = meta["fips"]
        if f not in fips_names and meta["county"]:
            fips_names[f] = (meta["state"], meta["county"])

    for rank, (fips, total_st) in enumerate(top, 1):
        state, county = fips_names.get(fips, ("?", "?"))
        print(f"  {rank:2}. {fips}  {county}, {state}  — {total_st/1e6:.1f} million short tons",
              flush=True)


# ---------------------------------------------------------------------------
# Write CSV
# ---------------------------------------------------------------------------

def write_csv(output_path: str, county_year_prod: dict, mine_meta: dict, years: list[int]):
    """Write wide-format CSV: geoid, state, county, coal{year}, ..."""

    # Build fips → (state, county) — take the most-common county name per fips
    fips_info: dict[str, dict] = {}
    for meta in mine_meta.values():
        f = meta["fips"]
        if f not in fips_info:
            fips_info[f] = meta
        elif not fips_info[f]["county"] and meta["county"]:
            fips_info[f] = meta

    # Collect all fips that have any production in range
    producing_fips = sorted({f for f, y in county_year_prod})

    print(f"\nWriting {len(producing_fips)} county rows to {output_path} ...", flush=True)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    year_cols = [f"coal{y}" for y in years]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["geoid", "state", "county"] + year_cols)

        for fips in producing_fips:
            info = fips_info.get(fips, {"fips": fips, "state": "", "county": ""})
            state = info["state"]
            county = info["county"]
            if not state:
                state = STATE_FIPS_TO_ABBR.get(fips[:2], "")

            row = [fips, state, county]
            for year in years:
                val = county_year_prod.get((fips, year), 0.0)
                row.append(int(val) if val == int(val) else round(val, 1))
            writer.writerow(row)

    print(f"Done. {len(producing_fips)} counties, {len(years)} years "
          f"({year_cols[0]}–{year_cols[-1]}).", flush=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Fetch MSHA coal production data and write county-level CSV."
    )
    parser.add_argument(
        "--output",
        default="coal/data/production.csv",
        help="Output CSV path (default: coal/data/production.csv)",
    )
    parser.add_argument(
        "--cache-dir",
        default=".msha_cache",
        help="Directory for cached zip files (default: .msha_cache)",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip EIA validation check",
    )
    args = parser.parse_args()

    os.makedirs(args.cache_dir, exist_ok=True)

    # 1. Download
    print("=== Step 1: Download MSHA datasets ===", flush=True)
    mines_zip = download_zip(MINES_URL, os.path.join(args.cache_dir, "Mines.zip"))
    prod_zip = download_zip(PROD_URL, os.path.join(args.cache_dir, "MinesProdYearly.zip"))

    # 2. Parse mines metadata
    print("\n=== Step 2: Parse mine metadata ===", flush=True)
    mine_meta = parse_mines(mines_zip)

    # 3. Parse production
    print("\n=== Step 3: Parse production data ===", flush=True)
    county_year_prod = parse_production(prod_zip, mine_meta, YEARS)

    # 4. Validate
    if not args.no_validate:
        print("\n=== Step 4: Validate ===", flush=True)
        validate(county_year_prod, YEARS)
        print_top_counties(county_year_prod, mine_meta, YEARS)
    else:
        print("\n=== Step 4: Validation skipped ===", flush=True)

    # 5. Write CSV
    print("\n=== Step 5: Write CSV ===", flush=True)
    write_csv(args.output, county_year_prod, mine_meta, YEARS)


if __name__ == "__main__":
    main()
