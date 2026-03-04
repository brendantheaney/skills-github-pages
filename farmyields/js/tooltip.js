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

  const crop = _data.crops.find(c => c.id === _state.crop);
  const metric = _data.metrics.find(m => m.id === _state.metric);
  if (!crop || !metric) return;

  const key = `${crop.id}_${_state.metric}`;
  const startVal = row[`${key}${_state.startYear}`] || 0;
  const endVal = row[`${key}${_state.endYear}`] || 0;
  const unit = crop.units[_state.metric];

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
    `${crop.label}  \u2014  ${metric.label}`,
    `  ${_state.startYear}: ${fmt(startVal).padStart(8)} ${unit.padEnd(10)} ${barStr(startVal)}`,
    `  ${_state.endYear}: ${fmt(endVal).padStart(8)} ${unit.padEnd(10)} ${barStr(endVal)}`,
  ];

  // For production, show state total and county share to surface suppression gaps
  if (_state.metric === 'prod') {
    const stateRow = _data.stateTotals && _data.stateTotals.get(row.state);
    const stateTotal = stateRow ? (stateRow[`${key}${_state.endYear}`] || 0) : 0;
    if (stateTotal > 0) {
      const pct = endVal > 0 ? (endVal / stateTotal * 100).toFixed(1) : '0.0';
      lines.push('');
      lines.push(`  ${row.state} ${_state.endYear} total: ${fmt(stateTotal)} ${unit}`);
      lines.push(`  County share: ${pct}%`);
    }
  }

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
