"""Feature engineering. Every feature at row t uses information available at the close of day t only.

Returns are 100 * log differences (percent). Target = realised h-day-ahead log return (percent):
    y_t = 100 * (log P_{t+h} - log P_t)
"""
from __future__ import annotations
import numpy as np
import pandas as pd

LAGS = (1, 2, 3, 5, 10, 20)        # ret_l1 = latest known daily return (t-1 -> t)


def build_features(prices: pd.DataFrame, pair: str) -> pd.DataFrame:
    prices = prices.dropna()
    lp = np.log(prices)
    R = 100 * lp.diff()
    r = R[pair]
    f: dict[str, pd.Series] = {}
    for k in LAGS:
        f[f"ret_l{k}"] = r.shift(k - 1)
    for w in (5, 20):
        f[f"ret_mean{w}"] = r.rolling(w).mean()
    for w in (5, 20, 60):
        f[f"vol{w}"] = r.rolling(w).std()
    for w in (5, 20, 60):
        f[f"mom{w}"] = r.rolling(w).sum()
    for w in (20, 60):
        f[f"dev_ma{w}"] = 100 * (lp[pair] - lp[pair].rolling(w).mean())
    f["vol_ratio_5_60"] = f["vol5"] / f["vol60"]
    others = R.drop(columns=[pair])
    if not others.empty:
        basket = others.mean(axis=1)
        f["basket_l1"] = basket
        f["basket_mean5"] = basket.rolling(5).mean()
    dow = prices.index.dayofweek
    f["dow_sin"] = pd.Series(np.sin(2 * np.pi * dow / 5), index=prices.index)
    f["dow_cos"] = pd.Series(np.cos(2 * np.pi * dow / 5), index=prices.index)
    return pd.DataFrame(f).dropna()


def build_target(prices: pd.DataFrame, pair: str, horizon: int) -> pd.Series:
    lp = np.log(prices[pair].dropna())
    return (100 * (lp.shift(-horizon) - lp)).rename(f"y_h{horizon}")


def build_dataset(prices: pd.DataFrame, pair: str, horizon: int) -> tuple[pd.DataFrame, pd.Series]:
    """Aligned (X, y) with rows that have both complete features and a realised target."""
    prices = prices.dropna()
    X = build_features(prices, pair)
    y = build_target(prices, pair, horizon).reindex(X.index)
    keep = y.notna()
    return X[keep], y[keep]
