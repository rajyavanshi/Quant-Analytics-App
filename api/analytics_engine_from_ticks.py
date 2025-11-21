# =====================================================
# File: api/db_pair_prices.py
# Purpose: Fetch and prepare recent pair price data for analytics
# Author: Suraj Prakash (Quant Developer)
# =====================================================

import sqlite3
import pandas as pd
import numpy as np
import os
import logging

# -------------------------------------------------------
# Database connection helper
# -------------------------------------------------------
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "quant_data.db")

def get_conn():
    """Return a new SQLite connection."""
    return sqlite3.connect(DB_PATH, check_same_thread=False)


# -------------------------------------------------------
# Fetch recent pair prices and align timestamps
# -------------------------------------------------------
def get_recent_pair_prices(symbol_pair: str, limit: int = 500):
    """
    Fetch recent tick prices for a symbol pair and return an aligned DataFrame.
    Structure:
        timestamp | x_price | y_price
    """
    try:
        conn = get_conn()
        a, b = symbol_pair.upper().split("_")

        # Fetch data for both legs
        q = """
            SELECT symbol, timestamp, price
            FROM tick_data
            WHERE UPPER(symbol) = ?
            ORDER BY timestamp DESC
            LIMIT ?;
        """
        df_a = pd.read_sql_query(q, conn, params=(a, limit))
        df_b = pd.read_sql_query(q, conn, params=(b, limit))
        conn.close()

        if df_a.empty or df_b.empty:
            logging.warning(f"[DB] One or both legs missing: {a}={len(df_a)}, {b}={len(df_b)}")
            return pd.DataFrame()

        # Convert timestamps to pandas datetime
        df_a["timestamp"] = pd.to_datetime(df_a["timestamp"])
        df_b["timestamp"] = pd.to_datetime(df_b["timestamp"])

        # Sort ascending
        df_a = df_a.sort_values("timestamp")
        df_b = df_b.sort_values("timestamp")

        # Merge using nearest timestamps within 2 seconds tolerance
        merged = pd.merge_asof(
            df_a.rename(columns={"price": "x_price"}),
            df_b.rename(columns={"price": "y_price"}),
            on="timestamp",
            direction="nearest",
            tolerance=pd.Timedelta("2s")
        )

        merged = merged.dropna(subset=["x_price", "y_price"]).reset_index(drop=True)

        logging.info(f"[DB] ✅ Aligned {len(merged)} rows for pair {symbol_pair}.")
        return merged

    except Exception as e:
        logging.exception(f"[DB] Error fetching pair prices for {symbol_pair}: {e}")
        return pd.DataFrame()


def compute_analytics_for_pair(symbol_pair, window=100, limit=1000):
    """
    Fetch recent pair_prices for symbol_pair and compute analytics.
    """
    df = get_recent_pair_prices(symbol_pair, limit=limit)
    if df.empty:
        return df

    # OLS hedge ratio
    sample = df.tail(window)
    beta, intercept = estimate_hedge_ratio_ols(sample['x_price'], sample['y_price'])
    if beta is None:
        beta, intercept = 1.0, 0.0

    df = df.copy()
    df['hedge_ratio'] = beta
    df['intercept'] = intercept
    df['spread'] = df['y_price'] - (beta * df['x_price'] + intercept)
    df['mean_spread'] = df['spread'].rolling(window=window, min_periods=1).mean()
    df['std_spread'] = df['spread'].rolling(window=window, min_periods=1).std()
    df['zscore'] = (df['spread'] - df['mean_spread']) / df['std_spread']
    df['rolling_corr'] = df['x_price'].rolling(window=window, min_periods=1).corr(df['y_price'])

    # Return final dataframe
    return df.reset_index(drop=True)
