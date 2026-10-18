from __future__ import annotations
import numpy as np
import pandas as pd
from scipy import stats


def walk_forward(X: pd.DataFrame, y: pd.Series, factory, horizon: int,
                 initial_train: int = 1000, refit_every: int = 63) -> pd.Series:
    """Expanding-window walk-forward predictions.

    For a test block starting at position s, the model is trained only on rows j <= s - horizon,
    i.e. rows whose h-day target was already fully realised by the first test date (no leakage
    from overlapping targets).
    """
    n = len(X)
    if n <= initial_train:
        raise ValueError(f"Need more than {initial_train} observations, have {n}.")
    preds = pd.Series(index=X.index[initial_train:], dtype=float)
    for s in range(initial_train, n, refit_every):
        e = min(s + refit_every, n)
        train_end = s - horizon + 1
        model = factory()
        model.fit(X.iloc[:train_end], y.iloc[:train_end])
        preds.iloc[s - initial_train:e - initial_train] = model.predict(X.iloc[s:e])
    return preds


def _newey_west_var(d: np.ndarray, lag: int) -> float:
    n = len(d)
    d = d - d.mean()
    v = float(d @ d) / n
    for k in range(1, lag + 1):
        v += 2 * (1 - k / (lag + 1)) * float(d[k:] @ d[:-k]) / n
    return v


def diebold_mariano(e_bench: np.ndarray, e_model: np.ndarray, h: int) -> tuple[float, float]:
    """One-sided DM test, H1: model has lower squared error than the benchmark.
    Newey-West variance with h-1 lags + Harvey-Leybourne-Newbold correction. Returns (stat, p)."""
    d = e_bench ** 2 - e_model ** 2
    n = len(d)
    if n < h + 10 or np.allclose(d, 0):
        return np.nan, np.nan
    v = _newey_west_var(d, max(h - 1, 0))
    if v <= 0:
        return np.nan, np.nan
    stat = d.mean() / np.sqrt(v / n)
    stat *= np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    return float(stat), float(1 - stats.t.cdf(stat, n - 1))


def holm(p: pd.Series) -> pd.Series:
    """Holm-Bonferroni adjustment (controls family-wise error across many model/pair tests)."""
    out = pd.Series(np.nan, index=p.index)
    valid = p.dropna().sort_values()
    m = len(valid)
    running = 0.0
    for i, (idx, val) in enumerate(valid.items()):
        running = max(running, min(1.0, (m - i) * val))
        out[idx] = running
    return out


def score(y_true: np.ndarray, y_pred: np.ndarray, y_bench: np.ndarray, h: int, is_benchmark: bool) -> dict:
    e, eb = y_true - y_pred, y_true - y_bench
    sse, sse_b = float(e @ e), float(eb @ eb)
    res = {"n_obs": len(e), "mae": float(np.abs(e).mean()), "rmse": float(np.sqrt(sse / len(e))),
           "rel_rmse": float(np.sqrt(sse / sse_b)), "oos_r2": 1 - sse / sse_b,
           "dir_acc": np.nan, "dir_p": np.nan, "dm_stat": np.nan, "dm_p": np.nan}
    mask = (y_pred != 0) & (y_true != 0)
    if not is_benchmark and mask.sum() > 30:
        hits = int((np.sign(y_pred[mask]) == np.sign(y_true[mask])).sum())
        res["dir_acc"] = hits / int(mask.sum())
        res["dir_p"] = float(stats.binomtest(hits, int(mask.sum()), 0.5, alternative="greater").pvalue)
    if not is_benchmark:
        res["dm_stat"], res["dm_p"] = diebold_mariano(eb, e, h)
    return res
