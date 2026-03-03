// data.js — CSV parsing, resource config, max values

export async function loadData() {
  const resources = [
    {
      id: 'oil',
      label: 'CRUDE OIL',
      unit: 'bbl',
      fieldPrefix: 'oil',
      years: d3.range(1970, 2021),
    },
    {
      id: 'gas',
      label: 'NATURAL GAS',
      unit: 'MCF',
      fieldPrefix: 'gas',
      years: d3.range(1970, 2021),
    },
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
