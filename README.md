# FX Lab — INR exchange-rate analytics & forecasting evaluation

**Research question:** *Can machine-learning models improve on a random-walk benchmark when forecasting
daily INR exchange-rate movements, and how does this vary by currency pair and forecast horizon?*

This is an **evaluation platform, not a prediction product.** The FX literature (e.g. Rossi, 2013,
*Exchange Rate Predictability*, JEL) finds that beating the random walk is very hard; the value of this
project is a leak-free, statistically honest way to test that claim.

**Stack:** Python · SQLite/SQL · scikit-learn · Streamlit + Plotly · Frankfurter API (ECB reference rates)

## Quick start (macOS, Apple Silicon M1/M2/M3)

```bash
brew install python@3.12          # if you don't already have Python 3.10+
./setup.sh                        # venv + dependencies + database
source .venv/bin/activate

make data                         # download ECB rates since 2010 (internet needed, no API key)
make quality                      # SQL data-quality checks
make run                          # walk-forward evaluation: 6 INR pairs x 3 horizons x 5 models
make app                          # dashboard at http://localhost:8501
make test
```
No internet? `make demo` loads **simulated** data into a separate DB (`data/demo.db`), runs a quick
evaluation and opens the dashboard with a visible "SIMULATED" banner. Real and simulated data are never mixed.

No GPU, no heavy dependencies (no XGBoost/LightGBM, so no OpenMP install problems on macOS).
`make run` uses all cores; expect minutes, not hours (use `python -m fxlab run --quick` for a fast pass).

## What it does

| Layer | Implementation |
|---|---|
| Ingestion | `ingest.py` — chunked Frankfurter requests, retries, upserts, run log (`ingestion_runs`) |
| SQL | `sql/schema.sql` (tables, constraints, indexes, cross-rate **views**), `quality_checks.sql`, `analytics.sql` |
| Features | `features.py` — lagged returns, momentum, rolling volatility, MA deviation, cross-currency basket, day-of-week |
| Models | random walk (benchmark), historical mean, ridge, random forest, gradient boosting |
| Validation | expanding-window **walk-forward** with a horizon gap (no overlapping-target leakage) |
| Metrics | MAE, RMSE, RMSE ratio vs random walk, out-of-sample R², directional accuracy (+ binomial test), **Diebold–Mariano** (Newey–West, HLN correction) with **Holm** multiple-testing correction |
| UI | Overview · Rate explorer · Model comparison · Forecast diagnostics · Data & methodology |

All results (metrics + every out-of-sample prediction) are stored in SQLite, so the UI and ad-hoc SQL read the same truth.

## Conventions
`USD/INR = 87.0` means 1 USD buys 87 INR. Rates are stored EUR-based as published and crossed in SQL
(`v_pair_rates`). Targets are h-day log returns in percent. See `docs/METHODOLOGY.md`.

## Project status — what is and isn't verified
* ✅ Unit tests (12) pass: SQL cross rates, constraints, feature look-ahead, walk-forward leakage, DM test, end-to-end pipeline, API parsing (mocked).
* ✅ Full pipeline run on simulated data: no model significantly beats the random walk, as it should (no planted signal).
* ⚠️ **Not yet run against the live Frankfurter API or inside Streamlit** (built in an offline sandbox). First real run: `make data` and check `make quality`; if the API response shape or the INR start date differs from expectation, `ingest.py` / the quality report will show it. INR history may start later than other currencies; the pipeline uses the common date range and skips pairs with too little history.

## Attribution & disclaimer
Data: European Central Bank euro reference rates via [Frankfurter](https://frankfurter.dev). The ECB states these
rates are for information only and not for transactions. This project is for education and portfolio
purposes and is not financial advice.
