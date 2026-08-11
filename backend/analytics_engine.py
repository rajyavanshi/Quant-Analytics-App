"""Quantitative analytics engine for synchronized market ticks.

The module is intentionally independent of the Flask and Streamlit layers. It
produces one canonical DataFrame containing prices, hedge ratios, spread,
z-score, ADF statistics and rolling correlation.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller

from database.database_setup import DB_PATH, init_db

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TABLE_NAME = "tick_data"
ANALYTICS_TABLE = "analytics_results"
DEFAULT_BASE = "BTCUSDT"
DEFAULT_QUOTE = "ETHUSDT"


def _normalize_timestamp_series(series: pd.Series) -> pd.Series:
    """Normalize ISO strings or Unix seconds/ms/us/ns without ambiguous thresholds."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(series, utc=True, errors="coerce")

    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().any():
        magnitude = float(numeric.dropna().abs().median())
        if magnitude >= 1e17:
            unit = "ns"
        elif magnitude >= 1e14:
            unit = "us"
        elif magnitude >= 1e11:
            unit = "ms"
        elif magnitude >= 1e9:
            unit = "s"
        else:
            unit = None
        if unit:
            return pd.to_datetime(numeric, unit=unit, utc=True, errors="coerce")

    return pd.to_datetime(series, utc=True, errors="coerce")


def check_db_structure(db_path=DB_PATH) -> dict[str, list[str]]:
    init_db(db_path)
    with sqlite3.connect(str(db_path)) as conn:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return {
            table: [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]
            for table in tables
        }


def fetch_recent_ticks(symbols: list[str], minutes: int = 60, db_path=DB_PATH) -> pd.DataFrame:
    """Fetch a bounded recent tick window using the DB's newest timestamp."""
    if minutes <= 0:
        raise ValueError("minutes must be positive")
    symbols = [str(s).upper() for s in symbols]
    if len(symbols) < 2:
        raise ValueError("At least two symbols are required")

    init_db(db_path)
    placeholders = ",".join("?" for _ in symbols)
    with sqlite3.connect(str(db_path)) as conn:
        query = f"""
            SELECT timestamp, symbol, price, volume
            FROM {TABLE_NAME}
            WHERE UPPER(symbol) IN ({placeholders})
            ORDER BY timestamp DESC
            LIMIT 200000
        """
        df = pd.read_sql_query(query, conn, params=symbols)

    if df.empty:
        return df

    df["timestamp"] = _normalize_timestamp_series(df["timestamp"])
    df["symbol"] = df["symbol"].astype(str).str.upper()
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df.dropna(subset=["timestamp", "symbol", "price"])
    if df.empty:
        return df

    newest = df["timestamp"].max()
    cutoff = newest - pd.Timedelta(minutes=minutes)
    return df[df["timestamp"] >= cutoff].sort_values("timestamp").reset_index(drop=True)


def resample_ticks_to_series(df: pd.DataFrame, timeframe: str = "1min") -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    required = {"timestamp", "symbol", "price"}
    if not required.issubset(df.columns):
        raise ValueError(f"Missing columns: {sorted(required - set(df.columns))}")

    work = df.copy()
    work["timestamp"] = _normalize_timestamp_series(work["timestamp"])
    work["price"] = pd.to_numeric(work["price"], errors="coerce")
    work = work.dropna(subset=["timestamp", "symbol", "price"])
    if work.empty:
        return pd.DataFrame()

    series = {}
    for symbol, group in work.groupby(work["symbol"].astype(str).str.upper()):
        g = group.set_index("timestamp").sort_index()
        series[symbol] = g["price"].resample(timeframe).last()
    return pd.concat(series, axis=1).sort_index().dropna(how="all") if series else pd.DataFrame()


def check_data_sufficiency(bars: pd.DataFrame, min_bars: int = 10, symbol_x=DEFAULT_BASE, symbol_y=DEFAULT_QUOTE) -> bool:
    if bars is None or bars.empty:
        return False
    if symbol_x not in bars.columns or symbol_y not in bars.columns:
        return False
    aligned = bars[[symbol_x, symbol_y]].dropna()
    return len(aligned) >= min_bars


def compute_hedge_ratio_ols(x: pd.Series, y: pd.Series) -> tuple[float, float]:
    pair = pd.concat([pd.to_numeric(x, errors="coerce"), pd.to_numeric(y, errors="coerce")], axis=1).dropna()
    if len(pair) < 10:
        return 1.0, 0.0
    model = sm.OLS(pair.iloc[:, 1], sm.add_constant(pair.iloc[:, 0])).fit()
    return float(model.params.iloc[1]), float(model.params.iloc[0])


def compute_hedge_ratio_kalman(x: pd.Series, y: pd.Series, delta=1e-5, vt=1e-3) -> pd.DataFrame:
    pair = pd.concat([pd.to_numeric(x, errors="coerce"), pd.to_numeric(y, errors="coerce")], axis=1).dropna()
    if len(pair) < 5:
        raise ValueError("At least five aligned observations are required for Kalman regression")

    theta = np.zeros(2, dtype=float)
    covariance = np.eye(2, dtype=float)
    process_noise = np.eye(2, dtype=float) * float(delta)
    betas, alphas = [], []

    for xv, yv in zip(pair.iloc[:, 0].to_numpy(float), pair.iloc[:, 1].to_numpy(float)):
        H = np.array([[xv, 1.0]], dtype=float)
        pred_cov = covariance + process_noise
        innovation = float(yv - (H @ theta).item())
        innovation_cov = float((H @ pred_cov @ H.T).item() + vt)
        if not np.isfinite(innovation_cov) or innovation_cov <= 0:
            raise FloatingPointError("Invalid Kalman innovation covariance")
        gain = pred_cov @ H.T / innovation_cov
        theta = theta + gain[:, 0] * innovation
        covariance = pred_cov - gain @ H @ pred_cov
        covariance = (covariance + covariance.T) / 2.0
        betas.append(float(theta[0]))
        alphas.append(float(theta[1]))

    return pd.DataFrame({"beta": betas, "alpha": alphas}, index=pair.index)


