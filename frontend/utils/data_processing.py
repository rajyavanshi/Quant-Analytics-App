# =====================================================
# File: frontend/utils/data_processing.py
# Purpose: Convert, clean, and preprocess API data for visualization
# Author: Suraj Prakash (Quant Developer)
# =====================================================

import pandas as pd
import numpy as np
from datetime import datetime

# -----------------------------------------------------
# 1️. Safe DataFrame Converter
# -----------------------------------------------------
def to_dataframe(data):
    """Safely convert API JSON/list/dict response into a clean Pandas DataFrame."""
    if data is None:
        return pd.DataFrame()

    if isinstance(data, dict):
        if "data" in data and isinstance(data["data"], (list, dict)):
            data = data["data"]
        else:
            data = [data]

    try:
        df = pd.DataFrame(data)
    except Exception as e:
        print(f"[ERROR] Could not convert data to DataFrame: {e}")
        return pd.DataFrame()

    if df.empty:
        return df

    df.columns = [c.lower().strip() for c in df.columns]

    for col in df.columns:
        if "time" in col or "timestamp" in col:
            try:
                df[col] = pd.to_datetime(df[col])
            except Exception:
                pass

    if "timestamp" in df.columns:
        df = df.sort_values("timestamp").reset_index(drop=True)

    return df


# -----------------------------------------------------
# 2️. Numeric Cleaner
# -----------------------------------------------------
def clean_numeric(df, cols=None):
    """Convert selected columns to numeric, coercing errors to NaN."""
    if df.empty:
        return df

    if cols is None:
        cols = [c for c in df.columns if any(k in c for k in ["price", "value", "zscore", "beta", "alpha"])]

    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    return df


# -----------------------------------------------------
# 3️. Rolling Statistics Helper
# -----------------------------------------------------
def add_rolling_stats(df, col, window=20):
    """Adds rolling mean/std columns for smoother visualization."""
    if df.empty or col not in df.columns:
        return df

    df[f"{col}_mean_{window}"] = df[col].rolling(window=window, min_periods=1).mean()
    df[f"{col}_std_{window}"] = df[col].rolling(window=window, min_periods=1).std()
    return df


# -----------------------------------------------------
# 4️. Spread & Z-Score Computation
# -----------------------------------------------------
def compute_spread_zscore(df, x_col="x_price", y_col="y_price", window=60):
    """Compute spread = y - x and rolling z-score."""
    if df.empty or x_col not in df.columns or y_col not in df.columns:
        return df

    df["spread"] = df[y_col] - df[x_col]
    df["spread_mean"] = df["spread"].rolling(window=window, min_periods=1).mean()
    df["spread_std"] = df["spread"].rolling(window=window, min_periods=1).std()
    df["zscore"] = (df["spread"] - df["spread_mean"]) / df["spread_std"]
    return df


# -----------------------------------------------------
# 5️. Pivot Key-Value Analytics (NEW)
# -----------------------------------------------------
def reshape_analytics_data(df):
    """
    Converts key-value analytics into a wide DataFrame.
    Example:
    metric_name | metric_value | timestamp → timestamp | zscore_latest | hedge_ratio_ols | ...
    """
    if df.empty or "metric_name" not in df.columns or "metric_value" not in df.columns:
        return df

    try:
        pivoted = (
            df.pivot_table(
                index="timestamp",
                columns="metric_name",
                values="metric_value",
                aggfunc="first",
            )
            .reset_index()
            .sort_values("timestamp")
        )
        pivoted.columns = [str(c).strip().lower() for c in pivoted.columns]
        return pivoted
    except Exception as e:
        print(f"[WARN] Pivoting failed: {e}")
        return df


# -----------------------------------------------------
# 6️. Correlation Matrix
# -----------------------------------------------------
def compute_correlation_matrix(df, cols=None):
    """Computes correlation matrix for numeric columns."""
    if df.empty:
        return pd.DataFrame()

    if cols is None:
        cols = [c for c in df.columns if df[c].dtype in [float, int]]

    try:
        return df[cols].corr().round(3)
    except Exception as e:
        print(f"[ERROR] Correlation computation failed: {e}")
        return pd.DataFrame()


# -----------------------------------------------------
# 7️. Summary Metrics
# -----------------------------------------------------
def get_summary_metrics(df, col="spread"):
    """Returns mean, std, min, max for a numeric column."""
    if df.empty or col not in df.columns:
        return {"mean": None, "std": None, "min": None, "max": None, "last_update": datetime.now().strftime("%H:%M:%S")}
    return {
        "mean": round(df[col].mean(), 4),
        "std": round(df[col].std(), 4),
        "min": round(df[col].min(), 4),
        "max": round(df[col].max(), 4),
        "last_update": datetime.now().strftime("%H:%M:%S"),
    }


# -----------------------------------------------------
# 8️. Combined Processor (Final)
# -----------------------------------------------------
def process_analytics_data(data, window=60):
    """
    Full pipeline:
    - Convert → Pivot (if key-value) → Clean → Add zscore/spread
    """
    df = to_dataframe(data)
    if df.empty:
        return df

    # Reshape if in metric_name/value format
    if "metric_name" in df.columns and "metric_value" in df.columns:
        df = reshape_analytics_data(df)

    df = clean_numeric(df)
    df = compute_spread_zscore(df, window=window)

    # Auto-add rolling stats if zscore or spread present
    for c in ["spread", "zscore"]:
        if c in df.columns:
            df = add_rolling_stats(df, c, window)

    return df
