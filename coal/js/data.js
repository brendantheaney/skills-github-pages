// data.js — CSV parsing, resource config, max values

export async function loadData() {
  const resources = [
    { id: 'total',       label: 'COAL (TOTAL)',    fieldPrefix: 'coal',        unit: 'short tons', color: '#3D3D3D', darkColor: '#D4A868', years: d3.range(2001, 2025) },
    { id: 'surface',     label: 'SURFACE MINING',  fieldPrefix: 'surface',     unit: 'short tons', color: '#7A5C2E', darkColor: '#C8A850', years: d3.range(2001, 2025) },
    { id: 'underground', label: 'UNDERGROUND',      fieldPrefix: 'underground', unit: 'short tons', color: '#3A4A6A', darkColor: '#7090C8', years: d3.range(2001, 2025) },
  ];

  const rows = await d3.csv('data/production.csv');

  const counties = new Map();
  for (const row of rows) {
    const geoid = String(row.geoid).padStart(5, '0');
    const parsed = { geoid, state: row.state, county: row.county };
    for (const res of resources) {
      for (const year of res.years) {
        const field = `${res.fieldPrefix}${year}`;
        parsed[field] = +(row[field] || 0);
      }
    }
    counties.set(geoid, parsed);
  }

  // Build maxValues keyed by resource id
  const maxValues = new Map();
  for (const res of resources) {
    let max = 0;
    for (const row of counties.values()) {
      for (const year of res.years) {
        const v = row[`${res.fieldPrefix}${year}`];
        if (v > max) max = v;
      }
    }
    maxValues.set(res.id, max);
  }

  return { counties, resources, maxValues };
}
