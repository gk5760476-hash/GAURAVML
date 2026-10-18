# FX Lab — INR exchange-rate analytics & forecasting evaluation

**Research question:** *Can machine-learning models improve on a random-walk benchmark when forecasting
daily INR exchange-rate movements, and how does this vary by currency pair and forecast horizon?*

This is an **evaluation platform, not a prediction product.** The FX literature (e.g. Rossi, 2013,
*Exchange Rate Predictability*, JEL) finds that beating the random walk is very hard; the value of this
project is a leak-free, statistically honest way to test that claim.

**Stack:** Python · SQLite/SQL · scikit-learn · Streamlit + Plotly · Frankfurter API (ECB reference rates)

## Quick start

Python 3.10 or newer is required. The commands below create a project-local virtual environment and install FX Lab with its development dependencies.

### macOS

```bash
brew install python@3.12          # if Python 3.10+ is not installed
./setup.sh                        # creates .venv, installs dependencies, initializes data/fx.db
source .venv/bin/activate          # activate the environment in this terminal

python -m fxlab ingest            # fetch real Frankfurter rates (internet required, no API key)
python -m fxlab quality           # run SQL data-quality checks
python -m fxlab run --quick       # evaluate all pairs/horizons (omit --quick for a longer run)
python -m fxlab app               # open the dashboard at http://localhost:8501
python -m pytest -q               # run tests
```

Alternatively, after activating `.venv`, use `make data`, `make quality`, `make run`, `make app`, and `make test`.

### Windows (PowerShell)

Install Python 3.10+ from [python.org](https://www.python.org/downloads/windows/) and enable **Add python.exe to PATH** in the installer. From the repository folder, run:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
python -m fxlab init

python -m fxlab ingest            # fetch real Frankfurter rates (internet required, no API key)
python -m fxlab quality           # run SQL data-quality checks
python -m fxlab run --quick       # evaluate all pairs/horizons (omit --quick for a longer run)
python -m fxlab app               # open the dashboard at http://localhost:8501
python -m pytest -q               # run tests
```

If PowerShell prevents virtual-environment activation, use Command Prompt and activate with `.venv\Scripts\activate.bat`, then run the same `python` and `pip` commands.

### Offline demo (macOS or Windows)

No internet? Simulated data is stored in a separate database and never mixed with real rates. With the virtual environment active, run:

```bash
python -m fxlab --db data/demo.db demo
python -m fxlab --db data/demo.db run --quick
python -m fxlab --db data/demo.db app
```

The dashboard displays a **SIMULATED** banner. On Windows, the same commands work in PowerShell or Command Prompt.

The dashboard's **Get latest rates** button fetches the latest available daily rates from Frankfurter. Rates are not streamed in real time.

No GPU, no heavy dependencies (no XGBoost/LightGBM, so no OpenMP install problems on macOS).
The full `python -m fxlab run` uses all cores; expect minutes, not hours. Use `--quick` for a faster pass.

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

## Project status

* ✅ Unit tests pass, including SQL cross rates, feature look-ahead, walk-forward leakage, statistical tests, and the end-to-end pipeline.
* ✅ Live Frankfurter ingestion, SQL quality checks, and a six-pair real-data evaluation have been run locally.
* ✅ The Streamlit dashboard has been run locally. Use **Get latest rates** to refresh the available daily rates; the model evaluation is a separate CLI step (`python -m fxlab run`).
* ⚠️ Streamlit Community Cloud does not guarantee persistence for files created at runtime. The SQLite database may need to be refreshed after an app restart.

## Attribution & disclaimer
Data: European Central Bank euro reference rates via [Frankfurter](https://frankfurter.dev). The ECB states these
rates are for information only and not for transactions. This project is for education and portfolio
purposes and is not financial advice.
