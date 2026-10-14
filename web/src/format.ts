// Money and date formatting. Amounts are integer cents everywhere; we only convert for display.

const usd0 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const usd2 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export function dollars(cents: number): string {
  return usd0.format(Math.round(Math.abs(cents)) / 100);
}

export function dollarsExact(cents: number): string {
  return usd2.format(Math.abs(cents) / 100);
}

/** Signed difference such as "+$120" or "-$45"; zero reads as "$0". */
export function signedDollars(cents: number): string {
  if (Math.round(cents / 100) === 0) return "$0";
  return `${cents > 0 ? "+" : "-"}${dollars(cents)}`;
}

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

/** "2026-10" -> "October 2026" */
export function monthLabel(month: string): string {
  const [y, m] = month.split("-").map(Number);
  return `${MONTHS[m - 1]} ${y}`;
}

/** "2026-10" -> "October" */
export function monthName(month: string): string {
  return MONTHS[Number(month.split("-")[1]) - 1];
}

/** "2026-10-07" -> "Oct 7" */
export function shortDate(iso: string): string {
  const [, m, d] = iso.split("-").map(Number);
  return `${MONTHS[m - 1].slice(0, 3)} ${d}`;
}

export function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}
