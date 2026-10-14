// Pure functions that turn API rows into what the dashboard shows. No React in here so it is easy to test.
import type { DailySpend, MonthlySpend } from "./api";

export const UNCATEGORIZED = "Uncategorized";
export const OTHER = "Other";
/** How many categories get their own color; everything past this folds into "Other". */
export const MAX_NAMED = 5;

export function monthsAvailable(rows: MonthlySpend[]): string[] {
  return [...new Set(rows.map((r) => r.month))].sort().reverse();
}

export function previousMonth(month: string): string {
  const [y, m] = month.split("-").map(Number);
  return m === 1 ? `${y - 1}-12` : `${y}-${String(m - 1).padStart(2, "0")}`;
}

export function daysInMonth(month: string): number {
  const [y, m] = month.split("-").map(Number);
  return new Date(y, m, 0).getDate();
}

export function currentMonth(today: Date): string {
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;
}

export function categoryName(category: string | null): string {
  return category ?? UNCATEGORIZED;
}

export function monthTotal(rows: MonthlySpend[], month: string): { cents: number; count: number } {
  let cents = 0;
  let count = 0;
  for (const r of rows) {
    if (r.month === month) {
      cents += r.spent_cents;
      count += r.transaction_count;
    }
  }
  return { cents, count };
}

/**
 * Color slot per category, ranked by total spend across ALL loaded months.
 * Ranking over everything (not the selected month) means a category keeps its color
 * when you switch months. "Uncategorized" never takes a hue slot.
 */
export function colorSlots(rows: MonthlySpend[]): Map<string, number> {
  const totals = new Map<string, number>();
  for (const r of rows) {
    const name = categoryName(r.category);
    if (name === UNCATEGORIZED) continue;
    totals.set(name, (totals.get(name) ?? 0) + r.spent_cents);
  }
  const ranked = [...totals.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  return new Map(ranked.slice(0, MAX_NAMED).map(([name], i) => [name, i]));
}

export interface CategoryRow {
  name: string;
  /** Hue slot 0..MAX_NAMED-1, or null for the neutral "Other"/"Uncategorized" rows. */
  slot: number | null;
  cents: number;
  count: number;
  share: number; // 0..1 of the month total
}

export function breakdown(rows: MonthlySpend[], month: string, slots: Map<string, number>): CategoryRow[] {
  const total = monthTotal(rows, month).cents;
  const named: CategoryRow[] = [];
  let other = { cents: 0, count: 0 };
  let uncategorized = { cents: 0, count: 0 };
  for (const r of rows) {
    if (r.month !== month) continue;
    const name = categoryName(r.category);
    const slot = slots.get(name);
    if (name === UNCATEGORIZED) {
      uncategorized = { cents: uncategorized.cents + r.spent_cents, count: uncategorized.count + r.transaction_count };
    } else if (slot === undefined) {
      other = { cents: other.cents + r.spent_cents, count: other.count + r.transaction_count };
    } else {
      named.push({ name, slot, cents: r.spent_cents, count: r.transaction_count, share: 0 });
    }
  }
  named.sort((a, b) => b.cents - a.cents);
  const out = [...named];
  if (other.cents > 0) out.push({ name: OTHER, slot: null, ...other, share: 0 });
  if (uncategorized.cents > 0) out.push({ name: UNCATEGORIZED, slot: null, ...uncategorized, share: 0 });
  for (const row of out) row.share = total > 0 ? row.cents / total : 0;
  return out;
}

/**
 * Running total for each day of the month (index 0 = day 1).
 * Days after `lastDay` are null so the line stops at today instead of flat-lining.
 */
export function cumulative(daily: DailySpend[], month: string, lastDay: number = daysInMonth(month)): (number | null)[] {
  const days = daysInMonth(month);
  const perDay = new Array<number>(days).fill(0);
  for (const d of daily) {
    if (!d.date.startsWith(month)) continue;
    const day = Number(d.date.slice(8, 10));
    if (day >= 1 && day <= days) perDay[day - 1] += d.spent_cents;
  }
  let running = 0;
  return perDay.map((cents, i) => {
    running += cents;
    return i + 1 <= lastDay ? running : null;
  });
}

export interface Pace {
  /** Last day that has data/elapsed: today for the current month, else the last day of the month. */
  elapsedDays: number;
  totalCents: number;
  perDayCents: number;
  /** Spend in the previous month over the same number of days; null when there is no previous data. */
  previousToDateCents: number | null;
  deltaCents: number | null;
}

export function pace(
  rows: MonthlySpend[],
  dailyPrev: DailySpend[],
  month: string,
  today: Date,
): Pace {
  const isCurrent = currentMonth(today) === month;
  const elapsedDays = isCurrent ? today.getDate() : daysInMonth(month);
  const totalCents = monthTotal(rows, month).cents;
  const prev = previousMonth(month);
  const hasPrev = rows.some((r) => r.month === prev);
  let previousToDateCents: number | null = null;
  if (hasPrev) {
    const run = cumulative(dailyPrev, prev, Math.min(elapsedDays, daysInMonth(prev)));
    const last = run.filter((v): v is number => v !== null);
    previousToDateCents = last.length ? last[last.length - 1] : 0;
  }
  return {
    elapsedDays,
    totalCents,
    perDayCents: elapsedDays > 0 ? Math.round(totalCents / elapsedDays) : 0,
    previousToDateCents,
    deltaCents: previousToDateCents === null ? null : totalCents - previousToDateCents,
  };
}
