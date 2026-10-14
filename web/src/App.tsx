import { useEffect, useMemo, useState } from "react";
import { Categories } from "./components/Categories";
import { CumulativeChart } from "./components/CumulativeChart";
import { ImportDialog } from "./components/ImportDialog";
import { TotalSpentCard } from "./components/TotalSpentCard";
import { TransactionsTable } from "./components/TransactionsTable";
import { breakdown, colorSlots, monthTotal, monthsAvailable, pace } from "./derive";
import { monthLabel } from "./format";
import { DEMO } from "./demo";
import { useDashboard } from "./hooks/useDashboard";

export function App() {
  const [selected, setSelected] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const data = useDashboard(selected);
  const today = useMemo(() => new Date(), []);

  const months = useMemo(() => monthsAvailable(data.monthly), [data.monthly]);
  const month = selected && months.includes(selected) ? selected : (months[0] ?? null);
  useEffect(() => {
    if (!selected && month) setSelected(month);
  }, [selected, month]);

  const slots = useMemo(() => colorSlots(data.monthly), [data.monthly]);
  const rows = useMemo(() => (month ? breakdown(data.monthly, month, slots) : []), [data.monthly, month, slots]);
  const p = useMemo(() => (month ? pace(data.monthly, data.dailyPrev, month, today) : null), [data.monthly, data.dailyPrev, month, today]);

  return (
    <div className="shell">
      <aside className="sidebar" aria-label="Main">
        <div className="brand">
          <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true">
            <rect width="26" height="26" rx="7" fill="var(--brand)" />
            <path d="M6 18l5-6 4 3 5-8" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span>FinancialTracker</span>
        </div>
        <nav>
          <a href="#top" className="nav-item current" aria-current="page">Overview</a>
          <a href="#transactions" className="nav-item">Transactions</a>
          <button type="button" className="nav-item" onClick={() => setImporting(true)}>Import statement</button>
        </nav>
        <p className="side-note">Informational only. Not financial advice.</p>
      </aside>

      <main id="top" className="main">
        <header className="topbar">
          <div>
            <h1>{month ? monthLabel(month) : "Spending overview"}</h1>
            {data.refreshing && data.status === "ready" && <span className="muted small">Refreshing...</span>}
          </div>
          <div className="controls">
            {months.length > 0 && (
              <label className="select">
                <span className="sr-only">Month</span>
                <select value={month ?? ""} onChange={(e) => setSelected(e.target.value)}>
                  {months.map((m) => <option key={m} value={m}>{monthLabel(m)}</option>)}
                </select>
              </label>
            )}
            <button type="button" className="btn primary" onClick={() => setImporting(true)}>Import CSV</button>
          </div>
        </header>

        {DEMO && (
          <p className="demo-banner" role="note">
            Demo with made-up sample data. The full app runs locally with your own statements; see the GitHub README.
          </p>
        )}

        {data.error && (
          <div className="notice error" role="alert">
            <p>{data.error}</p>
            <button type="button" className="btn ghost" onClick={data.reload}>Try again</button>
          </div>
        )}

        {data.status === "loading" && <p className="empty" role="status">Loading your spending...</p>}

        {data.status === "ready" && !month && (
          <section className="card empty-state">
            <h2>No spending yet</h2>
            <p>Import a bank statement CSV and your totals, categories and trends will show up here.</p>
            <button type="button" className="btn primary" onClick={() => setImporting(true)}>Import a statement</button>
          </section>
        )}

        {month && p && (
          <div className="grid">
            <TotalSpentCard month={month} pace={p} count={monthTotal(data.monthly, month).count} />
            <CumulativeChart month={month} elapsedDays={p.elapsedDays} dailyThis={data.dailyThis} dailyPrev={data.dailyPrev} />
            <Categories month={month} rows={rows} totalCents={p.totalCents} />
            <TransactionsTable rows={data.transactions} />
          </div>
        )}
      </main>

      <ImportDialog open={importing} onClose={() => setImporting(false)} onImported={data.reload} />
    </div>
  );
}