def compute_spread(y, x, beta, alpha):
    return y - (beta * x + alpha)


def compute_zscore(spread: pd.Series, window: int = 60) -> pd.Series:
    window = max(3, int(window))
    minimum = max(3, window // 4)
    mean = spread.rolling(window, min_periods=minimum).mean()
    std = spread.rolling(window, min_periods=minimum).std()
    return (spread - mean) / std.replace(0, np.nan)


def run_adf_test(spread: pd.Series) -> dict[str, Any]:
    clean = pd.to_numeric(spread, errors="coerce").dropna()
    if len(clean) < 20:
        return {"adf_stat": np.nan, "pvalue": np.nan, "critical_values": {}}
    try:
        result = adfuller(clean, maxlag=min(10, max(1, len(clean) // 10)), autolag="AIC")
        return {"adf_stat": float(result[0]), "pvalue": float(result[1]), "critical_values": result[4]}
    except Exception as exc:
        logger.warning("ADF failed: %s", exc)
        return {"adf_stat": np.nan, "pvalue": np.nan, "critical_values": {}}


def compute_rolling_correlation(x, y, window=60):
    minimum = max(3, int(window) // 4)
    return x.rolling(int(window), min_periods=minimum).corr(y)


def run_full_analytics(symbol_x=DEFAULT_BASE, symbol_y=DEFAULT_QUOTE, timeframe="1min", lookback_minutes=120, zscore_window=60):
    symbol_x, symbol_y = symbol_x.upper(), symbol_y.upper()
    ticks = fetch_recent_ticks([symbol_x, symbol_y], minutes=lookback_minutes)
    if ticks.empty:
        raise ValueError(f"No tick data available for {symbol_x}/{symbol_y}")

    bars = resample_ticks_to_series(ticks, timeframe)
    if not check_data_sufficiency(bars, 10, symbol_x, symbol_y):
        bars = resample_ticks_to_series(ticks, "10s")
    if not check_data_sufficiency(bars, 5, symbol_x, symbol_y):
        raise ValueError("Insufficient overlapping data for pair analytics")

    pair = bars[[symbol_x, symbol_y]].dropna().copy()
    pair.columns = ["x_price", "y_price"]
    beta_ols, alpha_ols = compute_hedge_ratio_ols(pair["x_price"], pair["y_price"])

    try:
        kalman = compute_hedge_ratio_kalman(pair["x_price"], pair["y_price"])
        kalman = kalman.reindex(pair.index).ffill().bfill()
    except Exception as exc:
        logger.warning("Kalman fallback to OLS: %s", exc)
        kalman = pd.DataFrame(
            {"beta": beta_ols, "alpha": alpha_ols}, index=pair.index
        )

    spread = compute_spread(pair["y_price"], pair["x_price"], kalman["beta"], kalman["alpha"])
    zscore = compute_zscore(spread, zscore_window)
    corr = compute_rolling_correlation(pair["x_price"], pair["y_price"], zscore_window)
    adf = run_adf_test(spread)

    out = pd.DataFrame(
        {
            "x_price": pair["x_price"],
            "y_price": pair["y_price"],
            "beta_ols": beta_ols,
            "alpha_ols": alpha_ols,
            "beta_kalman": kalman["beta"],
            "alpha_kalman": kalman["alpha"],
            "spread": spread,
            "zscore": zscore,
            "rolling_corr": corr,
            "adf_stat": adf["adf_stat"],
            "adf_pvalue": adf["pvalue"],
        },
        index=pair.index,
    )
    out.index.name = "timestamp"

    valid = out.dropna(subset=["zscore"])
    latest = valid.iloc[-1] if not valid.empty else out.iloc[-1]
    results = {
        "symbol_x": symbol_x,
        "symbol_y": symbol_y,
        "num_bars": int(len(out)),
        "hedge_ratio_ols": float(beta_ols),
        "intercept_ols": float(alpha_ols),
        "kalman_beta_latest": float(latest["beta_kalman"]),
        "kalman_alpha_latest": float(latest["alpha_kalman"]),
        "zscore_latest": float(latest["zscore"]) if pd.notna(latest["zscore"]) else np.nan,
        "adf_pvalue": adf["pvalue"],
        "adf_stat": adf["adf_stat"],
        "rolling_corr_latest": float(latest["rolling_corr"]) if pd.notna(latest["rolling_corr"]) else np.nan,
    }
    return {"results": results, "df": out}


def save_analytics_results_to_db(results: dict[str, Any], db_path=DB_PATH, table_name=ANALYTICS_TABLE) -> None:
    init_db(db_path)
    pair = f"{results['symbol_x']}_{results['symbol_y']}"
    rows = []
    timestamp = pd.Timestamp.now(tz=timezone.utc).isoformat()
    for metric in (
        "num_bars", "hedge_ratio_ols", "intercept_ols", "kalman_beta_latest",
        "kalman_alpha_latest", "zscore_latest", "adf_pvalue", "adf_stat", "rolling_corr_latest"
    ):
        value = results.get(metric)
        if value is None or pd.isna(value):
            continue
        rows.append((pair, metric, float(value), timestamp))

    if not rows:
        return
    with sqlite3.connect(str(db_path), timeout=30) as conn:
        conn.executemany(
            f"INSERT INTO {table_name}(symbol, metric_name, metric_value, timestamp) VALUES (?, ?, ?, ?)",
            rows,
        )
        conn.commit()
