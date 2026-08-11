import sqlite3

import numpy as np
import pandas as pd

from backend.analytics_engine import (
    compute_hedge_ratio_kalman,
    compute_hedge_ratio_ols,
    compute_spread,
    compute_zscore,
    run_full_analytics,
    _normalize_timestamp_series,
    _latest_contiguous_segment,
    resample_ticks_to_series,
)


def test_ols_recovers_known_relationship():
    x = pd.Series(np.arange(1, 101, dtype=float))
    y = 2.5 * x + 7.0
    beta, alpha = compute_hedge_ratio_ols(x, y)
    assert abs(beta - 2.5) < 1e-10
    assert abs(alpha - 7.0) < 1e-10


def test_spread_uses_hedge_ratio_and_intercept():
    x = pd.Series([10.0, 20.0, 30.0])
    y = 2.0 * x + 5.0
    spread = compute_spread(y, x, 2.0, 5.0)
    assert np.allclose(spread, 0.0)


def test_zscore_does_not_divide_by_zero_for_constant_spread():
    spread = pd.Series([1.0] * 20)
    z = compute_zscore(spread, window=5)
    assert z.isna().all()


def test_timestamp_normalizer_handles_epoch_milliseconds():
    ts = pd.Series([1_750_000_000_000, 1_750_000_001_000])
    normalized = _normalize_timestamp_series(ts)
    assert normalized.dt.year.iloc[0] >= 2025
    assert normalized.dt.tz is not None


def test_kalman_regression_runs_with_numpy_2_5_and_recovers_relationship():
    x = pd.Series(np.linspace(100.0, 200.0, 100))
    y = 2.0 * x + 5.0
    result = compute_hedge_ratio_kalman(x, y, delta=1e-5, vt=1e-3)
    assert len(result) == len(x)
    assert np.isfinite(result[["beta", "alpha"]].to_numpy()).all()
    assert abs(float(result["beta"].iloc[-1]) - 2.0) < 0.1


def test_kalman_regression_is_stable_for_crypto_price_scales():
    x = pd.Series(np.linspace(60_000.0, 64_000.0, 120))
    y = 0.03 * x + 100.0 + np.sin(np.arange(len(x)) / 8.0)
    result = compute_hedge_ratio_kalman(x, y, delta=1e-5, vt=1e-3)
    beta = float(result["beta"].iloc[-1])
    alpha = float(result["alpha"].iloc[-1])
    assert np.isfinite(beta)
    assert np.isfinite(alpha)
    assert abs(beta - 0.03) < 0.01


def test_canonical_pipeline_uses_same_sampling_and_metrics(tmp_path):
    db_path = tmp_path / "quant_data.db"
    timestamps = pd.date_range("2026-01-01", periods=120, freq="min", tz="UTC")
    x = np.linspace(500.0, 620.0, len(timestamps))
    y = 3.0 * x + 12.0 + np.sin(np.arange(len(timestamps)) / 5.0)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE tick_data (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, timestamp DATETIME, price REAL, volume REAL)"
        )
        rows = []
        for ts, xv, yv in zip(timestamps, x, y):
            rows.append(("AAAUSDT", ts.isoformat(), float(xv), 1.0))
            rows.append(("BBBUSDT", ts.isoformat(), float(yv), 1.0))
        conn.executemany(
            "INSERT INTO tick_data(symbol, timestamp, price, volume) VALUES (?, ?, ?, ?)",
            rows,
        )

    result = run_full_analytics(
        symbol_x="AAAUSDT",
        symbol_y="BBBUSDT",
        timeframe="1min",
        lookback_minutes=120,
        zscore_window=30,
        db_path=db_path,
    )
    latest = result["results"]
    assert latest["num_bars"] >= 100
    assert abs(latest["hedge_ratio_ols"] - 3.0) < 0.05
    assert np.isfinite(latest["kalman_beta_latest"])
    assert np.isfinite(latest["zscore_latest"])
    assert "adf_pvalue" in latest

