#!/usr/bin/env bash
# One-shot setup for macOS (Apple Silicon M1/M2/M3). Needs Python 3.10+ (brew install python@3.12).
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
python -m fxlab init
echo "Done. Activate with: source .venv/bin/activate"
echo "Next: make data && make run && make app     (or: make demo for offline simulated data)"
