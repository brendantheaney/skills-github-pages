// controls.js — UI controls (selects)

export function initControls(crops, metrics, state, onChange) {
  const cropSelect = document.getElementById('crop-select');
  const metricSelect = document.getElementById('metric-select');
  const startYearSelect = document.getElementById('start-year-select');
  const endYearSelect = document.getElementById('end-year-select');

  // Populate crop select
  cropSelect.innerHTML = '';
  for (const crop of crops) {
    const opt = document.createElement('option');
    opt.value = crop.id;
    opt.textContent = crop.label;
    if (crop.id === state.crop) opt.selected = true;
    cropSelect.appendChild(opt);
  }

  // Populate metric select
  metricSelect.innerHTML = '';
  for (const metric of metrics) {
    const opt = document.createElement('option');
    opt.value = metric.id;
    opt.textContent = metric.label;
    if (metric.id === state.metric) opt.selected = true;
    metricSelect.appendChild(opt);
  }

  function getYears() {
    const crop = crops.find(c => c.id === cropSelect.value);
    return crop ? crop.years : [];
  }

  function populateYears() {
    const years = getYears();
    const startVal = +startYearSelect.value || state.startYear;
    const endVal = +endYearSelect.value || state.endYear;

    startYearSelect.innerHTML = '';
    endYearSelect.innerHTML = '';

    for (const y of years) {
      const optS = document.createElement('option');
      optS.value = y;
      optS.textContent = y;
      if (y === startVal) optS.selected = true;
      startYearSelect.appendChild(optS);

      const optE = document.createElement('option');
      optE.value = y;
      optE.textContent = y;
      if (y === endVal) optE.selected = true;
      endYearSelect.appendChild(optE);
    }

    // Default: last year selected for end year
    if (!years.includes(endVal)) {
      endYearSelect.value = years[years.length - 1];
    }
  }

  populateYears();

  function emit() {
    onChange({
      crop: cropSelect.value,
      metric: metricSelect.value,
      startYear: +startYearSelect.value,
      endYear: +endYearSelect.value,
    });
  }

  cropSelect.addEventListener('change', () => {
    populateYears();
    emit();
  });
  metricSelect.addEventListener('change', emit);
  startYearSelect.addEventListener('change', emit);
  endYearSelect.addEventListener('change', emit);
}
