"""Pair analytics built on the canonical backend OLS implementation."""

from __future__ import annotations

import pandas as pd

from backend.analytics_engine import compute_hedge_ratio_ols, run_adf_test
from api.db_pair_prices import get_recent_pair_prices, parse_pair


def compute_analytics_for_pair(symbol_pair: str, window: int = 100, limit: int = 1000) -> pd.DataFrame:
    """Return a consistent pair analytics DataFrame for API consumers."""
    parse_pair(symbol_pair)
    window = max(3, min(int(window), 1000))
    df = get_recent_pair_prices(symbol_pair, limit=limit)
    if df.empty:
        return df

    sample = df.tail(window)
    beta, intercept = compute_hedge_ratio_ols(sample["x_price"], sample["y_price"])

    out = df.copy()
    out["hedge_ratio"] = float(beta)
    out["intercept"] = float(intercept)
    out["spread"] = out["y_price"] - (out["hedge_ratio"] * out["x_price"] + out["intercept"])
    out["mean_spread"] = out["spread"].rolling(window, min_periods=max(3, window // 4)).mean()
    out["std_spread"] = out["spread"].rolling(window, min_periods=max(3, window // 4)).std()
    out["zscore"] = (out["spread"] - out["mean_spread"]) / out["std_spread"]
    out["rolling_corr"] = out["x_price"].rolling(window, min_periods=max(3, window // 4)).corr(out["y_price"])

    adf = run_adf_test(out["spread"])
    out["adf_stat"] = adf.get("adf_stat")
    out["adf_pvalue"] = adf.get("pvalue")
    return out.reset_index(drop=True)
