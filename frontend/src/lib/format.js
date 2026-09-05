/**
 * Display formatting.
 *
 * Money is formatted for reading, never for calculation — every figure shown
 * here was computed by the backend's decimal engine.
 */

const currencyFormatters = new Map();

function formatter(currency, options) {
  const key = `${currency}:${JSON.stringify(options)}`;
  if (!currencyFormatters.has(key)) {
    currencyFormatters.set(
      key,
      new Intl.NumberFormat(undefined, { style: "currency", currency, ...options }),
    );
  }
  return currencyFormatters.get(key);
}

/** Full precision, e.g. $1,234.56 */
export function money(value, currency = "USD") {
  const n = Number(value ?? 0);
  return formatter(currency, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n);
}

/** Whole dollars, for headline figures and axes: $1,235 */
export function money0(value, currency = "USD") {
  const n = Number(value ?? 0);
  return formatter(currency, { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);
}

/** Compact, for tight axis labels: $1.2k, $34k, $1.1M */
export function moneyCompact(value, currency = "USD") {
  const n = Number(value ?? 0);
  const abs = Math.abs(n);
  if (abs < 1000) return money0(n, currency);
  return formatter(currency, {
    notation: "compact",
    maximumFractionDigits: abs < 10000 ? 1 : 0,
  }).format(n);
}

/** Signed, so a negative cash flow reads as −$420 rather than $-420. */
export function moneySigned(value, currency = "USD") {
  const n = Number(value ?? 0);
  const sign = n < 0 ? "−" : n > 0 ? "+" : "";
  return `${sign}${money0(Math.abs(n), currency)}`;
}

export function percent(value, digits = 0) {
  const n = Number(value ?? 0);
  return `${n.toFixed(digits)}%`;
}

export function number(value, digits = 0) {
  return new Intl.NumberFormat(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(Number(value ?? 0));
}

export function shortDate(value) {
  if (!value) return "";
  const d = value instanceof Date ? value : new Date(value);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function longDate(value) {
  if (!value) return "";
  const d = value instanceof Date ? value : new Date(value);
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export function relativeTime(value) {
  if (!value) return "";
  const then = new Date(value).getTime();
  const mins = Math.round((Date.now() - then) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return longDate(value);
}

/** Months rendered the way people actually say them. */
export function monthsToHuman(months) {
  if (months == null) return "—";
  if (months === 0) return "now";
  if (months < 12) return `${months} month${months === 1 ? "" : "s"}`;
  const years = Math.floor(months / 12);
  const rest = months % 12;
  if (rest === 0) return `${years} year${years === 1 ? "" : "s"}`;
  return `${years}y ${rest}m`;
}

export function titleCase(value) {
  if (!value) return "";
  return String(value)
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
