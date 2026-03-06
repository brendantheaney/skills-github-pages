// bars.js — proportional symbol bars

import { buildHeightScale } from './scale.js';
import { showTooltip, moveTooltip, hideTooltip } from './tooltip.js';

const BAR_WIDTH = 2.5;
const BAR_GAP = 0.8;

function getBarColor() {
  return getComputedStyle(document.documentElement).getPropertyValue('--coal-bar-color').trim() || '#4A3F35';
}

export function renderBars(barsLayer, features, data, state, topology) {
  const path = d3.geoPath();

  const res = data.resources.find(r => r.id === state.resource);
  if (!res) return null;

  const BAR_COLOR = getBarColor();
  const heightScale = buildHeightScale(data.maxValues.get(state.resource));

  // Clear existing bars
  barsLayer.selectAll('*').remove();

  for (const feature of features) {
    const geoid = String(feature.id).padStart(5, '0');
    const row = data.counties.get(geoid);
    if (!row) continue;

    const startVal = row[`${res.fieldPrefix}${state.startYear}`] || 0;
    const endVal = row[`${res.fieldPrefix}${state.endYear}`] || 0;

    if (startVal === 0 && endVal === 0) continue;

    const centroid = path.centroid(feature);
    if (!centroid || isNaN(centroid[0]) || isNaN(centroid[1])) continue;

    const [cx, cy] = centroid;
    const startH = heightScale(startVal);
    const endH = heightScale(endVal);

    const g = barsLayer.append('g')
      .attr('class', 'county-bar-group')
      .attr('data-fips', geoid);

    if (startH > 0) {
      g.append('rect')
        .attr('class', 'bar-start')
        .attr('x', cx - BAR_WIDTH - BAR_GAP / 2)
        .attr('y', cy - startH)
        .attr('width', BAR_WIDTH)
        .attr('height', startH)
        .attr('fill', BAR_COLOR)
        .attr('opacity', 1);
    }

    if (endH > 0) {
      g.append('rect')
        .attr('class', 'bar-end')
        .attr('x', cx + BAR_GAP / 2)
        .attr('y', cy - endH)
        .attr('width', BAR_WIDTH)
        .attr('height', endH)
        .attr('fill', BAR_COLOR)
        .attr('opacity', 0.55);
    }

    g.on('mouseover', (event) => showTooltip(event, geoid))
     .on('mousemove', (event) => moveTooltip(event))
     .on('mouseout', hideTooltip)
     .on('click', (event) => { event.stopPropagation(); showTooltip(event, geoid); });
  }

  return heightScale;
}

export function updateBars(barsLayer, features, data, state) {
  const res = data.resources.find(r => r.id === state.resource);
  if (!res) return;

  const BAR_COLOR = getBarColor();
  const heightScale = buildHeightScale(data.maxValues.get(state.resource));

  const path = d3.geoPath();

  barsLayer.selectAll('*').remove();

  for (const feature of features) {
    const geoid = String(feature.id).padStart(5, '0');
    const row = data.counties.get(geoid);
    if (!row) continue;

    const startVal = row[`${res.fieldPrefix}${state.startYear}`] || 0;
    const endVal = row[`${res.fieldPrefix}${state.endYear}`] || 0;

    if (startVal === 0 && endVal === 0) continue;

    const centroid = path.centroid(feature);
    if (!centroid || isNaN(centroid[0]) || isNaN(centroid[1])) continue;

    const [cx, cy] = centroid;
    const startH = heightScale(startVal);
    const endH = heightScale(endVal);

    const g = barsLayer.append('g')
      .attr('class', 'county-bar-group')
      .attr('data-fips', geoid);

    if (startH > 0) {
      g.append('rect')
        .attr('class', 'bar-start')
        .attr('x', cx - BAR_WIDTH - BAR_GAP / 2)
        .attr('y', cy - startH)
        .attr('width', BAR_WIDTH)
        .attr('height', startH)
        .attr('fill', BAR_COLOR)
        .attr('opacity', 1);
    }

    if (endH > 0) {
      g.append('rect')
        .attr('class', 'bar-end')
        .attr('x', cx + BAR_GAP / 2)
        .attr('y', cy - endH)
        .attr('width', BAR_WIDTH)
        .attr('height', endH)
        .attr('fill', BAR_COLOR)
        .attr('opacity', 0.55);
    }

    g.on('mouseover', (event) => showTooltip(event, geoid))
     .on('mousemove', (event) => moveTooltip(event))
     .on('mouseout', hideTooltip)
     .on('click', (event) => { event.stopPropagation(); showTooltip(event, geoid); });
  }
}
