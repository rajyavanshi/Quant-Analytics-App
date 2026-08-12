import numpy as np
import pandas as pd

from backend.pair_selection import (
    half_life,
    log_price_regression,
    log_spread,
    longest_contiguous_segment,
    screen_pair,
)


def test_log_price_regression_recovers_relationship():
    x = pd.Series(np.exp(np.linspace(3.0, 5.0, 300)))
    y = np.exp(0.25 + 1.10 * np.log(x))
    beta, alpha = log_price_regression(x, y)
    assert abs(beta - 1.10) < 1e-8
    assert abs(alpha - 0.25) < 1e-8


def test_longest_contiguous_segment_does_not_bridge_gap():
    index = pd.to_datetime(
        [
            "2026-01-01 00:00:00+00:00",
            "2026-01-01 00:01:00+00:00",
            "2026-01-01 00:10:00+00:00",
            "2026-01-01 00:11:00+00:00",
            "2026-01-01 00:12:00+00:00",
        ],
        utc=True,
    )
    pair = pd.DataFrame({"X": [1, 2, 3, 4, 5], "Y": [2, 4, 6, 8, 10]}, index=index)
    result = longest_contiguous_segment(pair, timeframe="1min")
    assert len(result) == 3
    assert result.index[0] == pd.Timestamp("2026-01-01 00:10:00+00:00")


def test_half_life_detects_mean_reverting_process():
    rng = np.random.default_rng(7)
    values = [0.0]
    phi = -0.20
    for _ in range(499):
        values.append(values[-1] + phi * values[-1] + rng.normal(0, 0.1))
    hl = half_life(pd.Series(values))
    assert np.isfinite(hl)
    assert 2.0 < hl < 6.0


def test_screen_pair_accepts_stationary_log_spread():
    rng = np.random.default_rng(11)
    n = 700
    index = pd.date_range("2026-01-01", periods=n, freq="min", tz="UTC")
    log_x = np.log(100.0) + np.cumsum(rng.normal(0, 0.001, n))
    spread = np.zeros(n)
    for i in range(1, n):
        spread[i] = 0.85 * spread[i - 1] + rng.normal(0, 0.001)
    log_y = 0.15 + 1.05 * log_x + spread
    pair = pd.DataFrame({"X": np.exp(log_x), "Y": np.exp(log_y)}, index=index)

    result = screen_pair(
        pair,
        "X",
        "Y",
        min_bars=500,
        min_correlation=0.50,
        max_adf_pvalue=0.05,
        min_half_life=1,
        max_half_life=120,
        beta_window=120,
    )

    assert result["bars"] == n
    assert np.isfinite(result["adf_pvalue"])
    assert result["adf_pvalue"] < 0.05
    assert np.isfinite(result["half_life_minutes"])
    assert result["eligible"] is True


def test_log_spread_is_zero_for_exact_relationship():
    x = pd.Series([100.0, 110.0, 120.0])
    beta = 1.2
    alpha = 0.3
    y = np.exp(alpha) * x ** beta
    spread = log_spread(x, y, beta, alpha)
    assert np.allclose(spread, 0.0)
