"""Simulated EUR-based rates for offline demos and tests. NOT real market data.

Each currency follows a random walk with volatility clustering (GARCH-like) plus a common
factor. There is no built-in predictability, so a sound evaluation should NOT find that
ML models reliably beat the random walk here.
"""
from __future__ import annotations
import datetime as dt
import numpy as np
import pandas as pd
from . import config

START_LEVELS = {"USD": 1.20, "GBP": 0.85, "JPY": 130.0, "AUD": 1.60, "SGD": 1.60, "INR": 60.0}


def simulate(start="2008-01-01", end="2024-12-31", seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, end)
    n = len(idx)
    common = rng.standard_normal(n)
    out = {}
    for k, (ccy, lvl) in enumerate(START_LEVELS.items()):
        vol = np.empty(n)
        v = 0.005
        eps = rng.standard_normal(n)
        for t in range(n):
            vol[t] = v
            shock = 0.6 * common[t] + 0.8 * eps[t]
            v = np.sqrt(1e-7 + 0.06 * (v * shock) ** 2 + 0.92 * v ** 2)
        drift = 0.00012 if ccy == "INR" else 0.0
        ret = drift + vol * (0.6 * common + 0.8 * eps)
        out[ccy] = lvl * np.exp(np.cumsum(ret))
    df = pd.DataFrame(out, index=idx)
    df["EUR"] = 1.0
    return df


def load_simulated(conn, **kw) -> int:
    existing = [r[0] for r in conn.execute("SELECT DISTINCT source FROM eur_rates")]
    if config.SOURCE_REAL in existing:
        raise RuntimeError("This database holds real data. Use a different --db for simulated data.")
    df = simulate(**kw)
    cur = conn.execute("INSERT INTO ingestion_runs(source, started_at, start_date, end_date, status) VALUES (?,?,?,?, 'ok')",
                       (config.SOURCE_SIM, dt.datetime.now(dt.timezone.utc).isoformat(),
                        str(df.index[0].date()), str(df.index[-1].date())))
    run_id = cur.lastrowid
    rows = [(d.strftime("%Y-%m-%d"), c, float(v), config.SOURCE_SIM, run_id)
            for d, r in df.iterrows() for c, v in r.items()]
    conn.executemany("INSERT OR REPLACE INTO eur_rates(rate_date, currency, rate, source, ingestion_run_id) VALUES (?,?,?,?,?)", rows)
    conn.execute("UPDATE ingestion_runs SET rows_written=? WHERE run_id=?", (len(rows), run_id))
    conn.commit()
    return len(rows)
