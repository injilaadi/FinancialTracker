-- Synthetic data for benchmarking ONLY. Run against a throwaway benchmark database.
-- 20 fake accounts; __ROWS__ transactions spread over five years (2021-10-01 .. 2026-09-30).
-- ~8% income (positive), the rest spending skewed toward the first categories; ~5% uncategorized.
SELECT setseed(0.42);

INSERT INTO accounts (name, institution)
SELECT 'SYNTHETIC ' || g, 'synthetic' FROM generate_series(1, 20) AS g;

WITH syn AS (
    SELECT array_agg(id ORDER BY id) AS account_ids FROM accounts WHERE institution = 'synthetic'
), spend_cats AS (
    SELECT array_agg(id ORDER BY id) AS ids FROM categories WHERE name <> 'Income'
), income_cat AS (
    SELECT id FROM categories WHERE name = 'Income'
), merchants AS (
    SELECT ARRAY['WHOLE FOODS MKT','TRADER JOES','SHELL OIL','CHEVRON','STARBUCKS','CHIPOTLE','UBER TRIP',
                 'NETFLIX.COM','SPOTIFY USA','AMAZON MKTPL','TARGET','CVS PHARMACY','AMC THEATRES',
                 'DELTA AIR LINES','SOUTHERN CALIF EDISON','COMCAST CABLE','APARTMENT RENT PAYMENT'] AS names
)
INSERT INTO transactions (account_id, posted_on, amount_cents, description, category_id, category_source)
SELECT syn.account_ids[1 + (s % 20)],
       DATE '2021-10-01' + (x.r1 * 1825)::int,
       CASE WHEN x.r2 < 0.08 THEN 100000 + (x.r3 * 400000)::bigint
            ELSE -(100 + (x.r3 * x.r4 * 20000)::bigint) END,
       merchants.names[1 + (x.r5 * 17)::int % 17] || ' ' || (x.r6 * 99999)::int,
       CASE WHEN x.r2 < 0.08 THEN income_cat.id
            WHEN x.r7 < 0.05 THEN NULL
            ELSE spend_cats.ids[1 + floor(power(x.r8, 1.6) * array_length(spend_cats.ids, 1))::int] END,
       'rules'
FROM generate_series(1, __ROWS__) AS s
CROSS JOIN syn CROSS JOIN spend_cats CROSS JOIN income_cat CROSS JOIN merchants
CROSS JOIN LATERAL (
    SELECT random() AS r1, random() AS r2, random() AS r3, random() AS r4,
           random() AS r5, random() AS r6, random() AS r7, random() AS r8
    WHERE s > 0                      -- references s so the random values are drawn per row
) AS x;
