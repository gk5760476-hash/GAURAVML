-- Each block starts with "-- name: <id> | <severity> | <description>".
-- fail/warn blocks should return ZERO rows when healthy; info blocks are reports.

-- name: coverage | info | First/last date and row count per currency
SELECT currency, MIN(rate_date) AS first_date, MAX(rate_date) AS last_date, COUNT(*) AS n_rows
FROM eur_rates GROUP BY currency ORDER BY currency;

-- name: date_gaps | warn | Gaps of more than 5 calendar days within a currency series
SELECT currency, prev_date, rate_date,
       CAST(julianday(rate_date) - julianday(prev_date) AS INTEGER) AS gap_days
FROM (SELECT currency, rate_date,
             LAG(rate_date) OVER (PARTITION BY currency ORDER BY rate_date) AS prev_date
      FROM eur_rates)
WHERE prev_date IS NOT NULL AND julianday(rate_date) - julianday(prev_date) > 5;

-- name: extreme_moves | warn | Cross-rate daily moves larger than 10 percent
SELECT pair, rate_date, ROUND(simple_return * 100, 2) AS pct_move
FROM v_pair_daily_change WHERE ABS(simple_return) > 0.10;

-- name: stale_data | warn | Latest observation older than 7 days
SELECT last_date FROM (SELECT MAX(rate_date) AS last_date FROM eur_rates)
WHERE julianday('now') - julianday(last_date) > 7;

-- name: mixed_sources | fail | Database mixes real and simulated data
SELECT source, COUNT(*) AS n FROM eur_rates GROUP BY source
HAVING (SELECT COUNT(DISTINCT source) FROM eur_rates) > 1;

-- name: missing_eur_anchor | fail | Dates present for other currencies but missing the EUR=1 anchor row
SELECT DISTINCT a.rate_date FROM eur_rates a
WHERE NOT EXISTS (SELECT 1 FROM eur_rates e WHERE e.rate_date = a.rate_date AND e.currency = 'EUR');
