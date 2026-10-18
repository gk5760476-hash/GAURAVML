# Methodology, data dictionary & risk notes

## Data dictionary
| Table / column | Meaning |
|---|---|
| `eur_rates.rate` | Units of `currency` per 1 EUR (ECB reference rate, working days ~16:00 CET). EUR rows = 1.0 anchors |
| `pairs.pair` | `BASE/QUOTE`, e.g. `USD/INR` = INR per 1 USD |
| `v_pair_rates.rate` | `quote_rate / base_rate` computed in SQL |
| `v_pair_daily_change.simple_return` | `rate / previous rate - 1` |
| `predictions.y_true / y_pred` | Realised / predicted h-day log return, **percent**; `pred_date` = forecast origin |
| `metrics.rel_rmse` | RMSE ÷ random-walk RMSE (<1 better) |
| `metrics.oos_r2` | 1 − SSE/SSE(random walk) |
| `metrics.dm_p`, `dm_p_holm` | One-sided Diebold–Mariano p-value (H1: model beats benchmark), raw and Holm-adjusted |

## Features (all known at the close of day *t*)
`ret_l{1,2,3,5,10,20}` lagged daily returns · `ret_mean{5,20}` · `vol{5,20,60}` · `mom{5,20,60}` ·
`dev_ma{20,60}` · `vol_ratio_5_60` · `basket_l1`, `basket_mean5` (average return of the other pairs) · day-of-week sin/cos.
Test `test_no_lookahead_in_features` proves that altering future prices does not change past features.

## Validation design
* Target `y_t = 100·(ln P_{t+h} − ln P_t)`, h ∈ {1, 5, 20} trading days.
* Expanding window; first 1000 rows are the minimum training set; models are refit every 63 rows (default).
* For a test block starting at row *s*, training uses rows ≤ *s − h* only, so no training target overlaps the test period
  (`test_training_targets_realised_before_test_block`).
* Hyper-parameters are fixed and deliberately conservative (shallow trees, regularisation); ridge picks its
  penalty with time-ordered inner CV. No tuning on the test period.

## Inference
Squared-error loss differential vs. random walk → Diebold–Mariano with Newey–West variance (h−1 lags) and the
Harvey–Leybourne–Newbold small-sample correction. Because dozens of tests are run (pairs × horizons × models),
Holm-adjusted p-values are the ones to trust. Directional accuracy is tested against 50% with a binomial test.

## Limitations
ECB fixings are daily snapshots, not tradable quotes; no transaction costs or slippage; overlapping targets for h>1
induce autocorrelation (handled in the DM test, not elsewhere); results depend on sample period and
structural breaks (e.g. RBI interventions, regime changes); synthetic data is only for software demonstration.

## Responsible communication
Say "evaluation of forecast accuracy", never "predicts the rupee". Report negative results (the benchmark often wins).
Never present backtest metrics as expected future returns.
