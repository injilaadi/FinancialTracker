"""FinancialTracker API: transactions, CSV import, and categorization via the ML service."""
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import date

import asyncpg
import httpx
from fastapi import FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.cache import SummaryCache
from app.config import load_settings
from app.ml_client import categorize_all
from app.parsing import CSVFormatError, parse_csv

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    app.state.settings = settings
    # A pool keeps several connections open and reuses them across requests.
    app.state.pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=10)
    app.state.http = httpx.AsyncClient(timeout=15.0)
    app.state.cache = (
        SummaryCache.from_url(settings.redis_url, settings.cache_ttl_seconds)
        if settings.redis_url and settings.cache_enabled
        else None
    )
    logger.info("api started (ml=%r, import workers=%d, cache=%s)",
                settings.ml_url, settings.import_workers, "on" if app.state.cache else "off")
    try:
        yield
    finally:
        if app.state.cache is not None:
            await app.state.cache.close()
        await app.state.http.aclose()
        await app.state.pool.close()


app = FastAPI(title="FinancialTracker API", lifespan=lifespan)


async def refresh_summary(state) -> None:
    """Rebuild the monthly summary after data changes. CONCURRENTLY: readers are not blocked.

    The summary is a materialized view (db/matview.sql), so it is only as fresh as the last
    refresh. A failed refresh must not fail the write that triggered it.
    """
    try:
        await state.pool.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_category_spend")
    except Exception:  # noqa: BLE001
        logger.warning("could not refresh monthly_category_spend", exc_info=True)
    if state.cache is not None:
        await state.cache.invalidate()  # after the refresh, so a reader cannot re-cache old data


@app.get("/healthz")
async def healthz(request: Request) -> dict[str, str]:
    try:
        await asyncio.wait_for(request.app.state.pool.fetchval("SELECT 1"), timeout=2)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=503, detail="database unavailable") from None
    return {"status": "ok"}


class TransactionIn(BaseModel):
    posted_on: date
    amount_cents: int
    description: str = Field(min_length=1)

    @field_validator("description")
    @classmethod
    def description_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("description is required")
        return value


class TransactionOut(BaseModel):
    id: int
    posted_on: str
    amount_cents: int
    description: str
    category: str | None
    category_source: str


@app.post("/transactions", status_code=201)
async def create_transaction(body: TransactionIn, request: Request) -> dict[str, int]:
    # Parameterized query ($1, $2, ...): values are sent separately from the SQL text,
    # which is what prevents SQL injection.
    row = await request.app.state.pool.fetchrow(
        """INSERT INTO transactions (account_id, posted_on, amount_cents, description)
           VALUES ((SELECT id FROM accounts ORDER BY id LIMIT 1), $1, $2, $3)
           RETURNING id""",
        body.posted_on,
        body.amount_cents,
        body.description,
    )
    await refresh_summary(request.app.state)
    return {"id": row["id"]}


@app.get("/transactions", response_model=list[TransactionOut])
async def list_transactions(request: Request, limit: int = Query(50, ge=1, le=500)):
    rows = await request.app.state.pool.fetch(
        """SELECT t.id, t.posted_on::text AS posted_on, t.amount_cents, t.description,
                  c.name AS category, t.category_source
           FROM transactions t
           LEFT JOIN categories c ON c.id = t.category_id
           ORDER BY t.posted_on DESC, t.id DESC
           LIMIT $1""",
        limit,
    )
    return [dict(row) for row in rows]


class MonthlySpend(BaseModel):
    month: str  # "YYYY-MM"
    category: str | None  # None = uncategorized
    spent_cents: int
    transaction_count: int


@app.get("/summary/monthly", response_model=list[MonthlySpend])
async def monthly_summary(request: Request, response: Response, months: int = Query(12, ge=1, le=60)):
    """Spending (money out) per month and category for the last `months` months.

    Read from the pre-aggregated monthly_category_spend view, so it stays fast on millions of rows.
    Cached in Redis when configured; the X-Cache header says HIT, MISS, or BYPASS (no cache).
    """
    cache = request.app.state.cache
    if cache is not None:
        cached = await cache.get(months)
        if cached is not None:
            response.headers["X-Cache"] = "HIT"
            return cached
    response.headers["X-Cache"] = "MISS" if cache is not None else "BYPASS"
    try:
        rows = await request.app.state.pool.fetch(
            """SELECT to_char(m.month, 'YYYY-MM') AS month, c.name AS category,
                      m.spent_cents::bigint AS spent_cents, m.transaction_count::int AS transaction_count
               FROM monthly_category_spend m
               LEFT JOIN categories c ON c.id = m.category_id
               WHERE m.account_id = (SELECT id FROM accounts ORDER BY id LIMIT 1)
                 AND m.month >= (date_trunc('month', current_date) - make_interval(months => $1::int - 1))::date
               ORDER BY m.month, c.name""",
            months,
        )
    except asyncpg.UndefinedTableError:
        raise HTTPException(status_code=503, detail="summary view missing; apply db/matview.sql") from None
    payload = [dict(row) for row in rows]
    if cache is not None:
        await cache.set(months, payload)
    return payload


