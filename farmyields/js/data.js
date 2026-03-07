// data.js — CSV parsing, crop/metric config, max values

export async function loadData() {
  const crops = [
    { id: 'corn',     label: 'CORN',     color: '#B89030', darkColor: '#D4AA40', units: { prod: 'BU',           yield: 'BU/ACRE' }, years: d3.range(1997, 2024) },
    { id: 'soybeans', label: 'SOYBEANS', color: '#5A7E45', darkColor: '#7AB85E', units: { prod: 'BU',           yield: 'BU/ACRE' }, years: d3.range(1997, 2024) },
    { id: 'wheat',    label: 'WHEAT',    color: '#A8844A', darkColor: '#C8A860', units: { prod: 'BU',           yield: 'BU/ACRE' }, years: d3.range(1997, 2024) },
    { id: 'cotton',   label: 'COTTON',   color: '#6090A0', darkColor: '#80B4C8', units: { prod: '480-LB BALES', yield: 'LB/ACRE' }, years: d3.range(1997, 2024) },
    { id: 'sorghum',  label: 'SORGHUM',  color: '#904035', darkColor: '#C05A4A', units: { prod: 'BU',           yield: 'BU/ACRE' }, years: d3.range(1997, 2024) },
    { id: 'barley',   label: 'BARLEY',   color: '#887048', darkColor: '#A88E60', units: { prod: 'BU',           yield: 'BU/ACRE' }, years: d3.range(1997, 2024) },
    { id: 'oats',     label: 'OATS',     color: '#706020', darkColor: '#988035', units: { prod: 'BU',           yield: 'BU/ACRE' }, years: d3.range(1997, 2024) },
    { id: 'rice',     label: 'RICE',     color: '#3A7855', darkColor: '#4EA876', units: { prod: 'CWT',          yield: 'LB/ACRE' }, years: d3.range(1997, 2024) },
  ];

  const metrics = [
    { id: 'prod',  label: 'PRODUCTION' },
    { id: 'yield', label: 'YIELD' },
  ];

  const [rows, stateRows] = await Promise.all([
    d3.csv('data/yields.csv'),
    d3.csv('data/state-totals.csv'),
  ]);

  const counties = new Map();
  for (const row of rows) {
    const geoid = String(row.geoid).padStart(5, '0');
    const parsed = { geoid, state: row.state, county: row.county };
    for (const crop of crops) {
      for (const metric of metrics) {
        for (const year of crop.years) {
          const field = `${crop.id}_${metric.id}${year}`;
          parsed[field] = +(row[field] || 0);
        }
      }
    }
    counties.set(geoid, parsed);
  }

  // Build maxValues keyed by "${cropId}_${metricId}"
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

  const stateTotals = new Map();
  for (const row of stateRows) {
    const state = row.state;
    if (!state) continue;
    const parsed = { state };
    for (const crop of crops) {
      for (const metric of metrics) {
        for (const year of crop.years) {
          const field = `${crop.id}_${metric.id}${year}`;
          parsed[field] = +(row[field] || 0);
        }
      }
    }
    stateTotals.set(state, parsed);
  }

  return { counties, crops, metrics, maxValues, stateTotals };
}
