"""FX Lab dashboard (Streamlit). Launch with:  python -m fxlab app"""
from __future__ import annotations
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from fxlab import config, db, quality
from fxlab.models import BENCHMARK, DESCRIPTIONS

st.set_page_config(page_title="FX Lab · INR", page_icon="💱", layout="wide")
DB_FILE = os.environ.get("FXLAB_DB", str(config.DB_PATH))
PLOT = dict(template="plotly_white", margin=dict(l=10, r=10, t=40, b=10))
DISCLAIMER = ("Educational research project. Rates are ECB euro reference rates (indicative, not for "
              "transactions). Nothing here is financial advice or a trading signal.")


def refresh_rates(path: str) -> subprocess.CompletedProcess:
    """Run the normal incremental Frankfurter ingestion for the dashboard database."""
    app_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["FXLAB_DB"] = str(Path(path).expanduser().resolve())
    src = str(app_root / "src")
    env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return subprocess.run(
        [sys.executable, "-m", "fxlab", "ingest"],
        cwd=app_root, env=env, capture_output=True, text=True, timeout=300,
    )


@st.cache_resource
def conn_for(path: str) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)


@st.cache_data(ttl=300, show_spinner=False)
def get_prices(path: str) -> pd.DataFrame:
    return db.load_prices(conn_for(path))


@st.cache_data(ttl=300, show_spinner=False)
def get_runs(path: str) -> pd.DataFrame:
    return db.list_runs(conn_for(path))


@st.cache_data(ttl=300, show_spinner=False)
def get_metrics(path: str, run_id: str) -> pd.DataFrame:
    return db.load_metrics(conn_for(path), run_id)


@st.cache_data(ttl=300, show_spinner=False)
def get_preds(path: str, run_id: str, pair: str, horizon: int) -> pd.DataFrame:
    return db.load_predictions(conn_for(path), run_id, pair, horizon)


@st.cache_data(ttl=300, show_spinner=False)
def get_sources(path: str) -> list[str]:
    return db.data_sources(conn_for(path))


def empty_state(msg: str) -> None:
    st.info(msg)
    st.code("python -m fxlab ingest --start 2010-01-01   # real ECB data (internet)\n"
            "python -m fxlab run                          # evaluate models\n"
            "# offline demo with SIMULATED data:  make demo", language="bash")
    st.stop()


st.sidebar.title("💱 FX Lab")
st.sidebar.caption("Frankfurter publishes daily reference rates, not a live streaming quote.")
if st.sidebar.button("Get latest rates", help="Fetch the latest available rates and refresh this dashboard."):
    try:
        with st.spinner("Fetching the latest available rates from Frankfurter…"):
            result = refresh_rates(DB_FILE)
        if result.returncode == 0:
            st.cache_data.clear()
            stored = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "Ingestion completed."
            st.session_state["refresh_notice"] = stored
            st.rerun()
        st.sidebar.error("Rate refresh failed. " + (result.stderr.strip() or result.stdout.strip() or "See the terminal for details."))
    except (OSError, subprocess.TimeoutExpired) as exc:
        st.sidebar.error(f"Rate refresh failed: {exc}")
if st.session_state.get("refresh_notice"):
    st.sidebar.success(st.session_state.pop("refresh_notice"))


# ---------------------------------------------------------------- shell
if not Path(DB_FILE).exists():
    st.title("💱 FX Lab")
    empty_state(f"No database found at `{DB_FILE}`. Use **Get latest rates** in the sidebar to fetch live data.")

prices = get_prices(DB_FILE)
if prices.empty:
    st.title("💱 FX Lab")
    empty_state("The database has no exchange-rate data yet. Use **Get latest rates** in the sidebar to fetch it.")

sources = get_sources(DB_FILE)
simulated = config.SOURCE_SIM in sources

page = st.sidebar.radio("Navigate", ["Overview", "Rate explorer", "Model comparison",
                                     "Forecast diagnostics", "Data & methodology"])
st.sidebar.caption(f"Data: {', '.join(sources)}  \nLast date: {prices.index[-1].date()}")
st.sidebar.caption(DISCLAIMER)
if simulated:
    st.warning("⚠️ This database contains **SIMULATED** data for demonstration. It is not real market data.")


def pick_run(key: str):
    runs = get_runs(DB_FILE)
    if runs.empty:
        st.info("No model runs yet. Run `python -m fxlab run` (add `--quick` for a faster pass).")
        st.stop()
    return st.selectbox("Experiment run", runs["run_id"].tolist(), key=f"run_{key}")


