"""Integration tests: real FastAPI app + real PostgreSQL (schema from db/init.sql, indexes.sql, matview.sql).

Set TEST_DATABASE_URL to run them, e.g.
  TEST_DATABASE_URL=postgres://postgres:postgres@localhost:5432/financetracker_test pytest
They are skipped when it is not set.
"""
import asyncio
import json
import os
from dataclasses import replace
from datetime import date
from pathlib import Path

import asyncpg
import fakeredis
import httpx
import pytest
from fastapi.testclient import TestClient

from app.cache import SummaryCache

DSN = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="TEST_DATABASE_URL is not set")

DB_DIR = Path(__file__).resolve().parents[2] / "db"
SAMPLE = b"date,description,amount\n2026-10-01,SHELL OIL 5521,-40.25\n2026-10-02,UBER EATS ORDER 1,-18.00\n"
FAKE_RULES = {"SHELL": "Gas", "UBER EATS": "Dining"}


async def _reset_db() -> None:
    conn = await asyncpg.connect(DSN)
    try:
        for name in ("init.sql", "indexes.sql", "matview.sql"):
            await conn.execute((DB_DIR / name).read_text())
        await conn.execute("TRUNCATE transactions RESTART IDENTITY")
        await conn.execute("REFRESH MATERIALIZED VIEW monthly_category_spend")
    finally:
        await conn.close()


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", DSN)
    monkeypatch.delenv("ML_URL", raising=False)  # no ML service unless a test installs a fake
    asyncio.run(_reset_db())
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def install_fake_ml(client, status=200):
    def handler(request):
        if status != 200:
            return httpx.Response(status)
        descriptions = json.loads(request.content)["descriptions"]
        predictions = []
        for d in descriptions:
            category = next((c for key, c in FAKE_RULES.items() if key in d), "Other")
            predictions.append({"description": d, "category": category, "source": "rules", "matched": None})
        return httpx.Response(200, json={"predictions": predictions})

    app = client.app
    app.state.settings = replace(app.state.settings, ml_url="http://ml.test")
    app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))


def upload(client, content=SAMPLE):
    return client.post("/import", files={"file": ("sample.csv", content, "text/csv")})


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_and_list_transaction(client):
    created = client.post(
        "/transactions",
        json={"posted_on": "2026-10-01", "amount_cents": -1234, "description": "  COFFEE  "},
    )
    assert created.status_code == 201
    assert created.json() == {"id": 1}
    assert client.get("/transactions").json() == [
        {
            "id": 1,
            "posted_on": "2026-10-01",
            "amount_cents": -1234,
            "description": "COFFEE",
            "category": None,
            "category_source": "none",
        }
    ]


def test_create_validation(client):
    assert client.post("/transactions", json={"posted_on": "nope", "amount_cents": 1, "description": "x"}).status_code == 422
    assert client.post("/transactions", json={"posted_on": "2026-10-01", "amount_cents": 1, "description": "   "}).status_code == 422
    assert client.post("/transactions", json={"posted_on": "2026-10-01", "description": "x"}).status_code == 422


def test_list_limit_validation(client):
    assert client.get("/transactions?limit=0").status_code == 422
    assert client.get("/transactions?limit=501").status_code == 422
    assert client.get("/transactions?limit=5").status_code == 200


def test_import_without_ml_saves_uncategorized(client):
    body = upload(client).json()
    assert body["imported"] == 2
    assert body["categorized"] == 0
    assert body["skipped_rows"] == 0
    assert body["workers"] == 1
    listed = client.get("/transactions").json()
    assert [t["description"] for t in listed] == ["UBER EATS ORDER 1", "SHELL OIL 5521"]  # newest first
    assert all(t["category"] is None and t["category_source"] == "none" for t in listed)


def test_import_with_ml_sets_categories(client):
    install_fake_ml(client)
    response = upload(client)
    assert response.status_code == 200
    body = response.json()
    assert body["imported"] == 2 and body["categorized"] == 2
    assert "warning" not in body
    listed = {t["description"]: t for t in client.get("/transactions").json()}
    assert listed["SHELL OIL 5521"]["category"] == "Gas"
    assert listed["UBER EATS ORDER 1"]["category"] == "Dining"
    assert listed["SHELL OIL 5521"]["category_source"] == "rules"
    assert listed["SHELL OIL 5521"]["amount_cents"] == -4025


def test_import_survives_ml_failure(client):
    install_fake_ml(client, status=500)
    body = upload(client).json()
    assert body["imported"] == 2
    assert body["categorized"] == 0
    assert "warning" in body


def test_import_reports_bad_rows(client):
    content = b"date,description,amount\n2026-10-01,COFFEE,-3.00\nnot-a-date,BAD,-1.00\n"
    body = upload(client, content).json()
    assert body["imported"] == 1
    assert body["skipped_rows"] == 1
    assert body["row_errors"][0]["line"] == 3


