from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path
import pandas as pd
from . import config, db, ingest as ingest_mod, quality, synthetic
from .pipeline import run_experiment


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="fxlab", description="INR exchange-rate analytics & forecast evaluation")
    ap.add_argument("--db", help="SQLite path (default: data/fx.db or $FXLAB_DB)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create database schema")
    p = sub.add_parser("ingest", help="download ECB rates via Frankfurter (internet required)")
    p.add_argument("--start", default="2010-01-01"); p.add_argument("--end"); p.add_argument("--full", action="store_true")
    sub.add_parser("demo", help="load SIMULATED data (offline demo; use with a separate --db)")
    p = sub.add_parser("run", help="walk-forward model evaluation")
    p.add_argument("--pairs", nargs="*"); p.add_argument("--horizons", nargs="*", type=int, default=list(config.HORIZONS))
    p.add_argument("--models", nargs="*"); p.add_argument("--initial-train", type=int, default=1000)
    p.add_argument("--refit-every", type=int, default=63); p.add_argument("--quick", action="store_true")
    p.add_argument("--run-id"); p.add_argument("--seed", type=int, default=42)
    sub.add_parser("quality", help="run SQL data-quality checks")
    sub.add_parser("app", help="launch the Streamlit dashboard")
    a = ap.parse_args(argv)

    if a.db:
        config.DB_PATH = Path(a.db)
    if a.cmd == "app":
        env_db = str(config.DB_PATH)
        import os
        os.environ["FXLAB_DB"] = env_db
        app = config.ROOT / "app" / "streamlit_app.py"
        sys.exit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(app)]))

    conn = db.connect(config.DB_PATH)
    db.init_db(conn)
    if a.cmd == "init":
        print(f"database ready at {config.DB_PATH}")
    elif a.cmd == "ingest":
        n = ingest_mod.ingest(conn, a.start, a.end, a.full)
        print(f"stored {n} rows")
    elif a.cmd == "demo":
        print(f"stored {synthetic.load_simulated(conn)} SIMULATED rows in {config.DB_PATH}")
    elif a.cmd == "run":
        kw = {"models": tuple(a.models)} if a.models else {}
        m = run_experiment(conn, pairs=a.pairs, horizons=a.horizons, initial_train=a.initial_train,
                           refit_every=a.refit_every, quick=a.quick, run_id=a.run_id, seed=a.seed, **kw)
        cols = ["pair", "horizon", "model", "n_obs", "rmse", "rel_rmse", "oos_r2", "dir_acc", "dm_p", "dm_p_holm"]
        with pd.option_context("display.width", 200, "display.max_rows", 500, "display.float_format", "{:.4f}".format):
            print(m[cols].to_string(index=False))
    elif a.cmd == "quality":
        bad = 0
        for r in quality.run_checks(conn):
            flag = "OK  " if r["ok"] else r["severity"].upper()
            print(f"[{flag}] {r['name']}: {r['description']}")
            if not r["ok"] or r["severity"] == "info":
                print(r["rows"].head(10).to_string(index=False))
            bad += (not r["ok"]) and r["severity"] == "fail"
        sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