class DailySpend(BaseModel):
    date: str  # "YYYY-MM-DD"
    spent_cents: int
    transaction_count: int


@app.get("/summary/daily", response_model=list[DailySpend])
async def daily_summary(request: Request, month: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$")):
    """Spending (money out) per day for one month, e.g. month=2026-09. Days with no spending are omitted.

    Uses the (account_id, posted_on) index on transactions, so it reads only that month's rows.
    """
    year, month_number = int(month[:4]), int(month[5:])
    start = date(year, month_number, 1)
    end = date(year + 1, 1, 1) if month_number == 12 else date(year, month_number + 1, 1)
    rows = await request.app.state.pool.fetch(
        """SELECT posted_on::text AS date, sum(-amount_cents)::bigint AS spent_cents,
                  count(*)::int AS transaction_count
           FROM transactions
           WHERE account_id = (SELECT id FROM accounts ORDER BY id LIMIT 1)
             AND amount_cents < 0 AND posted_on >= $1 AND posted_on < $2
           GROUP BY posted_on ORDER BY posted_on""",
        start,
        end,
    )
    return [dict(row) for row in rows]


@app.post("/import")
async def import_csv(
    request: Request,
    file: UploadFile = File(...),
    year: int | None = Query(None, ge=1990, le=2100, description="Year for dates written as MM/DD"),
):
    settings = request.app.state.settings

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="file too large (max 10 MB)")
    try:
        parsed = parse_csv(content, year=year)
    except CSVFormatError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    if not parsed.rows:
        return JSONResponse(
            status_code=400,
            content={"error": "no valid rows found", "row_errors": [asdict(e) for e in parsed.errors]},
        )

    descriptions = [row.description for row in parsed.rows]
    predictions: list[dict | None] = [None] * len(descriptions)  # None = uncategorized
    warning = None
    started = time.perf_counter()
    if settings.ml_url:
        predictions, error = await categorize_all(
            request.app.state.http,
            settings.ml_url,
            descriptions,
            settings.import_workers,
            settings.ml_batch_size,
        )
        if error is not None:
            logger.warning("categorization partly failed: %s", error)
            warning = "some rows could not be categorized and were saved uncategorized"
    categorize_ms = int((time.perf_counter() - started) * 1000)

    async with request.app.state.pool.acquire() as conn:
        category_ids = {r["name"]: r["id"] for r in await conn.fetch("SELECT id, name FROM categories")}
        account_id = await conn.fetchval("SELECT id FROM accounts ORDER BY id LIMIT 1")
        if account_id is None:
            raise HTTPException(status_code=500, detail="no account configured")

        records = []
        categorized = 0
        for row, prediction in zip(parsed.rows, predictions):
            category_id, source = None, "none"
            if (
                prediction
                and prediction.get("source") in ("rules", "model")
                and prediction.get("category") in category_ids
            ):
                category_id = category_ids[prediction["category"]]
                source = prediction["source"]
                categorized += 1
            records.append((account_id, row.posted_on, row.amount_cents, row.description, category_id, source))

        # COPY is Postgres's bulk-load path: much faster than inserting row by row.
        await conn.copy_records_to_table(
            "transactions",
            records=records,
            columns=["account_id", "posted_on", "amount_cents", "description", "category_id", "category_source"],
        )

    await refresh_summary(request.app.state)

    response = {
        "imported": len(records),
        "categorized": categorized,
        "skipped_rows": parsed.skipped,
        "row_errors": [asdict(e) for e in parsed.errors],
        "categorize_ms": categorize_ms,
        "workers": settings.import_workers,
    }
    if warning:
        response["warning"] = warning
    return response
