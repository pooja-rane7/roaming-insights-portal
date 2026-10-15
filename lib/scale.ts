/** Round up to an axis maximum whose quarters are round numbers (gridlines sit at 0, ¼, ½, ¾, 1). */
export function niceMax(value: number): number {
  if (value <= 0) return 1;
  const mag = 10 ** Math.floor(Math.log10(value));
  for (const step of [1, 1.2, 1.6, 2, 3, 4, 6, 8, 10]) if (value <= step * mag) return step * mag;
  return 10 * mag;
}

/** Evenly spaced indices for x-axis ticks, always including the first and last. */
export function tickIndices(n: number, count = 5): number[] {
  if (n <= 1) return [0];
  const c = Math.min(count, n);
  return [...new Set(Array.from({ length: c }, (_, i) => Math.round((i * (n - 1)) / (c - 1))))];
}

/** Push label y-positions apart so none are closer than `gap`, preserving order. */
export function spreadLabels(ys: number[], gap: number): number[] {
  const order = ys.map((y, i) => [y, i] as const).sort((a, b) => a[0] - b[0]);
  const out = [...ys];
  let prev = -Infinity;
  for (const [y, i] of order) {
    const placed = Math.max(y, prev + gap);
    out[i] = placed;
    prev = placed;
  }
  return out;
}
