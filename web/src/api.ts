// Thin typed client for the FastAPI service. In dev and in Docker the browser calls /api/*,
// which the dev server / nginx forwards to the API (see vite.config.ts and nginx.conf).

export type CategorySource = "none" | "rules" | "model" | "user";

export interface MonthlySpend {
  month: string; // "YYYY-MM"
  category: string | null; // null = uncategorized
  spent_cents: number;
  transaction_count: number;
}

export interface DailySpend {
  date: string; // "YYYY-MM-DD"
  spent_cents: number;
  transaction_count: number;
}

export interface Transaction {
  id: number;
  posted_on: string; // "YYYY-MM-DD"
  amount_cents: number; // negative = money out
  description: string;
  category: string | null;
  category_source: CategorySource;
}

export interface RowError {
  line: number;
  message: string;
}

export interface ImportResult {
  imported: number;
  categorized: number;
  skipped_rows: number;
  row_errors: RowError[];
  categorize_ms: number;
  workers: number;
  warning?: string;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number | null,
    readonly rowErrors: RowError[] = [],
  ) {
    super(message);
  }
}

import { DEMO, demoApi } from "./demo";

const BASE = "/api";

async function readError(response: Response): Promise<ApiError> {
  let message = `Request failed (${response.status})`;
  let rowErrors: RowError[] = [];
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") message = body.detail;
    else if (Array.isArray(body?.detail)) message = "The request was not valid.";
    else if (typeof body?.error === "string") message = body.error;
    if (Array.isArray(body?.row_errors)) rowErrors = body.row_errors;
  } catch {
    /* keep the generic message */
  }
  return new ApiError(message, response.status, rowErrors);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, init);
  } catch {
    throw new ApiError("Can't reach the API. Check that it is running.", null);
  }
  if (!response.ok) throw await readError(response);
  return (await response.json()) as T;
}

const live = {
  monthly: (months = 60) => request<MonthlySpend[]>(`/summary/monthly?months=${months}`),
  daily: (month: string) => request<DailySpend[]>(`/summary/daily?month=${encodeURIComponent(month)}`),
  transactions: (limit = 15) => request<Transaction[]>(`/transactions?limit=${limit}`),
  importCsv(file: File, year?: number) {
    const form = new FormData();
    form.append("file", file);
    const query = year ? `?year=${year}` : "";
    return request<ImportResult>(`/import${query}`, { method: "POST", body: form });
  },
};

const demo = DEMO ? demoApi() : null;

/** In demo mode (VITE_DEMO=true at build time) everything is served from generated sample data. */
export const api: typeof live = demo
  ? {
      monthly: async () => demo.monthly(),
      daily: async (month: string) => demo.daily(month),
      transactions: async (limit = 15) => demo.transactions(limit),
      importCsv: async () => {
        throw new ApiError("Importing is turned off in the demo. Run the full stack locally to import your own CSV.", null);
      },
    }
  : live;
