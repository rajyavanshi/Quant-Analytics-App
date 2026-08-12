"""Frontend data normalization helpers.

Financial metrics are treated as backend-owned values. These helpers clean and
format API responses and only derive a spread when the API provides the hedge
ratio/intercept needed to reproduce the backend definition exactly.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd


def to_dataframe(data):
    if data is None:
        return pd.DataFrame()
    if isinstance(data, dict):
        data = data.get("data", data)
        if isinstance(data, dict):
            data = [data]
    try:
        df = pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return df
    df.columns = [str(c).lower().strip() for c in df.columns]
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    return df


def clean_numeric(df, cols=None):
    if df.empty:
        return df
    if cols is None:
        cols = [c for c in df.columns if any(k in c for k in ("price", "value", "zscore", "beta", "alpha", "spread", "corr", "pvalue"))]
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def add_rolling_stats(df, col, window=20):
    if df.empty or col not in df.columns:
        return df
    df[f"{col}_mean_{window}"] = df[col].rolling(window, min_periods=max(3, window // 4)).mean()
    df[f"{col}_std_{window}"] = df[col].rolling(window, min_periods=max(3, window // 4)).std()
    return df


def compute_spread_zscore(df, x_col="x_price", y_col="y_price", window=60):
    """Use backend spread/z-score when present; otherwise reproduce the hedge formula."""
    if df.empty:
        return df
    if "spread" not in df.columns and {x_col, y_col}.issubset(df.columns):
        if {"hedge_ratio", "intercept"}.issubset(df.columns):
            df["spread"] = df[y_col] - (df["hedge_ratio"] * df[x_col] + df["intercept"])
        elif {"beta_ols", "alpha_ols"}.issubset(df.columns):
            df["spread"] = df[y_col] - (df["beta_ols"] * df[x_col] + df["alpha_ols"])
    if "spread" in df.columns and "zscore" not in df.columns:
        mean = df["spread"].rolling(window, min_periods=max(3, window // 4)).mean()
        std = df["spread"].rolling(window, min_periods=max(3, window // 4)).std()
        df["zscore"] = (df["spread"] - mean) / std.replace(0, np.nan)
    return df


def reshape_analytics_data(df):
    if df.empty or not {"metric_name", "metric_value"}.issubset(df.columns):
        return df
    try:
        result = df.pivot_table(index="timestamp", columns="metric_name", values="metric_value", aggfunc="first").reset_index()
        result.columns = [str(c).strip().lower() for c in result.columns]
        return result.sort_values("timestamp")
    except Exception:
        return df


def compute_correlation_matrix(df, cols=None):
    if df.empty:
        return pd.DataFrame()
    if cols is None:
        cols = df.select_dtypes(include=[np.number]).columns.tolist()
    return df[cols].corr().round(3)


def get_summary_metrics(df, col="spread"):
    if df.empty or col not in df.columns:
        return {"mean": None, "std": None, "min": None, "max": None, "last_update": datetime.now().strftime("%H:%M:%S")}
    return {
        "mean": round(float(df[col].mean()), 4),
        "std": round(float(df[col].std()), 4),
        "min": round(float(df[col].min()), 4),
        "max": round(float(df[col].max()), 4),
        "last_update": datetime.now().strftime("%H:%M:%S"),
    }


def process_analytics_data(data, window=60):
    df = to_dataframe(data)
    if df.empty:
        return df
    if "metric_name" in df.columns and "metric_value" in df.columns:
        df = reshape_analytics_data(df)
    df = clean_numeric(df)
    df = compute_spread_zscore(df, window=window)
    for col in ("spread", "zscore"):
        if col in df.columns:
            df = add_rolling_stats(df, col, window)
    return df
