// Demo mode: made-up transactions generated in the browser, so the site can be hosted without a backend.
// Nothing here comes from real statements. A seeded generator keeps the numbers the same on every visit.
import type { DailySpend, MonthlySpend, Transaction } from "./api";

export const DEMO = import.meta.env.VITE_DEMO === "true";

const MERCHANTS: { name: string; category: string; min: number; max: number; weight: number }[] = [
  { name: "WHOLE FOODS MKT 0412", category: "Groceries", min: 35, max: 140, weight: 4 },
  { name: "TRADER JOES 118", category: "Groceries", min: 20, max: 90, weight: 4 },
  { name: "CHIPOTLE 2345", category: "Dining", min: 10, max: 18, weight: 4 },
  { name: "STARBUCKS STORE 1234", category: "Dining", min: 4, max: 9, weight: 5 },
  { name: "TARGET 00012345", category: "Shopping", min: 20, max: 110, weight: 2 },
  { name: "AMAZON.COM*AB12", category: "Shopping", min: 12, max: 120, weight: 3 },
  { name: "SHELL OIL 5742", category: "Gas", min: 30, max: 60, weight: 2 },
  { name: "UBER *TRIP", category: "Transport", min: 8, max: 35, weight: 2 },
  { name: "NETFLIX.COM", category: "Subscriptions", min: 15, max: 16, weight: 1 },
  { name: "SPOTIFY USA", category: "Subscriptions", min: 11, max: 12, weight: 1 },
  { name: "PG&E ONLINE PAYMENT", category: "Utilities", min: 60, max: 140, weight: 1 },
];

function rng(seed: number) {
  // mulberry32: tiny deterministic PRNG
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

/** Spending for the two full months before `today`'s month, plus the current month up to today. */
export function demoTransactions(today: Date): Transaction[] {
  const rand = rng(2026);
  const pool = MERCHANTS.flatMap((m) => Array<typeof m>(m.weight).fill(m));
  const out: Transaction[] = [];
  const start = new Date(today.getFullYear(), today.getMonth() - 2, 1);
  let id = 1;
  for (const d = new Date(start); d <= today; d.setDate(d.getDate() + 1)) {
    const count = [0, 1, 1, 2, 3][Math.floor(rand() * 5)];
    for (let i = 0; i < count; i++) {
      const m = pool[Math.floor(rand() * pool.length)];
      const cents = Math.round((m.min + rand() * (m.max - m.min)) * 100);
      out.push({ id: id++, posted_on: iso(d), amount_cents: -cents, description: m.name, category: m.category, category_source: "rules" });
    }
  }
  return out;
}

export function demoApi(today: Date = new Date()) {
  const all = demoTransactions(today);
  return {
    monthly(): MonthlySpend[] {
      const map = new Map<string, MonthlySpend>();
      for (const t of all) {
        const month = t.posted_on.slice(0, 7);
        const key = `${month}|${t.category}`;
        const row = map.get(key) ?? { month, category: t.category, spent_cents: 0, transaction_count: 0 };
        row.spent_cents -= t.amount_cents;
        row.transaction_count += 1;
        map.set(key, row);
      }
      return [...map.values()].sort((a, b) => a.month.localeCompare(b.month) || (a.category ?? "").localeCompare(b.category ?? ""));
    },
    daily(month: string): DailySpend[] {
      const map = new Map<string, DailySpend>();
      for (const t of all) {
        if (!t.posted_on.startsWith(month)) continue;
        const row = map.get(t.posted_on) ?? { date: t.posted_on, spent_cents: 0, transaction_count: 0 };
        row.spent_cents -= t.amount_cents;
        row.transaction_count += 1;
        map.set(t.posted_on, row);
      }
      return [...map.values()].sort((a, b) => a.date.localeCompare(b.date));
    },
    transactions(limit: number): Transaction[] {
      return [...all].reverse().slice(0, limit);
    },
  };
}
