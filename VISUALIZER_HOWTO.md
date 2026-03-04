# How to Build a New Data Visualizer

This document explains how the `farmyields/` tool was built so a future instance can create a similar one. The `oilgas/` directory is the canonical template; `farmyields/` extends it.

---

## Architecture Overview

Each tool lives in its own self-contained subdirectory. It has no build step and no dependencies outside its own folder. Pages are served as static files by GitHub Pages.

```
mytool/
  index.html                      ← page shell; loads D3, TopoJSON, and js/main.js
  css/map.css                     ← map/tooltip/bar styles (copy from oilgas or farmyields)
  js/
    main.js                       ← entry point; holds app state; wires modules together
    data.js                       ← loads and parses CSV(s); returns data object
    map.js                        ← D3 SVG map with TopoJSON; calls bars; updates legend
    bars.js                       ← renders proportional symbol bars at county centroids
    scale.js                      ← maps data values to SVG height units
    controls.js                   ← populates and wires <select> elements
    tooltip.js                    ← hover tooltip with ASCII bar chart
  data/
    counties-10m.json             ← us-atlas TopoJSON (copy from oilgas/data/)
    mydata.csv                    ← wide CSV keyed by geoid (5-digit FIPS, zero-padded)
  the-monospace-web-main/src/     ← copy from oilgas/ or farmyields/
```

Add a `<li>` link to the "Other Materials" list in the root `index.html`.

---

## Key Differences: farmyields vs. oilgas

| | oilgas | farmyields |
|---|---|---|
| State shape | `{ resource, startYear, endYear }` | `{ crop, metric, startYear, endYear }` |
| Selects | 1 (resource) | 4 (crop, metric, start year, end year) |
| Bar color | `currentColor` (CSS theme) | hardcoded per crop |
| CSV column | `{prefix}{year}` e.g. `oil1985` | `{cropId}_{metricId}{year}` e.g. `corn_prod1997` |
| maxValues key | `resource.id` | `${crop.id}_${metric.id}` (16 keys) |
| Scale | symlog | square root |
| Extra data | none | `state-totals.csv` for suppression display |

---

## CSV Format

`yields.csv` is wide-format, one row per county:

```
geoid,state,county,corn_prod1997,corn_prod1998,...,rice_yield2023
01001,AL,Autauga County,0,0,...,0
```

- `geoid`: 5-digit FIPS, zero-padded (e.g. `06037` for Los Angeles)
- Column naming: `{cropId}_{metricId}{year}` — no spaces, lowercase
- Suppressed NASS values (`(D)`, `(S)`, `(Z)`, etc.) → `0.0`

`state-totals.csv` has the same column names, keyed by 2-letter state alpha code instead of geoid.

---

## Fetch Script (`scripts/fetch_nass.py`)

Stdlib-only (no pip). Uses a JSON resume cache so interrupted runs restart from where they left off.

**Key NASS API quirks discovered — read this before writing a new fetcher:**

### 1. Wheat (and any crop with class subdivisions): ALL CLASSES dedup

NASS publishes both class-specific rows (`WINTER`, `SPRING`, `DURUM`) **and** an `ALL CLASSES` aggregate in the same response. Naively summing all records produces ~2.8× overcount.

**Fix (applied to both county and state fetches):** after collecting records for a geoid/state-year, check if any record has `class_desc == "ALL CLASSES"`. If yes, use only that value. If no, sum the class-specific production values (or take the max for yield).

This also applies at state level for crops like rice (LONG GRAIN / MEDIUM GRAIN / SHORT GRAIN + ALL CLASSES).

### 2. State-level records mix commodity types and units

A single state-level NASS request for `CORN / PRODUCTION` returns grain (BU), silage (TONS), dollar value ($), and traditional corn (LB) records — all with the same `(state, year)` key. If you just keep the last record per key, you'll often land on silage or dollars.

**Fix:** define an expected `unit_desc` per crop×metric and filter records after fetching:

