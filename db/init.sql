-- Schema for FinancialTracker. Loaded automatically on first start of an empty Postgres volume.
-- To re-run after changes:  docker compose down -v && docker compose up --build

CREATE TABLE IF NOT EXISTS categories (
    id   SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    institution TEXT
);

CREATE TABLE IF NOT EXISTS transactions (
    id              BIGSERIAL PRIMARY KEY,
    account_id      INT REFERENCES accounts(id),
    posted_on       DATE   NOT NULL,
    amount_cents    BIGINT NOT NULL,            -- negative = money out, positive = money in
    description     TEXT   NOT NULL,            -- raw bank text, e.g. 'SQ *BLUE BOTTLE 0423 SF'
    category_id     INT REFERENCES categories(id),
    category_source TEXT   NOT NULL DEFAULT 'none'
                    CHECK (category_source IN ('none', 'rules', 'model', 'user')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- NOTE (deliberate): this file creates the transactions table WITHOUT secondary indexes.
-- db/indexes.sql and db/matview.sql add them (Compose loads them right after this file), and
-- db/bench/run_benchmark.py applies them one at a time to measure before/after timings.

CREATE TABLE IF NOT EXISTS budgets (
    id          SERIAL PRIMARY KEY,
    category_id INT  NOT NULL REFERENCES categories(id),
    month       DATE NOT NULL,                  -- first day of the month
    limit_cents BIGINT NOT NULL CHECK (limit_cents >= 0),
    UNIQUE (category_id, month)
);

INSERT INTO categories (name) VALUES
    ('Groceries'), ('Dining'), ('Transport'), ('Gas'), ('Subscriptions'),
    ('Shopping'), ('Rent'), ('Utilities'), ('Health'), ('Entertainment'),
    ('Travel'), ('Income'), ('Other')
ON CONFLICT (name) DO NOTHING;

INSERT INTO accounts (name, institution)
SELECT 'Default account', NULL
WHERE NOT EXISTS (SELECT 1 FROM accounts);
