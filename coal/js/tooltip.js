// tooltip.js — hover tooltip

const fmt = d3.format('.3~s');

let _data = null;
let _state = null;

export function initTooltip(data, state) {
  _data = data;
  _state = state;
}

export function updateTooltipState(state) {
  _state = state;
}

export function showTooltip(event, geoid) {
  const tooltip = document.getElementById('tooltip');
  const row = _data.counties.get(geoid);
  if (!row || !tooltip) return;

  const res = _data.resources.find(r => r.id === _state.resource);
  if (!res) return;

  const startVal = row[`${res.fieldPrefix}${_state.startYear}`] || 0;
  const endVal = row[`${res.fieldPrefix}${_state.endYear}`] || 0;

  const maxVal = Math.max(startVal, endVal);
  const barMaxLen = 16;

  function barStr(val) {
    if (maxVal === 0) return '';
    const len = Math.round((val / maxVal) * barMaxLen);
    return '\u2588'.repeat(Math.max(0, len));
  }

  const lines = [
    `${row.county}, ${row.state}`,
    '\u2500'.repeat(36),
    res.label,
    `  ${_state.startYear}: ${fmt(startVal).padStart(8)} ${res.unit.padEnd(10)} ${barStr(startVal)}`,
    `  ${_state.endYear}: ${fmt(endVal).padStart(8)} ${res.unit.padEnd(10)} ${barStr(endVal)}`,
  ];

  tooltip.textContent = lines.join('\n');
  tooltip.style.display = 'block';
  moveTooltip(event);
}

export function moveTooltip(event) {
  const tooltip = document.getElementById('tooltip');
  if (!tooltip || tooltip.style.display === 'none') return;

  const margin = 12;
  let x = event.clientX + margin;
  let y = event.clientY + margin;

  const rect = tooltip.getBoundingClientRect();
  if (x + rect.width > window.innerWidth - margin) {
    x = event.clientX - rect.width - margin;
  }
  if (y + rect.height > window.innerHeight - margin) {
    y = event.clientY - rect.height - margin;
  }

  tooltip.style.left = `${x}px`;
  tooltip.style.top = `${y}px`;
}

export function hideTooltip() {
  const tooltip = document.getElementById('tooltip');
  if (tooltip) tooltip.style.display = 'none';
}
