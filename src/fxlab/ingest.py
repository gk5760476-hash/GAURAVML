"""Download ECB reference rates through the free Frankfurter API (no API key)."""
from __future__ import annotations
import datetime as dt
import time
import requests
from . import config

CHUNK_DAYS = 85          # keep requests short so the API returns daily (not weekly) points
SYMBOLS = [c for c in config.CURRENCY_NAMES if c != "EUR"]


def _get(session: requests.Session, url: str, params: dict, retries: int = 4) -> dict:
    for attempt in range(retries):
        try:
            r = session.get(url, params=params, timeout=30)
            if r.status_code == 404:          # no data in that window (e.g. before a currency starts)
                return {"rates": {}}
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    return {"rates": {}}


def fetch_range(start: dt.date, end: dt.date, session: requests.Session | None = None,
                progress=print) -> list[tuple[str, str, float]]:
    session = session or requests.Session()
    rows: dict[tuple[str, str], float] = {}
    cur = start
    while cur <= end:
        chunk_end = min(cur + dt.timedelta(days=CHUNK_DAYS), end)
        payload = _get(session, f"{config.API_BASE}/{cur}..{chunk_end}",
                       {"base": "EUR", "symbols": ",".join(SYMBOLS)})
        for d, rates in payload.get("rates", {}).items():
            for ccy, val in rates.items():
                rows[(d, ccy)] = float(val)
            rows[(d, "EUR")] = 1.0
        progress(f"  fetched {cur} -> {chunk_end}")
        cur = chunk_end + dt.timedelta(days=1)
        time.sleep(0.15)                       # be polite to a free public service
    return [(d, c, v) for (d, c), v in sorted(rows.items())]


def ingest(conn, start: str = "2010-01-01", end: str | None = None, full: bool = False,
           progress=print) -> int:
    existing = [r[0] for r in conn.execute("SELECT DISTINCT source FROM eur_rates")]
    if config.SOURCE_SIM in existing:
        raise RuntimeError("This database holds simulated data. Use a different --db for real data.")
    start_d = dt.date.fromisoformat(start)
    last = conn.execute("SELECT MAX(rate_date) FROM eur_rates").fetchone()[0]
    if last and not full:
        start_d = max(start_d, dt.date.fromisoformat(last) - dt.timedelta(days=7))  # small overlap, upsert
    end_d = dt.date.fromisoformat(end) if end else dt.date.today()
    cur = conn.execute("INSERT INTO ingestion_runs(source, started_at, start_date, end_date) VALUES (?,?,?,?)",
                       (config.SOURCE_REAL, dt.datetime.now(dt.timezone.utc).isoformat(), str(start_d), str(end_d)))
    run_id = cur.lastrowid
    try:
        rows = fetch_range(start_d, end_d, progress=progress)
        conn.executemany(
            "INSERT OR REPLACE INTO eur_rates(rate_date, currency, rate, source, ingestion_run_id) VALUES (?,?,?,?,?)",
            [(d, c, v, config.SOURCE_REAL, run_id) for d, c, v in rows])
        conn.execute("UPDATE ingestion_runs SET rows_written=?, status='ok' WHERE run_id=?", (len(rows), run_id))
        conn.commit()
        return len(rows)
    except Exception as exc:
        conn.execute("UPDATE ingestion_runs SET status='failed', message=? WHERE run_id=?", (str(exc)[:500], run_id))
        conn.commit()
        raise
