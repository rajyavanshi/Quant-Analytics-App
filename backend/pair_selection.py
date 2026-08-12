"""Statistical screening utilities for crypto pairs research.

The functions in this module are deliberately independent from the live
analytics API. They are used by the historical pair scanner to answer:

* Are two assets sufficiently related?
* Is their log-price residual stationary?
* Does the residual mean-revert on a useful horizon?
* Is the hedge ratio reasonably stable?

This module is for research/discovery. Pair selection must still be followed
by walk-forward out-of-sample backtesting with execution costs.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller


def split_contiguous_segments(
    pair: pd.DataFrame,
    timeframe: str = "1min",
    max_gap_bars: int = 0,
) -> list[pd.DataFrame]:
    """Return contiguous non-overlapping segments of a synchronized pair."""
    if pair is None or pair.empty:
        return []

    work = pair.dropna().sort_index()
    if work.empty:
        return []

    expected = pd.Timedelta(timeframe)
    gaps = work.index.to_series().diff()
    breaks = gaps > expected * (max_gap_bars + 1)
    segment_id = breaks.cumsum()

    return [segment.copy() for _, segment in work.groupby(segment_id)]


def longest_contiguous_segment(
    pair: pd.DataFrame,
    timeframe: str = "1min",
) -> pd.DataFrame:
    segments = split_contiguous_segments(pair, timeframe=timeframe)
    if not segments:
        return pd.DataFrame(columns=pair.columns if pair is not None else None)
    return max(segments, key=len)


def log_price_regression(
    x: pd.Series,
    y: pd.Series,
) -> tuple[float, float]:
    """Fit log(y) = alpha + beta*log(x)."""
    data = pd.concat([x, y], axis=1).apply(pd.to_numeric, errors="coerce").dropna()
    data = data[(data.iloc[:, 0] > 0) & (data.iloc[:, 1] > 0)]
    if len(data) < 20:
        raise ValueError("At least 20 positive observations are required")

    lx = np.log(data.iloc[:, 0].to_numpy(float))
    ly = np.log(data.iloc[:, 1].to_numpy(float))
    design = np.column_stack([np.ones(len(lx)), lx])
    alpha, beta = np.linalg.lstsq(design, ly, rcond=None)[0]
    return float(beta), float(alpha)


def log_spread(
    x: pd.Series,
    y: pd.Series,
    beta: float,
    alpha: float,
) -> pd.Series:
    return np.log(y) - alpha - beta * np.log(x)


def adf_pvalue(spread: pd.Series) -> tuple[float, float]:
    clean = pd.to_numeric(spread, errors="coerce").dropna()
    if len(clean) < 30 or clean.nunique() < 3:
        return np.nan, np.nan
    try:
        stat, pvalue, *_rest, critical = adfuller(
            clean,
            maxlag=min(10, max(1, len(clean) // 10)),
            autolag="AIC",
        )
        return float(stat), float(pvalue)
    except Exception:
        return np.nan, np.nan


def half_life(spread: pd.Series) -> float:
    """Estimate AR(1) mean-reversion half-life in bars."""
    clean = pd.to_numeric(spread, errors="coerce").dropna()
    if len(clean) < 30:
        return np.nan

    lag = clean.shift(1)
    delta = clean.diff()
    data = pd.concat([delta, lag], axis=1).dropna()
    if len(data) < 20:
        return np.nan

    x = data.iloc[:, 1].to_numpy(float)
    y = data.iloc[:, 0].to_numpy(float)
    design = np.column_stack([np.ones(len(x)), x])
    _, phi = np.linalg.lstsq(design, y, rcond=None)[0]

    # Delta S_t = a + phi*S_(t-1); mean reversion requires phi < 0.
    if not np.isfinite(phi) or phi >= 0:
        return np.inf

    return float(-np.log(2.0) / phi)


def rolling_ols_betas(
    x: pd.Series,
    y: pd.Series,
    window: int = 120,
) -> pd.Series:
    """Rolling log-price hedge ratios for stability diagnostics."""
    values = pd.concat([x, y], axis=1).dropna()
    values = values[(values.iloc[:, 0] > 0) & (values.iloc[:, 1] > 0)]
    if len(values) < window:
        return pd.Series(dtype=float)

    lx = np.log(values.iloc[:, 0])
    ly = np.log(values.iloc[:, 1])
    betas = []
    indices = []

    for end in range(window, len(values) + 1):
        xx = lx.iloc[end - window:end].to_numpy(float)
        yy = ly.iloc[end - window:end].to_numpy(float)
        design = np.column_stack([np.ones(window), xx])
        beta = np.linalg.lstsq(design, yy, rcond=None)[0][1]
        betas.append(float(beta))
        indices.append(values.index[end - 1])

    return pd.Series(betas, index=indices, name="beta")


def screen_pair(
    pair: pd.DataFrame,
    symbol_x: str,
    symbol_y: str,
    timeframe: str = "1min",
    min_bars: int = 500,
    min_correlation: float = 0.70,
    max_adf_pvalue: float = 0.05,
    min_half_life: float = 1.0,
    max_half_life: float = 120.0,
    beta_window: int = 120,
) -> dict:
    """Compute the statistical screening metrics for one pair."""
    segment = longest_contiguous_segment(
        pair[[symbol_x, symbol_y]],
        timeframe=timeframe,
    )

    result = {
        "symbol_x": symbol_x,
        "symbol_y": symbol_y,
        "bars": int(len(segment)),
        "start": segment.index.min() if not segment.empty else pd.NaT,
        "end": segment.index.max() if not segment.empty else pd.NaT,
        "correlation": np.nan,
        "beta": np.nan,
        "adf_stat": np.nan,
        "adf_pvalue": np.nan,
        "half_life_bars": np.nan,
        "half_life_minutes": np.nan,
        "beta_mean": np.nan,
        "beta_std": np.nan,
        "beta_cv": np.nan,
        "eligible": False,
        "score": np.nan,
        "reason": "insufficient_contiguous_history",
    }

    if len(segment) < min_bars:
        return result

    x = segment[symbol_x]
    y = segment[symbol_y]

    correlation = float(x.pct_change().corr(y.pct_change()))
    beta, alpha = log_price_regression(x, y)
    spread = log_spread(x, y, beta, alpha)
    adf_stat, pvalue = adf_pvalue(spread)
    hl = half_life(spread)
    rolling_beta = rolling_ols_betas(x, y, window=beta_window)

    beta_mean = float(rolling_beta.mean()) if not rolling_beta.empty else np.nan
    beta_std = float(rolling_beta.std()) if not rolling_beta.empty else np.nan
    beta_cv = abs(beta_std / beta_mean) if np.isfinite(beta_mean) and beta_mean != 0 else np.inf

    eligible = bool(
        np.isfinite(correlation)
        and correlation >= min_correlation
        and np.isfinite(pvalue)
        and pvalue <= max_adf_pvalue
        and np.isfinite(hl)
        and min_half_life <= hl <= max_half_life
        and np.isfinite(beta_cv)
        and beta_cv <= 0.50
    )

    # Score is a ranking aid, not a trading objective.
    # Higher correlation, stronger ADF rejection, shorter useful half-life,
    # and more stable beta receive higher scores.
    if np.isfinite(pvalue):
        stationarity_score = max(0.0, min(1.0, -np.log10(max(pvalue, 1e-12)) / 6.0))
    else:
        stationarity_score = 0.0
    corr_score = max(0.0, min(1.0, (correlation - min_correlation) / (1.0 - min_correlation)))
    half_life_score = (
        max(0.0, min(1.0, (max_half_life - hl) / max_half_life))
        if np.isfinite(hl)
        else 0.0
    )
    stability_score = max(0.0, min(1.0, 1.0 - beta_cv)) if np.isfinite(beta_cv) else 0.0
    score = 0.30 * corr_score + 0.35 * stationarity_score + 0.20 * half_life_score + 0.15 * stability_score

    result.update(
        {
            "correlation": correlation,
            "beta": beta,
            "adf_stat": adf_stat,
            "adf_pvalue": pvalue,
            "half_life_bars": hl,
            "half_life_minutes": hl * pd.Timedelta(timeframe).total_seconds() / 60.0,
            "beta_mean": beta_mean,
            "beta_std": beta_std,
            "beta_cv": beta_cv,
            "eligible": eligible,
            "score": score,
            "reason": "eligible" if eligible else "failed_statistical_filters",
        }
    )
    return result


def generate_pair_list(symbols: list[str]) -> list[tuple[str, str]]:
    clean = sorted({str(s).upper() for s in symbols})
    return list(combinations(clean, 2))
