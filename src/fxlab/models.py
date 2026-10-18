from __future__ import annotations
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

BENCHMARK = "random_walk"
MODEL_NAMES = ("random_walk", "hist_mean", "ridge", "random_forest", "grad_boosting")

DESCRIPTIONS = {
    "random_walk": "No-change benchmark: predicts a 0% move (the standard FX benchmark).",
    "hist_mean": "Predicts the average historical move seen so far (drift only).",
    "ridge": "Regularised linear regression on lagged returns, momentum and volatility.",
    "random_forest": "Shallow random forest (non-linear, heavily regularised).",
    "grad_boosting": "Histogram gradient boosting (shallow trees, small learning rate).",
}


def make_models(seed: int = 42, quick: bool = False, names=MODEL_NAMES) -> dict:
    n_trees, n_iter = (60, 60) if quick else (200, 150)
    all_models = {
        "random_walk": lambda: DummyRegressor(strategy="constant", constant=0.0),
        "hist_mean": lambda: DummyRegressor(strategy="mean"),
        "ridge": lambda: make_pipeline(
            StandardScaler(),
            RidgeCV(alphas=[1, 10, 100, 1e3, 1e4, 1e5], cv=TimeSeriesSplit(3))),
        "random_forest": lambda: RandomForestRegressor(
            n_estimators=n_trees, max_depth=4, min_samples_leaf=50, max_features=0.5,
            n_jobs=-1, random_state=seed),
        "grad_boosting": lambda: HistGradientBoostingRegressor(
            max_iter=n_iter, learning_rate=0.03, max_depth=3, min_samples_leaf=50,
            l2_regularization=1.0, random_state=seed),
    }
    unknown = set(names) - set(all_models)
    if unknown:
        raise ValueError(f"Unknown models: {sorted(unknown)}")
    return {n: all_models[n] for n in names}      # name -> factory
