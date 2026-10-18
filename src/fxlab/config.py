from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(os.environ.get("FXLAB_HOME", Path(__file__).resolve().parents[2]))
DB_PATH = Path(os.environ.get("FXLAB_DB", ROOT / "data" / "fx.db"))
SQL_DIR = ROOT / "sql"

API_BASE = "https://api.frankfurter.dev/v1"
SOURCE_REAL = "frankfurter"      # ECB euro foreign-exchange reference rates
SOURCE_SIM = "synthetic"

CURRENCY_NAMES = {
    "EUR": "Euro", "USD": "US dollar", "GBP": "Pound sterling", "JPY": "Japanese yen",
    "AUD": "Australian dollar", "SGD": "Singapore dollar", "INR": "Indian rupee",
}
# Convention: "USD/INR" = how many INR one USD buys.
PAIRS = [(b, "INR") for b in ("USD", "EUR", "GBP", "JPY", "AUD", "SGD")]
HORIZONS = (1, 5, 20)           # forecast horizons in trading days
