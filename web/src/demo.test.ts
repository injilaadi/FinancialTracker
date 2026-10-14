import { describe, expect, it } from "vitest";
import { demoApi, demoTransactions } from "./demo";

const today = new Date(2026, 9, 14);

describe("demo data", () => {
  it("is deterministic and never dated in the future", () => {
    expect(demoTransactions(today)).toEqual(demoTransactions(today));
    expect(demoTransactions(today).every((t) => t.posted_on <= "2026-10-14")).toBe(true);
  });
  it("covers three months and every amount is money out", () => {
    const api = demoApi(today);
    expect([...new Set(api.monthly().map((r) => r.month))]).toEqual(["2026-08", "2026-09", "2026-10"]);
    expect(demoTransactions(today).every((t) => t.amount_cents < 0)).toBe(true);
  });
  it("monthly and daily totals agree", () => {
    const api = demoApi(today);
    const monthTotal = api.monthly().filter((r) => r.month === "2026-09").reduce((a, r) => a + r.spent_cents, 0);
    const dayTotal = api.daily("2026-09").reduce((a, r) => a + r.spent_cents, 0);
    expect(dayTotal).toBe(monthTotal);
  });
  it("returns newest transactions first, limited", () => {
    const rows = demoApi(today).transactions(5);
    expect(rows).toHaveLength(5);
    expect(rows[0].posted_on >= rows[4].posted_on).toBe(true);
  });
});
