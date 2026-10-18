-- fxlab schema (SQLite). All FX rates are stored once, EUR-based, exactly as published
-- (1 EUR = rate units of `currency`). Cross pairs are derived in SQL via v_pair_rates.

CREATE TABLE IF NOT EXISTS currencies (
    code TEXT PRIMARY KEY CHECK (length(code) = 3),
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    source       TEXT NOT NULL,
    started_at   TEXT NOT NULL,
    start_date   TEXT,
    end_date     TEXT,
    rows_written INTEGER NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running','ok','failed')),
    message      TEXT
);

CREATE TABLE IF NOT EXISTS eur_rates (
    rate_date        TEXT NOT NULL,
    currency         TEXT NOT NULL REFERENCES currencies(code),
    rate             REAL NOT NULL CHECK (rate > 0),
    source           TEXT NOT NULL,
    ingestion_run_id INTEGER REFERENCES ingestion_runs(run_id),
    PRIMARY KEY (rate_date, currency)
);
CREATE INDEX IF NOT EXISTS ix_eur_rates_ccy_date ON eur_rates(currency, rate_date);

CREATE TABLE IF NOT EXISTS pairs (
    pair      TEXT PRIMARY KEY,
    base_ccy  TEXT NOT NULL REFERENCES currencies(code),
    quote_ccy TEXT NOT NULL REFERENCES currencies(code)
);

-- Cross rate: (quote per EUR) / (base per EUR) = quote per base. EUR itself is stored as 1.0.
CREATE VIEW IF NOT EXISTS v_pair_rates AS
SELECT p.pair, q.rate_date, q.rate / b.rate AS rate, q.source
FROM pairs p
JOIN eur_rates b ON b.currency = p.base_ccy
JOIN eur_rates q ON q.currency = p.quote_ccy AND q.rate_date = b.rate_date;

CREATE VIEW IF NOT EXISTS v_pair_daily_change AS
SELECT pair, rate_date, rate,
       rate / LAG(rate) OVER (PARTITION BY pair ORDER BY rate_date) - 1 AS simple_return
FROM v_pair_rates;

CREATE TABLE IF NOT EXISTS experiments (
    run_id      TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    data_source TEXT NOT NULL,
    config_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metrics (
    run_id    TEXT NOT NULL REFERENCES experiments(run_id) ON DELETE CASCADE,
    pair      TEXT NOT NULL,
    horizon   INTEGER NOT NULL,
    model     TEXT NOT NULL,
    n_obs     INTEGER NOT NULL,
    mae       REAL, rmse REAL,
    rel_rmse  REAL,
    oos_r2    REAL,
    dir_acc   REAL, dir_p REAL,
    dm_stat   REAL, dm_p REAL, dm_p_holm REAL,
    PRIMARY KEY (run_id, pair, horizon, model)
);

CREATE TABLE IF NOT EXISTS predictions (
    run_id    TEXT NOT NULL REFERENCES experiments(run_id) ON DELETE CASCADE,
    pair      TEXT NOT NULL,
    horizon   INTEGER NOT NULL,
    model     TEXT NOT NULL,
    pred_date TEXT NOT NULL,
    y_true    REAL NOT NULL,
    y_pred    REAL NOT NULL,
    PRIMARY KEY (run_id, pair, horizon, model, pred_date)
);
CREATE INDEX IF NOT EXISTS ix_pred_lookup ON predictions(run_id, pair, horizon, model);