```python
CROPS = [
    {"id": "corn",     "commodity_desc": "CORN",     "units": {"prod": "BU",           "yield": "BU / ACRE"}},
    {"id": "cotton",   "commodity_desc": "COTTON",   "units": {"prod": "480 LB BALES", "yield": "LB / ACRE"}},
    {"id": "rice",     "commodity_desc": "RICE",     "units": {"prod": "CWT",          "yield": "LB / ACRE"}},
    # ...
]

expected_unit = crop["units"][metric["id"]]
records = [r for r in all_records if r.get("unit_desc", "").strip() == expected_unit]
```

Do not add `unit_desc` to the API query params — NASS returns HTTP 400 for some year/filter combinations when unit_desc is specified, even when data exists.

### 3. HTTP 400 from NASS means "no records" (sometimes)

NASS returns HTTP 400 instead of an empty JSON response for some filter combinations. Catch `urllib.error.HTTPError` with `exc.code == 400` and return `[]` immediately (no retry).

### 4. County data: fetch one year at a time

County-level requests with all 27 years would exceed 50,000 records and return HTTP 413. Fetch one year per request. State-level data is small enough (~1,350 records per crop×metric) to fetch all years at once using `year__GE` / `year__LE` params.

---

## JS Module Notes

### `scale.js` — Square Root Scale

```js
const rawScale = d3.scaleSqrt()
  .domain([0, maxValue])
  .range([0, maxHeightUnits]);

return (value) => {
  if (value <= 0) return 0;
  return Math.max(2, rawScale(value)); // 2px floor keeps any producer visible
};
```

Square root is the cartographic standard for proportional symbols. Bar *area* scales linearly with value; bar *height* scales as sqrt. This makes major producers visually dominant without making tiny producers invisible. The symlog scale (used in oilgas) is more aggressive — it compresses the range so much that a 1%-of-max county appears ~28% as tall as the maximum, making it hard to distinguish major from minor producers.

### `bars.js` — Crop-colored bars

```js
.attr('fill', crop.color)   // set per-crop color, not currentColor
.attr('opacity', 1)          // start year: solid
// or
.attr('opacity', 0.55)       // end year: semi-transparent
```

### `tooltip.js` — State coverage line

For production metrics, the tooltip shows the state total and the county's share:

```js
if (_state.metric === 'prod') {
  const stateRow = _data.stateTotals && _data.stateTotals.get(row.state);
  const stateTotal = stateRow ? (stateRow[`${key}${_state.endYear}`] || 0) : 0;
  if (stateTotal > 0) {
    const pct = endVal > 0 ? (endVal / stateTotal * 100).toFixed(1) : '0.0';
    lines.push(`  ${row.state} ${_state.endYear} total: ${fmt(stateTotal)} ${unit}`);
    lines.push(`  County share: ${pct}%`);
  }
}
```

Counties with suppressed data will show 0.0% share even though they do produce — this is a useful signal to the user that data is missing.

### `data.js` — maxValues

Build a `Map<"${cropId}_${metricId}", number>` so that production and yield have separate scales (they have completely different magnitudes):

```js
const maxValues = new Map();
for (const crop of crops) {
  for (const metric of metrics) {
    const key = `${crop.id}_${metric.id}`;
    let max = 0;
    for (const row of counties.values()) {
      for (const year of crop.years) {
        const v = row[`${key}${year}`];
        if (v > max) max = v;
      }
    }
    maxValues.set(key, max);
  }
}
```

---

## Map Geometry

`counties-10m.json` is us-atlas TopoJSON (pre-projected Albers Equal Area). Use `d3.geoPath()` with no projection argument — the coordinates are already in pixel space. County FIPS codes come from `feature.id`; zero-pad to 5 digits with `String(feature.id).padStart(5, '0')`.

State borders: `topojson.mesh(topology, topology.objects.states, (a, b) => a !== b)` (interior edges).
Nation outline: `topojson.mesh(topology, topology.objects.states, (a, b) => a === b)` (exterior edges).

---

## Local Dev

```bash
npx serve .        # from repo root
# open http://localhost:3000/farmyields
```

ES modules and CSV loading require HTTP — `file://` won't work.
