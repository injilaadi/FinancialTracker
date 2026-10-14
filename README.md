# FinancialTracker

Tracking my finances and categorizing where my money goes across all my bank accounts.

Upload a bank-statement CSV; each transaction is categorized automatically (rules baseline now, trained
ML model next), stored in PostgreSQL, and summarized in a dashboard of spending by category and month.

> **Status:** early build (Day 1 scaffold). Numbers in the results table below are filled in only after they are measured.

## Architecture

```
CSV upload -> FastAPI api (asyncpg) --batches--> Python ML service (FastAPI) --> category per description
                  |
                  +--> PostgreSQL (transactions, categories, budgets)
                  +--> Redis (planned: dashboard cache, rate limiting)
```

| Service | Tech | Port |
|---|---|---|
| `api/` | Python 3.12, FastAPI, asyncpg, httpx | 8080 |
| `ml/`  | Python, FastAPI, scikit-learn (planned) | 8001 |
| `db`   | PostgreSQL 16 (schema in `db/init.sql`) | 5432 |
| `redis`| Redis 7 | 6379 |

## Quickstart

```bash
docker compose up --build          # first run loads db/init.sql
curl localhost:8080/healthz

printf 'date,description,amount\n2026-10-01,SHELL OIL 5521,-40.25\n2026-10-02,UBER EATS ORDER 1,-18.00\n' > sample.csv
curl -F file=@sample.csv localhost:8080/import
curl localhost:8080/transactions
```

CSV columns: `date` (YYYY-MM-DD, M/D/YYYY, or year-less M/D; for M/D pass `?year=2025` to `/import`, otherwise the most recent past date is assumed), `description`, `amount` (negative = spending). Common bank header
names (`Transaction Date`, `Details`, ...) are accepted. Bad rows are skipped and reported in the response.

Set `IMPORT_WORKERS=4` to categorize import batches concurrently; the import response reports `categorize_ms`.

## Tests

```bash
cd ml  && pip install -r requirements-dev.txt && pytest
cd api && pip install -r requirements-dev.txt && pytest   # integration tests need TEST_DATABASE_URL (a Postgres DB); otherwise they are skipped
```

## Train and evaluate the categorizer

```bash
cd ml && pip install -r requirements-dev.txt
python eval.py ../data/private/labeled.csv        # rules baseline on your labeled statements
python train.py --data ../data/public/<dataset>.csv --desc-col "<description column>" \
    --cat-col "<category column>" --mapping ../data/public/mapping.json \
    --eval ../data/private/test.csv --out models/model.joblib
```

`data/seed/seed_merchants.csv` is a hand-written seed set (about 630 US merchants expanded into ~5,000
statement-style descriptors by `ml/make_seed.py`). Train on it alone with `--seed-data`, or add it to a
public dataset. Regenerate it with `python make_seed.py --out ../data/seed/seed_merchants.csv --check ../data/private/labeled.csv`;
`--check` fails if a seed merchant also appears in your labeled test set, so the test stays honest.

`--mapping` maps the public dataset's categories onto ours (see `data/public/mapping.example.json`);
unmapped categories are dropped. The model never trains on `labeled.csv`.

### Serving the model

The ML service loads `ml/models/model.joblib` if it exists (Compose mounts `ml/models/` read-only) and
otherwise runs on the keyword rules alone. Order per transaction: a rules keyword match wins; if there is
none, the model decides when its confidence is at least `MODEL_THRESHOLD` (default `0.0`); anything
below that becomes `Other`. `GET :8001/healthz` reports `model_loaded`. The model file is git-ignored.

```bash
cd ml && python train.py --seed-data ../data/seed/seed_merchants.csv \
    --extra-train ../data/private/dev.csv --eval ../data/private/test.csv   # writes models/model.joblib
docker compose up --build
```

Train with the pinned scikit-learn from `requirements.txt`, so the saved model loads inside the container.

## Results (to be measured)

| Metric | Result |
|---|---|
| Categorizer F1 vs rules baseline, on my own labeled statements | TBD |
| Import throughput, 1 worker vs N workers | TBD |
| Dashboard query time before/after index + materialized view (1M rows) | TBD |
| Dashboard latency with/without Redis | TBD |

## Roadmap

- [x] Schema, Compose stack, FastAPI api skeleton, CSV import, ML service with rules baseline, CI
- [ ] Hand-labeled test set (kept private) and baseline measurement
- [ ] scikit-learn categorizer (TF-IDF + logistic regression) trained on a public dataset
- [ ] Hand-written analytics SQL, indexes, materialized view, `EXPLAIN ANALYZE` timings
- [ ] Redis cache for dashboard aggregates
- [ ] React + TypeScript dashboard
- [ ] Stretch: forecasting, PyTorch categorizer comparison, Kubernetes (Helm, HPA)

## Data and privacy

Real statements and the labeled test set live in `data/private/` (git-ignored). Training data sources and
licenses will be listed here. This tool shows spending patterns only; it is not financial advice.
