"""API adapter for the canonical quantitative analytics engine."""

from __future__ import annotations

import pandas as pd

from backend.analytics_engine import run_full_analytics
from api.db_pair_prices import parse_pair


def compute_analytics_for_pair(
    symbol_pair: str,
    window: int = 100,
    limit: int = 1000,
    timeframe: str = "1min",
) -> pd.DataFrame:
    """Return API-compatible pair analytics from the canonical backend pipeline.

    ``window`` controls rolling statistics. ``limit`` is retained for API
    compatibility; the canonical engine uses a time-based lookback so every
    consumer uses the same sampling policy.
    """
    del limit
    symbol_x, symbol_y = parse_pair(symbol_pair)
    window = max(3, min(int(window), 1000))
    lookback_minutes = max(10, window * 2)
    result = run_full_analytics(
        symbol_x=symbol_x,
        symbol_y=symbol_y,
        timeframe=timeframe,
        lookback_minutes=lookback_minutes,
        zscore_window=window,
    )
    return result["df"].reset_index()
