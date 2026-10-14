-- Dashboard queries, written by hand. Parameters: $1 account id, $2 start date (and $3 end date).
-- The runner reads this file; each query starts with a "-- name:" line.

-- name: q1_monthly_by_category
-- Spending per month and category since a start date (the main dashboard chart).
SELECT date_trunc('month', t.posted_on)::date AS month,
       c.name                                  AS category,
       sum(-t.amount_cents)::bigint            AS spent_cents
FROM transactions t
LEFT JOIN categories c ON c.id = t.category_id
WHERE t.account_id = $1::int
  AND t.amount_cents < 0
  AND t.posted_on >= $2::date
GROUP BY 1, 2
ORDER BY 1, 2;

-- name: q1_monthly_by_category_mv
SELECT m.month, c.name AS category, m.spent_cents::bigint AS spent_cents
FROM monthly_category_spend m
LEFT JOIN categories c ON c.id = m.category_id
WHERE m.account_id = $1::int
  AND m.month >= date_trunc('month', $2::date)::date
ORDER BY 1, 2;

-- name: q2_recent_transactions
-- The 50 newest transactions for the transactions table.
SELECT t.id, t.posted_on, t.amount_cents, t.description, c.name AS category
FROM transactions t
LEFT JOIN categories c ON c.id = t.category_id
WHERE t.account_id = $1::int
ORDER BY t.posted_on DESC, t.id DESC
LIMIT 50;

-- name: q3_top_categories_one_month
-- Where did the money go in a single month? ($2 inclusive start, $3 exclusive end)
SELECT c.name AS category, sum(-t.amount_cents)::bigint AS spent_cents
FROM transactions t
LEFT JOIN categories c ON c.id = t.category_id
WHERE t.account_id = $1::int
  AND t.amount_cents < 0
  AND t.posted_on >= $2::date AND t.posted_on < $3::date
GROUP BY c.name
ORDER BY spent_cents DESC;

-- name: q3_top_categories_one_month_mv
SELECT c.name AS category, m.spent_cents::bigint AS spent_cents
FROM monthly_category_spend m
LEFT JOIN categories c ON c.id = m.category_id
WHERE m.account_id = $1::int AND m.month = $2::date
ORDER BY spent_cents DESC;
