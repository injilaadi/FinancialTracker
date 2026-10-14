-- Index added AFTER measuring the unindexed baseline (see bench/run_benchmark.py).
-- Leading account_id: every dashboard query is for one account.
-- posted_on DESC, id DESC: matches "newest first" ordering, so LIMIT 50 stops early.
-- INCLUDE: lets the aggregation queries be answered from the index alone (index-only scan).
CREATE INDEX IF NOT EXISTS idx_transactions_account_posted
    ON transactions (account_id, posted_on DESC, id DESC)
    INCLUDE (amount_cents, category_id);