# ---------------------------------------------------------------- Overview
if page == "Overview":
    st.title("INR exchange-rate overview")
    st.caption("Convention: USD/INR = rupees per 1 US dollar. Source: ECB reference rates via Frankfurter.")
    last, prev = prices.iloc[-1], prices.iloc[-2]
    month = prices.iloc[max(len(prices) - 22, 0)]
    cols = st.columns(len(prices.columns))
    for c, pair in zip(cols, prices.columns):
        c.metric(pair, f"{last[pair]:.3f}", f"{100 * (last[pair] / prev[pair] - 1):+.2f}% (1d)")
    window = st.select_slider("Window", ["1M", "3M", "6M", "1Y", "5Y", "Max"], value="1Y")
    days = {"1M": 22, "3M": 66, "6M": 132, "1Y": 252, "5Y": 1260, "Max": len(prices)}[window]
    sub = prices.iloc[-days:]
    rebased = 100 * sub / sub.iloc[0]
    fig = px.line(rebased, labels={"value": "Index (start = 100)", "rate_date": "", "variable": "Pair"},
                  title="Performance vs INR (rebased to 100; up = INR weaker)")
    fig.update_layout(**PLOT)
    st.plotly_chart(fig)
    summary = pd.DataFrame({
        "Latest": last, "1d %": 100 * (last / prev - 1), "1m %": 100 * (last / month - 1),
        "YTD %": 100 * (last / prices[prices.index.year == prices.index[-1].year].iloc[0] - 1)}).round(3)
    st.dataframe(summary)

# ---------------------------------------------------------------- Explorer
elif page == "Rate explorer":
    st.title("Rate explorer")
    c1, c2 = st.columns([1, 2])
    pair = c1.selectbox("Pair", prices.columns)
    lo, hi = prices.index[0].date(), prices.index[-1].date()
    rng = c2.date_input("Date range", (max(lo, (prices.index[-1] - pd.Timedelta(days=3 * 365)).date()), hi),
                        min_value=lo, max_value=hi)
    if len(rng) != 2:
        st.info("Pick both a start and an end date.")
        st.stop()
    s = prices[pair].loc[str(rng[0]):str(rng[1])]
    if len(s) < 30:
        st.warning("Not enough observations in this range.")
        st.stop()
    mas = st.multiselect("Moving averages (days)", [20, 60, 200], default=[20, 60])
    fig = go.Figure(go.Scatter(x=s.index, y=s, name=pair, line=dict(width=1.5)))
    for w in mas:
        fig.add_trace(go.Scatter(x=s.index, y=s.rolling(w).mean(), name=f"MA{w}", line=dict(width=1, dash="dot")))
    fig.update_layout(title=f"{pair} (INR per 1 {pair[:3]})", **PLOT)
    st.plotly_chart(fig)

    ret = 100 * np.log(s).diff().dropna()
    a, b = st.columns(2)
    h = px.histogram(ret, nbins=60, title="Distribution of daily log returns (%)")
    h.update_layout(showlegend=False, **PLOT)
    a.plotly_chart(h)
    w = b.select_slider("Rolling volatility window (days)", [10, 20, 60, 120], value=20)
    vol = ret.rolling(w).std() * np.sqrt(252)
    v = px.line(vol, title=f"Annualised {w}-day volatility (%)")
    v.update_layout(showlegend=False, **PLOT)
    b.plotly_chart(v)
    st.dataframe(pd.DataFrame({
        "Mean daily %": [ret.mean()], "Std daily %": [ret.std()], "Skew": [ret.skew()],
        "Excess kurtosis": [ret.kurt()], "Worst day %": [ret.min()], "Best day %": [ret.max()],
        "Observations": [len(ret)]}).round(4))

# ---------------------------------------------------------------- Model comparison
elif page == "Model comparison":
    st.title("Do ML models beat the random walk?")
    st.caption("rel_rmse < 1 means lower error than the no-change benchmark. Significance uses a one-sided "
               "Diebold–Mariano test, Holm-adjusted across every model, pair and horizon in the run.")
    run_id = pick_run("cmp")
    m = get_metrics(DB_FILE, run_id)
    horizons = sorted(m["horizon"].unique())
    h = st.radio("Forecast horizon (trading days)", horizons, horizontal=True)
    mh = m[(m.horizon == h) & (m.model != BENCHMARK)]
    winners = m[(m.model != BENCHMARK) & (m.rel_rmse < 1) & (m.dm_p_holm < 0.05)]
    total = len(m[m.model != BENCHMARK])
    if len(winners):
        st.success(f"{len(winners)} of {total} model×pair×horizon results significantly beat the random walk "
                   f"after multiple-testing correction.")
    else:
        st.info(f"0 of {total} model×pair×horizon results significantly beat the random walk after "
                f"multiple-testing correction. This is the typical finding in the FX forecasting literature.")
    piv = mh.pivot(index="pair", columns="model", values="rel_rmse")
    fig = px.imshow(piv, text_auto=".3f", color_continuous_scale="RdYlGn_r", color_continuous_midpoint=1.0,
                    aspect="auto", title=f"RMSE relative to random walk (h = {h}); green < 1 is better")
    fig.update_layout(**PLOT)
    st.plotly_chart(fig)
    cols = ["pair", "model", "n_obs", "rmse", "mae", "rel_rmse", "oos_r2", "dir_acc", "dm_p", "dm_p_holm"]
    st.dataframe(mh[cols].sort_values(["pair", "rel_rmse"]).round(4), hide_index=True)
    with st.expander("What the models are"):
        for k, v in DESCRIPTIONS.items():
            st.markdown(f"**{k}** — {v}")
    with st.expander("How to read the metrics"):
        st.markdown(
            "- **rel_rmse**: RMSE ÷ random-walk RMSE. Below 1 = better.\n"
            "- **oos_r2**: share of the benchmark's squared error removed. Negative = worse than random walk.\n"
            "- **dir_acc**: share of correct up/down calls (50% = coin flip). Not defined for the benchmark.\n"
            "- **dm_p / dm_p_holm**: probability of seeing this improvement by luck, raw and corrected for "
            "running many tests. Small corrected values are the only credible evidence.")

