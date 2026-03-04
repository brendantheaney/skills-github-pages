// scale.js — square-root height scale for bars
//
// sqrt is the standard for proportional symbol maps: bar area (and perceived size)
// scales linearly with value, while bar height scales as sqrt. This preserves the
// visual hierarchy — major producers tower over minor ones — while still keeping
// small producers visible via the 2px floor.

export function buildHeightScale(maxValue, maxHeightUnits = 80) {
  const rawScale = d3.scaleSqrt()
    .domain([0, maxValue])
    .range([0, maxHeightUnits]);

  return (value) => {
    if (value <= 0) return 0;
    return Math.max(2, rawScale(value)); // floor: any non-zero producer gets a visible bar
  };
}
