import { describe, expect, it } from "vitest";
import type { DailySpend, MonthlySpend } from "./api";
import { breakdown, colorSlots, cumulative, daysInMonth, monthsAvailable, pace, previousMonth } from "./derive";
import { dollars, monthLabel, signedDollars } from "./format";

const row = (month: string, category: string | null, dollarsSpent: number, n = 1): MonthlySpend => ({
  month,
  category,
  spent_cents: dollarsSpent * 100,
  transaction_count: n,
});
const day = (date: string, dollarsSpent: number): DailySpend => ({ date, spent_cents: dollarsSpent * 100, transaction_count: 1 });

describe("months", () => {
  it("lists months newest first and wraps January back to December", () => {
    expect(monthsAvailable([row("2026-08", "A", 1), row("2026-10", "A", 1), row("2026-08", "B", 1)])).toEqual(["2026-10", "2026-08"]);
    expect(previousMonth("2026-01")).toBe("2025-12");
    expect(previousMonth("2026-10")).toBe("2026-09");
  });
  it("knows month lengths, including leap February", () => {
    expect(daysInMonth("2024-02")).toBe(29);
    expect(daysInMonth("2026-02")).toBe(28);
    expect(daysInMonth("2026-10")).toBe(31);
  });
});

describe("colorSlots and breakdown", () => {
  const rows = [
    row("2026-09", "Groceries", 500), row("2026-09", "Dining", 300), row("2026-09", "Gas", 100),
    row("2026-09", "Shopping", 90), row("2026-09", "Travel", 80), row("2026-09", "Fees", 20), row("2026-09", null, 50),
    row("2026-10", "Fees", 40), row("2026-10", "Groceries", 10),
  ];
  it("ranks by all-time spend and leaves Uncategorized without a hue", () => {
    const slots = colorSlots(rows);
    expect(slots.get("Groceries")).toBe(0);
    expect(slots.get("Dining")).toBe(1);
    expect(slots.has("Fees")).toBe(false); // sixth, so it folds into Other
    expect([...slots.keys()]).not.toContain("Uncategorized");
  });
  it("keeps a category's color when the selected month changes", () => {
    const slots = colorSlots(rows);
    const oct = breakdown(rows, "2026-10", slots);
    const sep = breakdown(rows, "2026-09", slots);
    expect(oct.find((r) => r.name === "Groceries")?.slot).toBe(sep.find((r) => r.name === "Groceries")?.slot);
  });
  it("folds the tail into Other, puts Uncategorized last, and shares sum to 1", () => {
    const sep = breakdown(rows, "2026-09", colorSlots(rows));
    expect(sep.map((r) => r.name)).toEqual(["Groceries", "Dining", "Gas", "Shopping", "Travel", "Other", "Uncategorized"]);
    expect(sep.reduce((a, r) => a + r.share, 0)).toBeCloseTo(1, 10);
    expect(sep.find((r) => r.name === "Other")?.cents).toBe(2000);
  });
});

describe("cumulative", () => {
  it("builds a running total and stops after the last elapsed day", () => {
    const run = cumulative([day("2026-10-01", 10), day("2026-10-01", 5), day("2026-10-03", 20)], "2026-10", 4);
    expect(run.slice(0, 5)).toEqual([1500, 1500, 3500, 3500, null]);
    expect(run).toHaveLength(31);
  });
  it("ignores rows from other months", () => {
    expect(cumulative([day("2026-09-30", 99)], "2026-10", 2)).toEqual([0, 0, ...new Array(29).fill(null)]);
  });
});

describe("pace", () => {
  const rows = [row("2026-09", "A", 300), row("2026-10", "A", 100)];
  const prevDaily = [day("2026-09-02", 100), day("2026-09-20", 200)];
  it("compares this month so far with the same days of last month", () => {
    const p = pace(rows, prevDaily, "2026-10", new Date(2026, 9, 5));
    expect(p.elapsedDays).toBe(5);
    expect(p.perDayCents).toBe(2000);
    expect(p.previousToDateCents).toBe(10000);
    expect(p.deltaCents).toBe(0);
  });
  it("uses the whole month for a finished month", () => {
    const p = pace(rows, [], "2026-09", new Date(2026, 9, 5));
    expect(p.elapsedDays).toBe(30);
    expect(p.deltaCents).toBeNull(); // no August data
  });
});

describe("format", () => {
  it("formats cents without float surprises", () => {
    expect(dollars(123456)).toBe("$1,235");
    expect(signedDollars(5000)).toBe("+$50");
    expect(signedDollars(-5000)).toBe("-$50");
    expect(signedDollars(20)).toBe("$0");
    expect(monthLabel("2026-10")).toBe("October 2026");
  });
});
