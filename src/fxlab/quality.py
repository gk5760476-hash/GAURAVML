from __future__ import annotations
import pandas as pd
from . import config
from .db import load_queries


def run_checks(conn) -> list[dict]:
    results = []
    for q in load_queries(config.SQL_DIR / "quality_checks.sql"):
        df = pd.read_sql_query(q["sql"], conn)
        ok = True if q["severity"] == "info" else df.empty
        results.append({**q, "ok": ok, "rows": df})
    return results
