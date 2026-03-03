// controls.js — UI controls (selects)

export function initControls(resources, state, onChange) {
  const resourceSelect = document.getElementById('resource-select');
  const startYearSelect = document.getElementById('start-year-select');
  const endYearSelect = document.getElementById('end-year-select');

  // Populate resource select
  resourceSelect.innerHTML = '';
  for (const res of resources) {
    const opt = document.createElement('option');
    opt.value = res.id;
    opt.textContent = res.label;
    if (res.id === state.resource) opt.selected = true;
    resourceSelect.appendChild(opt);
  }

  function getYears() {
    const res = resources.find(r => r.id === resourceSelect.value);
    return res ? res.years : [];
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
      resource: resourceSelect.value,
      startYear: +startYearSelect.value,
      endYear: +endYearSelect.value,
    });
  }

  resourceSelect.addEventListener('change', () => {
    populateYears();
    emit();
  });
  startYearSelect.addEventListener('change', emit);
  endYearSelect.addEventListener('change', emit);
}
