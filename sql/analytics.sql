-- name: monthly_average | Monthly average rate per pair
SELECT pair, substr(rate_date,1,7) AS month, ROUND(AVG(rate),4) AS avg_rate
FROM v_pair_rates GROUP BY pair, month ORDER BY pair, month;

-- name: annual_volatility | Annualised volatility of daily % moves, by year (SQLite has no STDDEV)
SELECT pair, substr(rate_date,1,4) AS year,
       ROUND(100 * SQRT(MAX(AVG(simple_return*simple_return) - AVG(simple_return)*AVG(simple_return), 0)) * SQRT(252), 2) AS ann_vol_pct,
       COUNT(simple_return) AS n_days
FROM v_pair_daily_change WHERE simple_return IS NOT NULL
GROUP BY pair, year ORDER BY pair, year;

-- name: largest_daily_moves | Ten largest one-day moves per pair
SELECT pair, rate_date, ROUND(simple_return*100,3) AS pct_move FROM (
  SELECT pair, rate_date, simple_return,
         ROW_NUMBER() OVER (PARTITION BY pair ORDER BY ABS(simple_return) DESC) AS rk
  FROM v_pair_daily_change WHERE simple_return IS NOT NULL)
WHERE rk <= 10 ORDER BY pair, rk;

-- name: best_models | Models with RMSE below the random walk, best first
SELECT run_id, pair, horizon, model, ROUND(rel_rmse,4) AS rel_rmse, ROUND(dm_p,4) AS dm_p, ROUND(dm_p_holm,4) AS dm_p_holm
FROM metrics WHERE model <> 'random_walk' AND rel_rmse < 1 ORDER BY rel_rmse;
