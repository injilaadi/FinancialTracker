import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, type DailySpend, type MonthlySpend, type Transaction } from "../api";
import { previousMonth } from "../derive";

type Status = "loading" | "ready" | "error";

export interface Dashboard {
  status: Status;
  error: string | null;
  refreshing: boolean;
  monthly: MonthlySpend[];
  transactions: Transaction[];
  dailyThis: DailySpend[];
  dailyPrev: DailySpend[];
  reload: () => void;
}

/**
 * Loads the monthly summary and recent transactions once, then the two daily series for whichever
 * month is selected. Old data stays on screen while a refetch runs, so switching months never blanks the page.
 */
export function useDashboard(month: string | null): Dashboard {
  const [status, setStatus] = useState<Status>("loading");
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [monthly, setMonthly] = useState<MonthlySpend[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [dailyThis, setDailyThis] = useState<DailySpend[]>([]);
  const [dailyPrev, setDailyPrev] = useState<DailySpend[]>([]);
  const [tick, setTick] = useState(0);
  const ticket = useRef(0);

  useEffect(() => {
    const mine = ++ticket.current;
    setRefreshing(true);
    (async () => {
      try {
        const [m, t] = await Promise.all([api.monthly(), api.transactions()]);
        if (mine !== ticket.current) return;
        setMonthly(m);
        setTransactions(t);
        setError(null);
        setStatus("ready");
      } catch (e) {
        if (mine !== ticket.current) return;
        setError(e instanceof ApiError ? e.message : "Something went wrong loading your data.");
        setStatus((s) => (s === "ready" ? s : "error"));
      } finally {
        if (mine === ticket.current) setRefreshing(false);
      }
    })();
  }, [tick]);

  useEffect(() => {
    if (!month) return;
    const mine = ++ticket.current;
    (async () => {
      try {
        const [a, b] = await Promise.all([api.daily(month), api.daily(previousMonth(month))]);
        if (mine !== ticket.current) return;
        setDailyThis(a);
        setDailyPrev(b);
      } catch (e) {
        if (mine !== ticket.current) return;
        setError(e instanceof ApiError ? e.message : "Couldn't load the daily breakdown.");
      }
    })();
  }, [month, tick]);

  const reload = useCallback(() => setTick((n) => n + 1), []);
  return { status, error, refreshing, monthly, transactions, dailyThis, dailyPrev, reload };
}
