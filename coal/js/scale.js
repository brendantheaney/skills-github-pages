// scale.js — log height scale for bars

export function buildHeightScale(maxValue, maxHeightUnits = 80) {
  // Set the symlog constant relative to maxValue.
  // constant = maxValue/100000 means:
  //   - values at 0.1% of max  → ~22 units  (small producers, visible)
  //   - values at 1% of max    → ~32 units  (moderate producers)
  //   - values at 10% of max   → ~47 units  (large producers)
  //   - values at 100% of max  → 80 units   (biggest producers)
  // This gives clear visual separation across the full 8-decade data range.
  const constant = Math.max(1, maxValue / 100000);

  const rawScale = d3.scaleSymlog()
    .domain([0, maxValue])
    .range([0, maxHeightUnits])
    .constant(constant);

  return (value) => {
    if (value <= 0) return 0;
    return Math.max(2, rawScale(value)); // floor: any non-zero producer gets a visible bar
  };
}