# ---------------------------------------------------------------- Diagnostics
elif page == "Forecast diagnostics":
    st.title("Forecast diagnostics")
    run_id = pick_run("diag")
    m = get_metrics(DB_FILE, run_id)
    c1, c2, c3 = st.columns(3)
    pair = c1.selectbox("Pair", sorted(m["pair"].unique()))
    h = c2.selectbox("Horizon (days)", sorted(m["horizon"].unique()))
    model = c3.selectbox("Model", [x for x in m["model"].unique() if x != BENCHMARK])
    p = get_preds(DB_FILE, run_id, pair, int(h))
    wide = p.pivot(index="pred_date", columns="model", values="y_pred")
    truth = p.drop_duplicates("pred_date").set_index("pred_date")["y_true"]
    adv = ((truth - wide[BENCHMARK]) ** 2 - (truth - wide[model]) ** 2).cumsum()
    fig = go.Figure(go.Scatter(x=adv.index, y=adv, name="cumulative advantage"))
    fig.add_hline(y=0, line_dash="dot")
    fig.update_layout(title="Cumulative squared-error advantage over random walk (above 0 = model ahead)", **PLOT)
    st.plotly_chart(fig)
    n_show = st.slider("Days shown in actual-vs-predicted chart", 60, min(1000, len(truth)), min(250, len(truth)))
    t = truth.iloc[-n_show:]
    f2 = go.Figure()
    f2.add_trace(go.Scatter(x=t.index, y=t, name="actual", line=dict(width=1)))
    f2.add_trace(go.Scatter(x=t.index, y=wide[model].loc[t.index], name=model, line=dict(width=1)))
    f2.update_layout(title=f"Realised vs predicted {h}-day log return (%)", **PLOT)
    st.plotly_chart(f2)
    hit = (np.sign(wide[model]) == np.sign(truth)).astype(float).rolling(250).mean().dropna()
    if len(hit):
        f3 = px.line(hit, title="Rolling 250-day directional accuracy (0.5 = coin flip)")
        f3.add_hline(y=0.5, line_dash="dot")
        f3.update_layout(showlegend=False, **PLOT)
        st.plotly_chart(f3)

# ---------------------------------------------------------------- Methodology
else:
    st.title("Data quality & methodology")
    st.subheader("Data-quality checks (SQL)")
    for r in quality.run_checks(conn_for(DB_FILE)):
        icon = "ℹ️" if r["severity"] == "info" else ("✅" if r["ok"] else ("❌" if r["severity"] == "fail" else "⚠️"))
        with st.expander(f"{icon} {r['name']} — {r['description']}"):
            st.dataframe(r["rows"]) if len(r["rows"]) else st.write("No issues.")
    st.subheader("Method")
    st.markdown(
        "- **Source:** ECB euro foreign-exchange reference rates (published on working days around 16:00 CET), "
        "served by the free Frankfurter API. Stored EUR-based; cross rates computed in SQL.\n"
        "- **Target:** h-day-ahead log return in percent. Benchmark: random walk (predicts 0).\n"
        "- **Validation:** expanding-window walk-forward; each model is trained only on rows whose target was "
        "fully realised before the test block starts, and refit periodically.\n"
        "- **Inference:** Diebold–Mariano (Newey–West, small-sample corrected) with Holm correction.\n"
        "- **Limits:** ECB fixings are not tradable prices; no transaction costs; overlapping h-day targets; "
        "results depend on sample period. Past performance does not predict future results.")
    runs = get_runs(DB_FILE)
    if not runs.empty:
        st.subheader("Experiment runs")
        runs = runs.assign(config=runs["config_json"].map(lambda s: json.dumps(json.loads(s))))
        st.dataframe(runs.drop(columns=["config_json"]), hide_index=True)
    st.caption(DISCLAIMER)
