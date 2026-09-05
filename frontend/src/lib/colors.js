/**
 * Chart colour roles.
 *
 * Series hues are assigned in fixed order and never cycled — a seventh series
 * folds into "Other" rather than reusing slot 1, so a colour always means the
 * same thing. Status colours are reserved and never used for a data series.
 */
export const SERIES = [
  "var(--series-1)",
  "var(--series-2)",
  "var(--series-3)",
  "var(--series-4)",
  "var(--series-5)",
  "var(--series-6)",
];

export const MAX_SERIES = SERIES.length;

export function seriesColor(index) {
  return SERIES[index] ?? "var(--ink-subtle)";
}

/**
 * Group rows into at most MAX_SERIES slices, folding the tail into "Other".
 * Rows must already be sorted by value, descending.
 */
export function foldToSeries(rows, { labelKey = "label", valueKey = "value" } = {}) {
  if (rows.length <= MAX_SERIES) {
    return rows.map((row, i) => ({ ...row, color: seriesColor(i) }));
  }
  const head = rows.slice(0, MAX_SERIES - 1).map((row, i) => ({ ...row, color: seriesColor(i) }));
  const tail = rows.slice(MAX_SERIES - 1);
  return [
    ...head,
    {
      [labelKey]: `Other (${tail.length})`,
      [valueKey]: tail.reduce((sum, r) => sum + Number(r[valueKey] ?? 0), 0),
      color: "var(--ink-subtle)",
      isOther: true,
    },
  ];
}

/** Cash-flow direction. Never the only signal — always paired with a label. */
export const FLOW = {
  income: "var(--series-3)",
  expense: "var(--series-2)",
  net: "var(--series-1)",
};

export function statusColor(kind) {
  return (
    { good: "var(--good)", warning: "var(--warning)", serious: "var(--serious)", critical: "var(--critical)" }[kind] ??
    "var(--ink-subtle)"
  );
}

/** Health-score band. Returns a status role, never a raw hue. */
export function scoreStatus(score) {
  if (score >= 85) return "good";
  if (score >= 70) return "good";
  if (score >= 55) return "warning";
  if (score >= 35) return "serious";
  return "critical";
}