def test_import_missing_column_is_400(client):
    response = upload(client, b"date,amount\n2026-10-01,5.00\n")
    assert response.status_code == 400
    assert "description" in response.json()["detail"]


def test_import_with_no_valid_rows_is_400(client):
    response = upload(client, b"date,description,amount\nnope,BAD,1.00\n")
    assert response.status_code == 400
    assert response.json()["error"] == "no valid rows found"
    assert len(response.json()["row_errors"]) == 1


def test_import_requires_a_file(client):
    assert client.post("/import").status_code == 422


def test_import_month_day_dates_with_year_param(client):
    csv_bytes = b"date,description,amount\n09/29,SQ *. TUSTIN CA,-5.00\n"
    response = client.post("/import?year=2025", files={"file": ("s.csv", csv_bytes, "text/csv")})
    assert response.status_code == 200
    assert response.json()["imported"] == 1
    assert client.get("/transactions").json()[0]["posted_on"] == "2025-09-29"


def test_import_year_param_validated(client):
    csv_bytes = b"date,description,amount\n09/29,COFFEE,-5.00\n"
    response = client.post("/import?year=12", files={"file": ("s.csv", csv_bytes, "text/csv")})
    assert response.status_code == 422


def test_summary_monthly_aggregates_spending_only(client):
    install_fake_ml(client)
    today = f"{date.today():%Y-%m-%d}"
    csv_bytes = (f"date,description,amount\n{today},SHELL OIL 5521,-40.25\n{today},UBER EATS ORDER 1,-18.00\n"
                 f"{today},UBER EATS ORDER 2,-2.00\n{today},PAYROLL,2000.00\n").encode()
    assert upload(client, csv_bytes).status_code == 200
    body = client.get("/summary/monthly").json()
    month = today[:7]
    # money out only: the payroll deposit is not counted
    assert {(r["month"], r["category"]): (r["spent_cents"], r["transaction_count"]) for r in body} == {
        (month, "Dining"): (2000, 2),
        (month, "Gas"): (4025, 1),
    }


def test_summary_monthly_updates_after_manual_transaction_and_counts_uncategorized(client):
    today = f"{date.today():%Y-%m-%d}"
    response = client.post("/transactions", json={"posted_on": today, "amount_cents": -750, "description": "COFFEE"})
    assert response.status_code == 201
    body = client.get("/summary/monthly?months=1").json()
    assert body == [{"month": today[:7], "category": None, "spent_cents": 750, "transaction_count": 1}]


def test_summary_monthly_window_and_validation(client):
    old = "2019-01-15"
    client.post("/transactions", json={"posted_on": old, "amount_cents": -100, "description": "OLD"})
    assert client.get("/summary/monthly?months=12").json() == []  # outside the window
    assert client.get("/summary/monthly?months=0").status_code == 422
    assert client.get("/summary/monthly?months=61").status_code == 422


def install_cache(client):
    server = fakeredis.FakeServer()
    client.app.state.cache = SummaryCache(fakeredis.FakeAsyncRedis(server=server, decode_responses=True), 60)
    return server


def _post_today(client, cents, description="COFFEE"):
    today = f"{date.today():%Y-%m-%d}"
    assert client.post("/transactions", json={"posted_on": today, "amount_cents": cents, "description": description}).status_code == 201


def test_summary_without_cache_reports_bypass(client):
    assert client.get("/summary/monthly").headers["X-Cache"] == "BYPASS"


def test_summary_miss_then_hit_with_identical_body(client):
    install_cache(client)
    _post_today(client, -750)
    first = client.get("/summary/monthly")
    second = client.get("/summary/monthly")
    assert (first.headers["X-Cache"], second.headers["X-Cache"]) == ("MISS", "HIT")
    assert first.json() == second.json() and first.json()[0]["spent_cents"] == 750


def test_write_invalidates_cache(client):
    install_cache(client)
    _post_today(client, -750)
    assert client.get("/summary/monthly").json()[0]["spent_cents"] == 750  # now cached
    _post_today(client, -250)
    after = client.get("/summary/monthly")
    assert after.headers["X-Cache"] == "MISS"  # the write cleared the cached copy
    assert after.json()[0]["spent_cents"] == 1000


def test_import_invalidates_cache(client):
    install_cache(client)
    _post_today(client, -100)
    client.get("/summary/monthly")
    today = f"{date.today():%Y-%m-%d}"
    assert upload(client, f"date,description,amount\n{today},TEST,-900.00\n".encode()).status_code == 200
    after = client.get("/summary/monthly")
    assert after.headers["X-Cache"] == "MISS" and after.json()[0]["spent_cents"] == 90100


def test_summary_still_works_when_redis_is_down(client):
    server = install_cache(client)
    _post_today(client, -750)
    server.connected = False
    response = client.get("/summary/monthly")
    assert response.status_code == 200 and response.json()[0]["spent_cents"] == 750
