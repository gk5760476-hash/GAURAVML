import sqlite3
import unittest
import numpy as np
import pandas as pd

from fxlab import config, db, synthetic
from fxlab.evaluate import diebold_mariano, holm, walk_forward
from fxlab.features import build_dataset, build_features
from fxlab.pipeline import run_experiment


def make_conn(start="2015-01-01", end="2021-12-31"):
    conn = sqlite3.connect(":memory:")
    db.init_db(conn)
    synthetic.load_simulated(conn, start=start, end=end)
    return conn


class TestDatabase(unittest.TestCase):
    def test_cross_rate_view(self):
        conn = sqlite3.connect(":memory:")
        db.init_db(conn)
        conn.executemany("INSERT INTO eur_rates VALUES (?,?,?,?,NULL)", [
            ("2024-01-02", "EUR", 1.0, "t"), ("2024-01-02", "USD", 1.10, "t"), ("2024-01-02", "INR", 90.0, "t")])
        rate = dict(conn.execute("SELECT pair, rate FROM v_pair_rates").fetchall())
        self.assertAlmostEqual(rate["USD/INR"], 90.0 / 1.10)   # INR per USD
        self.assertAlmostEqual(rate["EUR/INR"], 90.0)

    def test_rejects_non_positive_rates(self):
        conn = sqlite3.connect(":memory:")
        db.init_db(conn)
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO eur_rates VALUES ('2024-01-02','USD',-1,'t',NULL)")

    def test_synthetic_and_real_are_not_mixed(self):
        conn = make_conn("2020-01-01", "2020-03-01")
        from fxlab import ingest
        with self.assertRaises(RuntimeError):
            ingest.ingest(conn, "2020-01-01", "2020-01-10")


class TestFeatures(unittest.TestCase):
    def setUp(self):
        self.prices = db.load_prices(make_conn())

    def test_no_lookahead_in_features(self):
        cut = self.prices.index[1500]
        altered = self.prices.copy()
        altered.loc[altered.index > cut] *= 3.0          # wreck the future
        a = build_features(self.prices, "USD/INR").loc[:cut]
        b = build_features(altered, "USD/INR").loc[:cut]
        pd.testing.assert_frame_equal(a, b)

    def test_target_is_future_return(self):
        X, y = build_dataset(self.prices, "USD/INR", 5)
        t = X.index[10]
        pos = self.prices.index.get_loc(t)
        expected = 100 * np.log(self.prices["USD/INR"].iloc[pos + 5] / self.prices["USD/INR"].iloc[pos])
        self.assertAlmostEqual(y.loc[t], expected)


class Spy:
    log = []
    def fit(self, X, y):
        Spy.log.append(["fit", X.index[-1]])
        return self
    def predict(self, X):
        Spy.log.append(["predict", X.index[0]])
        return np.zeros(len(X))


class TestWalkForward(unittest.TestCase):
    def test_training_targets_realised_before_test_block(self):
        prices = db.load_prices(make_conn())
        for h in (1, 5, 20):
            X, y = build_dataset(prices, "USD/INR", h)
            Spy.log = []
            walk_forward(X, y, Spy, h, initial_train=800, refit_every=50)
            pos = {d: i for i, d in enumerate(X.index)}
            fits = [d for kind, d in Spy.log if kind == "fit"]
            tests = [d for kind, d in Spy.log if kind == "predict"]
            self.assertEqual(len(fits), len(tests))
            for last_train, first_test in zip(fits, tests):
                # last training row's target date is `h` rows ahead and must not be after first test date
                self.assertLessEqual(pos[last_train] + h, pos[first_test])


class TestStats(unittest.TestCase):
    def test_dm_detects_better_model(self):
        rng = np.random.default_rng(0)
        y = rng.standard_normal(2000)
        stat, p = diebold_mariano(y - 0.0, y - 0.7 * y, 1)    # model explains 70% of y
        self.assertGreater(stat, 5); self.assertLess(p, 0.001)

    def test_dm_not_significant_for_noise(self):
        rng = np.random.default_rng(1)
        y = rng.standard_normal(2000)
        _, p = diebold_mariano(y, y - 0.01 * rng.standard_normal(2000), 1)
        self.assertTrue(np.isnan(p) or p > 0.01)

    def test_holm_monotone_and_bounded(self):
        adj = holm(pd.Series([0.01, 0.04, 0.03, np.nan]))
        self.assertTrue((adj.dropna() >= pd.Series([0.01, 0.04, 0.03])).all())
        self.assertTrue((adj.dropna() <= 1).all())
        self.assertTrue(np.isnan(adj.iloc[3]))


class TestPipeline(unittest.TestCase):
    def test_end_to_end_small(self):
        conn = make_conn("2012-01-01", "2019-12-31")
        m = run_experiment(conn, pairs=["USD/INR"], horizons=[1, 5], initial_train=800, refit_every=200,
                           quick=True, run_id="t", progress=lambda *_: None)
        self.assertEqual(set(m["model"]), set(config_models()))
        rw = m[m.model == "random_walk"].iloc[0]
        self.assertAlmostEqual(rw["rel_rmse"], 1.0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0], len(m))
        self.assertGreater(conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0], 0)
        # on data with no built-in predictability nothing should be significant after Holm correction
        self.assertTrue((m["dm_p_holm"].dropna() > 0.01).all())


def config_models():
    from fxlab.models import MODEL_NAMES
    return MODEL_NAMES


if __name__ == "__main__":
    unittest.main()


class FakeResp:
    status_code = 200
    def __init__(self, payload): self.payload = payload
    def raise_for_status(self): pass
    def json(self): return self.payload


class FakeSession:
    """Mimics Frankfurter's time-series response shape: {"rates": {"YYYY-MM-DD": {"USD": 1.1, ...}}}"""
    def get(self, url, params=None, timeout=None):
        return FakeResp({"base": "EUR", "rates": {
            "2024-01-02": {"USD": 1.10, "INR": 91.0}, "2024-01-03": {"USD": 1.09, "INR": 90.5}}})


class TestIngestParsing(unittest.TestCase):
    def test_fetch_range_parses_and_adds_eur_anchor(self):
        import datetime as dt
        from fxlab import ingest
        rows = ingest.fetch_range(dt.date(2024, 1, 1), dt.date(2024, 1, 5), FakeSession(), progress=lambda *_: None)
        self.assertIn(("2024-01-02", "EUR", 1.0), rows)
        self.assertIn(("2024-01-03", "INR", 90.5), rows)

    def test_analytics_queries_run(self):
        conn = make_conn("2020-01-01", "2020-12-31")
        from pathlib import Path
        for q in db.load_queries(config.SQL_DIR / "analytics.sql"):
            if q["name"] != "best_models":
                self.assertFalse(pd.read_sql_query(q["sql"], conn).empty, q["name"])
