# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a static GitHub Pages personal portfolio site (`brendanheaney.com`) built on [The Monospace Web](https://github.com/owickstrom/the-monospace-web) CSS framework. It hosts statistics education content, interactive economic models, and data visualization tools.

The active development goal is in `farmyieldsdesign.txt`: build a county-level US staple crop yields visualizer (using NASS Quick Stats data) modeled on the existing oil & gas tool in `oilgas/`.

## Development

**Local dev server** (must be served over HTTP — ES modules and CSV loading won't work from `file://`):
```
npx serve .         # from repo root, then open http://localhost:3000/oilgas
live-server         # alternative, available via nix devshell
```

**Build** (only needed to regenerate `index.html` from `demo/index.md`):
```
nix develop         # or direnv allow .
make                # runs pandoc on demo/index.md → index.html via demo/template.html
```

The Nix devshell provides: `live-server`, `pandoc`, `jq`, `gnumake`.

## Architecture

### Site Structure

The root `index.html` is the homepage. Each tool lives in its own subdirectory and is self-contained:
- `oilgas/` — US county oil & gas production visualizer (complete, serves as the template)
- A new `farmyields/` directory needs to be created for the crop yields tool

Each tool subdirectory contains its own copy of the monospace web source at `the-monospace-web-main/src/` (CSS + JS), so pages can be opened independently without depending on the root `src/` directory.

### Monospace Web Framework

All pages use CSS variables defined in `src/index.css` (or the local copy). Key variables used in custom styles: `--text-color`, `--background-color`, `--font-family`, `--font-size`, `--line-height`, `--border-thickness`. The framework provides the `.header` table layout, `.grid` form layout, and monospace typography.

### Oil & Gas Visualizer — Module Breakdown (`oilgas/js/`)

The oilgas tool is the template for all new visualizers. Its JS is split into ES modules loaded via `<script type="module">`:

| File | Responsibility |
|------|---------------|
| `main.js` | Entry point; holds app state (`resource`, `startYear`, `endYear`); wires all modules together |
| `data.js` | Defines resource configs (id, label, unit, fieldPrefix, year range); loads and parses CSV into a `Map<geoid, row>`; computes per-resource max values |
| `map.js` | D3 SVG map with TopoJSON county/state boundaries; zoom/pan behavior; calls `renderBars` and manages the legend |
| `bars.js` | Renders proportional symbol bars at county centroids (two SVG rects per county: start year solid, end year semi-transparent) |
| `scale.js` | Symlog height scale — maps production values to SVG units, floors at 2px so any producer is visible |
| `controls.js` | Populates and wires the resource/start-year/end-year `<select>` elements; calls `onChange` on change |
| `tooltip.js` | Hover/click tooltip with ASCII bar chart; follows cursor, pins to bottom on mobile |

### Data Format (CSV)

`data/production.csv` is keyed by `geoid` (5-digit FIPS, zero-padded). Column names follow the pattern `{fieldPrefix}{year}` (e.g., `oil1985`, `gas2010`). The `geoid`, `state`, and `county` columns are always present.

### Map Geometry

`data/counties-10m.json` is us-atlas TopoJSON (pre-projected Albers Equal Area). No D3 projection is needed — use `d3.geoPath()` with no projection argument. County FIPS codes come from `feature.id` (zero-pad to 5 digits).

### Bar Color Convention

The oilgas tool uses `currentColor` (inheriting the monospace web's `--text-color`, typically black/dark). The farmyields tool should use crop-specific colors rather than `currentColor` — set `fill` to a hardcoded color per crop type in `bars.js`.

## FarmYields Tool Design (from `farmyieldsdesign.txt`)

- Data source: USDA NASS Quick Stats, county-level, major staple crops
- Structure: mirror `oilgas/` exactly (same HTML layout, same JS module structure)
- Key difference: bar fill color should match the crop (e.g., yellow for corn, amber for wheat)
- Do not modify `index.html` or any existing pages — add a new directory and a new link