def test_resampling_fills_only_short_gaps():
    timestamps = pd.to_datetime(
        [
            "2026-01-01 00:00:10+00:00",
            "2026-01-01 00:01:10+00:00",
            "2026-01-01 00:04:10+00:00",
            "2026-01-01 00:05:10+00:00",
        ],
        utc=True,
    )

    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["BTCUSDT"] * 4,
            "price": [100.0, 101.0, 104.0, 105.0],
        }
    )

    bars = resample_ticks_to_series(
        df,
        timeframe="1min",
        max_gap_bars=2,
    )

    assert len(bars) == 6
    assert bars.index.to_series().diff().dropna().eq(
        pd.Timedelta(minutes=1)
    ).all()

    # 00:02 and 00:03 are a two-bar short gap.
    assert bars.loc["2026-01-01 00:02:00+00:00", "BTCUSDT"] == 101.0
    assert bars.loc["2026-01-01 00:03:00+00:00", "BTCUSDT"] == 101.0


def test_long_gap_remains_missing():
    timestamps = pd.to_datetime(
        [
            "2026-01-01 00:00:10+00:00",
            "2026-01-01 00:01:10+00:00",
            "2026-01-01 00:06:10+00:00",
        ],
        utc=True,
    )

    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["BTCUSDT"] * 3,
            "price": [100.0, 101.0, 106.0],
        }
    )

    bars = resample_ticks_to_series(
        df,
        timeframe="1min",
        max_gap_bars=2,
    )

    assert pd.isna(
        bars.loc["2026-01-01 00:04:00+00:00", "BTCUSDT"]
    )
    assert pd.isna(
        bars.loc["2026-01-01 00:05:00+00:00", "BTCUSDT"]
    )


def test_latest_contiguous_segment_does_not_bridge_long_gap():
    index = pd.to_datetime(
        [
            "2026-01-01 00:00:00+00:00",
            "2026-01-01 00:01:00+00:00",
            "2026-01-01 00:02:00+00:00",
            "2026-01-01 00:10:00+00:00",
            "2026-01-01 00:11:00+00:00",
        ],
        utc=True,
    )

    pair = pd.DataFrame(
        {
            "BTCUSDT": [100, 101, 102, 110, 111],
            "ETHUSDT": [10, 11, 12, 20, 21],
        },
        index=index,
    )

    result = _latest_contiguous_segment(
        pair,
        timeframe="1min",
    )

    assert list(result.index) == [
        pd.Timestamp("2026-01-01 00:10:00+00:00"),
        pd.Timestamp("2026-01-01 00:11:00+00:00"),
    ]

def test_pipeline_uses_effective_timeframe_after_10s_fallback(tmp_path):
    db_path = tmp_path / "quant_data.db"

    timestamps = pd.date_range(
        "2026-01-01 00:00:00",
        periods=20,
        freq="10s",
        tz="UTC",
    )

    x = np.linspace(500.0, 520.0, len(timestamps))
    y = 2.0 * x + 10.0

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE tick_data ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "symbol TEXT, "
            "timestamp DATETIME, "
            "price REAL, "
            "volume REAL"
            ")"
        )

        rows = []
        for ts, xv, yv in zip(timestamps, x, y):
            rows.append(("AAAUSDT", ts.isoformat(), float(xv), 1.0))
            rows.append(("BBBUSDT", ts.isoformat(), float(yv), 1.0))

        conn.executemany(
            "INSERT INTO tick_data(symbol, timestamp, price, volume) "
            "VALUES (?, ?, ?, ?)",
            rows,
        )

    result = run_full_analytics(
        symbol_x="AAAUSDT",
        symbol_y="BBBUSDT",
        timeframe="1min",
        lookback_minutes=5,
        zscore_window=5,
        db_path=db_path,
    )

    df = result["df"]

    assert not df.empty
    assert len(df) >= 10

    intervals = df.index.to_series().diff().dropna()

    assert intervals.eq(pd.Timedelta(seconds=10)).all()