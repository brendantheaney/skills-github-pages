// main.js — entry point, app state, wiring

import { loadData } from './data.js';
import { initMap } from './map.js';
import { initControls } from './controls.js';
import { initTooltip, updateTooltipState } from './tooltip.js';

window.addEventListener('load', async () => {
  const state = {
    crop: 'corn',
    metric: 'prod',
    startYear: 1997,
    endYear: 2023,
  };

  let mapController = null;

  try {
    const [data, topology] = await Promise.all([
      loadData(),
      d3.json('data/counties-10m.json'),
    ]);

    initTooltip(data, state);

    mapController = initMap(data, topology, state);

    initControls(data.crops, data.metrics, state, (newState) => {
      Object.assign(state, newState);
      updateTooltipState(state);
      if (mapController) mapController.update(state);
    });

  } catch (err) {
    console.error('Failed to initialize map:', err);
    const container = document.getElementById('map-container');
    if (container) {
      container.innerHTML = `<p style="color:red">Error loading map: ${err.message}. Serve this page from a local HTTP server (e.g. <code>npx serve .</code>).</p>`;
    }
  }
});
