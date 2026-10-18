# Architecture

```
Frankfurter API ──> ingest.py ──> SQLite (eur_rates) ──views──> v_pair_rates
                                         │                           │
                       quality_checks.sql┘                features.py (X, y)
                                                                      │
                                              evaluate.walk_forward ──┤ models.py
                                                                      ▼
                          metrics + predictions tables  <──  pipeline.run_experiment
                                         │
                                 Streamlit app (read-only connection)
```
* **One writer, many readers:** CLI writes; the dashboard opens the DB read-only (`mode=ro`).
* **Config:** `FXLAB_DB` selects the database file; `src/fxlab/config.py` holds pairs, horizons, API base.
* **Extending:** add a model in `models.py` (factory returning an sklearn-style estimator); add a pair in `config.PAIRS`
  and a currency in `CURRENCY_NAMES` — SQL views and the UI pick it up automatically.
* **Deployment:** local first. For hosting, run `streamlit run app/streamlit_app.py` on any VM/Streamlit Community Cloud
  with a pre-built `data/fx.db`; schedule `python -m fxlab ingest` (incremental) and `run` via cron/launchd/GitHub Actions.
* **Production notes:** no secrets are needed (public API). The API is a free public service: keep the polite delay in
  `ingest.py` and cache data locally.
