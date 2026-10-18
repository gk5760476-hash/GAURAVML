from __future__ import annotations
import re
import sqlite3
from pathlib import Path
import pandas as pd
from . import config


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript((config.SQL_DIR / "schema.sql").read_text())
    conn.executemany("INSERT OR IGNORE INTO currencies(code, name) VALUES (?, ?)",
                     list(config.CURRENCY_NAMES.items()))
    conn.executemany("INSERT OR IGNORE INTO pairs(pair, base_ccy, quote_ccy) VALUES (?, ?, ?)",
                     [(f"{b}/{q}", b, q) for b, q in config.PAIRS])
    conn.commit()


def load_queries(path: Path) -> list[dict]:
    """Parse '-- name: id | severity | description' blocks from a .sql file."""
    out = []
    for block in re.split(r"(?m)^-- name:", path.read_text())[1:]:
        header, _, sql = block.partition("\n")
        parts = [p.strip() for p in header.split("|")]
        if len(parts) == 3:
            name, severity, desc = parts
        else:
            name, desc = parts[0], parts[-1]
            severity = "info"
        out.append({"name": name, "severity": severity, "description": desc, "sql": sql.strip()})
    return out


def data_sources(conn) -> list[str]:
    return [r[0] for r in conn.execute("SELECT DISTINCT source FROM eur_rates")]


def load_prices(conn) -> pd.DataFrame:
    """Wide DataFrame: index = date, columns = pairs (e.g. 'USD/INR'), values = rate."""
    df = pd.read_sql_query("SELECT pair, rate_date, rate FROM v_pair_rates", conn,
                           parse_dates=["rate_date"])
    if df.empty:
        return pd.DataFrame()
    return df.pivot(index="rate_date", columns="pair", values="rate").sort_index()


def list_runs(conn) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT run_id, created_at, data_source, config_json FROM experiments ORDER BY created_at DESC", conn)


def load_metrics(conn, run_id: str) -> pd.DataFrame:
    return pd.read_sql_query("SELECT * FROM metrics WHERE run_id = ?", conn, params=(run_id,))


def load_predictions(conn, run_id: str, pair: str, horizon: int) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT model, pred_date, y_true, y_pred FROM predictions "
        "WHERE run_id = ? AND pair = ? AND horizon = ? ORDER BY pred_date",
        conn, params=(run_id, pair, int(horizon)), parse_dates=["pred_date"])
