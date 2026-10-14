-- Pre-aggregated monthly spending per account and category. Reads that used to scan and
-- group thousands of transactions become a lookup of a few dozen rows.
-- category_id 0 stands for "uncategorized" so every row has a non-null unique key.
-- Refresh after imports:  REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_category_spend;
CREATE MATERIALIZED VIEW IF NOT EXISTS monthly_category_spend AS
SELECT account_id,
       date_trunc('month', posted_on)::date AS month,
       COALESCE(category_id, 0)             AS category_id,
       count(*)                             AS transaction_count,
       sum(-amount_cents)                   AS spent_cents
FROM transactions
WHERE amount_cents < 0
GROUP BY account_id, date_trunc('month', posted_on)::date, COALESCE(category_id, 0);

-- Required for REFRESH ... CONCURRENTLY (readers are not blocked during a refresh).
CREATE UNIQUE INDEX IF NOT EXISTS idx_monthly_category_spend_key
    ON monthly_category_spend (account_id, month, category_id);
