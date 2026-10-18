from __future__ import annotations
import datetime as dt
import json
import numpy as np
import pandas as pd
from . import config
from .db import data_sources, load_prices
from .evaluate import holm, score, walk_forward
from .features import build_dataset
from .models import BENCHMARK, MODEL_NAMES, make_models


def run_experiment(conn, pairs=None, horizons=config.HORIZONS, models=MODEL_NAMES,
                   initial_train: int = 1000, refit_every: int = 63, quick: bool = False,
                   run_id: str | None = None, seed: int = 42, progress=print) -> pd.DataFrame:
    prices = load_prices(conn).dropna()
    if prices.empty:
        raise RuntimeError("No price data. Run `python -m fxlab ingest` (or `demo`) first.")
    if BENCHMARK not in models:
        models = (BENCHMARK, *models)
    pairs = list(pairs or prices.columns)
    run_id = run_id or dt.datetime.now().strftime("run_%Y%m%d_%H%M%S")
    factories = make_models(seed=seed, quick=quick, names=tuple(models))
    sources = data_sources(conn)

    all_metrics, all_preds = [], []
    for pair in pairs:
        for h in horizons:
            X, y = build_dataset(prices, pair, h)
            if len(X) <= initial_train + 50:
                progress(f"! skipping {pair} h={h}: only {len(X)} usable rows (need > {initial_train + 50})")
                continue
            progress(f"{pair} h={h}: {len(X)} rows, test from {X.index[initial_train].date()}")
            preds = {name: walk_forward(X, y, fac, h, initial_train, refit_every) for name, fac in factories.items()}
            y_true = y.loc[preds[BENCHMARK].index].to_numpy()
            y_bench = preds[BENCHMARK].to_numpy()
            for name, p in preds.items():
                m = score(y_true, p.to_numpy(), y_bench, h, name == BENCHMARK)
                all_metrics.append({"run_id": run_id, "pair": pair, "horizon": h, "model": name, **m})
                all_preds.append(pd.DataFrame({
                    "run_id": run_id, "pair": pair, "horizon": h, "model": name,
                    "pred_date": p.index.strftime("%Y-%m-%d"), "y_true": y_true, "y_pred": p.to_numpy()}))
    if not all_metrics:
        raise RuntimeError("No pair had enough data. Ingest more history or lower --initial-train.")

    metrics = pd.DataFrame(all_metrics)
    metrics["dm_p_holm"] = holm(metrics["dm_p"])
    cfg = {"pairs": pairs, "horizons": list(horizons), "models": list(models), "initial_train": initial_train,
           "refit_every": refit_every, "quick": quick, "seed": seed}
    conn.execute("DELETE FROM experiments WHERE run_id = ?", (run_id,))
    conn.execute("INSERT INTO experiments(run_id, created_at, data_source, config_json) VALUES (?,?,?,?)",
                 (run_id, dt.datetime.now(dt.timezone.utc).isoformat(), ",".join(sources), json.dumps(cfg)))
    metrics.replace({np.nan: None}).to_sql("metrics", conn, if_exists="append", index=False)
    pd.concat(all_preds).to_sql("predictions", conn, if_exists="append", index=False)
    conn.commit()
    progress(f"saved run '{run_id}'")
    return metrics
