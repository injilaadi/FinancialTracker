"""FinancialTracker API: transactions, CSV import, and categorization via the ML service."""
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import date

import asyncpg
import httpx
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

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
    logger.info("api started (ml=%r, import workers=%d)", settings.ml_url, settings.import_workers)
    try:
        yield
    finally:
        await app.state.http.aclose()
        await app.state.pool.close()


app = FastAPI(title="FinancialTracker API", lifespan=lifespan)


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
