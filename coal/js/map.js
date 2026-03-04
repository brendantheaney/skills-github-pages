// map.js — D3 SVG, county boundaries, zoom

import { renderBars, updateBars } from './bars.js';
import { showTooltip, moveTooltip, hideTooltip } from './tooltip.js';

export function initMap(data, topology, state) {
  const svg = d3.select('#map-svg');
  const zoomGroup = d3.select('#zoom-group');
  const countiesLayer = d3.select('#counties-layer');
  const statesLayer = d3.select('#states-layer');
  const barsLayer = d3.select('#bars-layer');

  // us-atlas is pre-projected (Albers), no d3 projection needed
  const path = d3.geoPath();

  // Extract feature arrays
  const countyFeatures = topojson.feature(topology, topology.objects.counties).features
    .filter(d => { const s = String(d.id).padStart(5, '0').slice(0, 2); return s !== '02' && s !== '15'; });
  const stateMesh = topojson.mesh(topology, topology.objects.states,
    (a, b) => a !== b && a.id !== '02' && b.id !== '02' && a.id !== '15' && b.id !== '15');

  // Draw county boundaries
  countiesLayer.selectAll('path.county-path')
    .data(countyFeatures)
    .join('path')
    .attr('class', 'county-path')
    .attr('d', path)
    .attr('data-fips', d => String(d.id).padStart(5, '0'))
    .on('mouseover', function(event, d) {
      const geoid = String(d.id).padStart(5, '0');
      showTooltip(event, geoid);
    })
    .on('mousemove', moveTooltip)
    .on('mouseout', hideTooltip)
    .on('click', function(event, d) {
      event.stopPropagation();
      const geoid = String(d.id).padStart(5, '0');
      showTooltip(event, geoid);
    });

  // Draw state borders
  statesLayer.append('path')
    .attr('class', 'state-border')
    .attr('d', path(stateMesh));

  // Draw nation outline (exterior edges of states mesh)
  const nationMesh = topojson.mesh(topology, topology.objects.states,
    (a, b) => a === b && a.id !== '02' && a.id !== '15');
  statesLayer.append('path')
    .attr('class', 'nation-border')
    .attr('d', path(nationMesh));

  // Zoom/pan
  const zoom = d3.zoom()
    .scaleExtent([1, 12])
    .translateExtent([[0, 0], [975, 610]])
    .on('zoom', e => zoomGroup.attr('transform', e.transform));

  svg.call(zoom);

  // Tap empty map area to dismiss tooltip on mobile
  svg.on('click', hideTooltip);

  // Double-click to reset zoom
  svg.on('dblclick.zoom', null);
  svg.on('dblclick', () => {
    svg.transition().duration(500).call(zoom.transform, d3.zoomIdentity);
  });

  // Initial bars render
  renderBars(barsLayer, countyFeatures, data, state);

  // Update legend
  updateLegend(state, data);

  return {
    update(newState) {
      updateBars(barsLayer, countyFeatures, data, newState);
      updateLegend(newState, data);
    }
  };
}

function updateLegend(state, data) {
  const legendEl = document.getElementById('legend-text');
  if (!legendEl) return;

  const res = data.resources.find(r => r.id === state.resource);
  if (!res) return;

  const maxVal = data.maxValues.get(state.resource);
  const fmt = d3.format('.3~s');

  legendEl.textContent = [
    `  \u2591  = START YEAR (${state.startYear})    [lighter]`,
    `  \u2588  = END YEAR   (${state.endYear})    [solid]`,
    ``,
    `  Max bar = ${fmt(maxVal)} ${res.unit}  (${res.label})`,
    `  Scale: square root. Each bar = one county.`,
  ].join('\n');
}
