"""
backend/analytics_engine.py
Production-ready Stage 3: Analytics Engine

Main responsibilities:
 - Read tick data from SQLite (database/quant_data.db, table tick_data)
 - Resample ticks into bars (1s, 10s, 1m, 5m)
 - Compute static hedge ratio (OLS) and dynamic hedge ratio (Kalman)
 - Compute spread, rolling z-score, ADF stationarity test, rolling correlation
 - Save summary metrics to analytics_results table every cycle
 - Provide df_out (full timeseries) for visualization / downstream systems

Design principles:
 - Defensive: context-managed DB operations, safe logging, clear fallbacks
 - Deterministic outputs: fixed metric names written every cycle
 - Observable: logs and CSV preview for debugging and dashboard integration
"""

import os
import sys
import time
import sqlite3
import logging
import warnings
from typing import List, Tuple, Dict, Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

# -------------------------
# Configuration
# -------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(PROJECT_ROOT, "database", "quant_data.db")
TABLE_NAME = "tick_data"  # expected table with raw ticks
ANALYTICS_TABLE = "analytics_results"
DEFAULT_BASE = "BTCUSDT"
DEFAULT_QUOTE = "ETHUSDT"

LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_PATH = os.path.join(LOG_DIR, "analytics.log")

# Setup logger (file + stdout). File uses UTF-8 encoding; console uses sys.stdout.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("AnalyticsEngine")

# -------------------------
# Metrics we will write every cycle
# - Keep this list stable because downstream consumers / dashboards rely on these names
# -------------------------
METRICS_TO_WRITE = [
    "num_bars",
    "hedge_ratio_ols",      # static OLS beta
    "intercept_ols",       # static OLS alpha
    "kalman_beta_latest",  # latest dynamic beta
    "kalman_alpha_latest", # latest dynamic alpha
    "zscore_latest",
    "adf_pvalue",
    "adf_stat",
    "rolling_corr_latest"
]

# -------------------------
# Helper utilities and formulas (concept notes)
# -------------------------
# OLS formula (simple linear regression):
#    y_t = alpha + beta * x_t + eps_t
# We fit beta, alpha via Ordinary Least Squares (statsmodels OLS).
#
# Kalman filter for time-varying regression:
#    Observation: y_t = [x_t, 1] * theta_t + eps_t  (theta_t = [beta_t, alpha_t])
#    State evolution: theta_t = theta_{t-1} + eta_t (random walk)
# Kalman update (compact):
#    theta_pred = theta_prev
#    P_pred = P_prev + Q
#    K = P_pred * H.T * inv(H * P_pred * H.T + R)
#    theta = theta_pred + K * (y - H * theta_pred)
#    P = (I - K * H) * P_pred
#
# Spread: s_t = y_t - (beta_t * x_t + alpha_t)
# Z-score: z_t = (s_t - rolling_mean(s)) / rolling_std(s)
#
# ADF: Augmented Dickey-Fuller test to check stationarity of spread.
# Rolling correlation: rolling Pearson corr(x, y)
#
# Important: We use Kalman result (beta_t, alpha_t) for spread. If Kalman unavailable
# (insufficient data), we fallback to OLS static beta/alpha repeated across time.

# -------------------------
# Timestamp normalizer
# -------------------------
def _maybe_convert_timestamp_series(ts_series: pd.Series) -> pd.Series:
    """
    Convert a timestamp column to pandas datetime.
    Handles integer epochs in seconds/ms/ns or ISO strings.
    """
    if pd.api.types.is_datetime64_any_dtype(ts_series):
        return pd.to_datetime(ts_series)
    try:
        s = pd.to_numeric(ts_series, errors="coerce")
        maxv = s.max()
        if pd.isna(maxv):
            return pd.to_datetime(ts_series, errors="coerce")
        if maxv > 1e12:
            return pd.to_datetime(s, unit="ns", errors="coerce")
        elif maxv > 1e11:
            return pd.to_datetime(s, unit="ms", errors="coerce")
        elif maxv > 1e9:
            return pd.to_datetime(s, unit="s", errors="coerce")
        else:
            return pd.to_datetime(s, errors="coerce")
    except Exception:
        return pd.to_datetime(ts_series, errors="coerce")

# -------------------------
# DB structure check (sanity)
# -------------------------
def check_db_structure(db_path: str = DB_PATH) -> None:
    """
    Logs table names and column lists in the SQLite DB. Useful for quick verification.
    """
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        return
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        logger.info(f"Connected to DB: {db_path}")
        for t in tables:
            cur.execute(f"PRAGMA table_info({t})")
            cols = [c[1] for c in cur.fetchall()]
            logger.info(f"Table: {t} -> {cols}")

# -------------------------
# Fetch recent ticks
# -------------------------
def fetch_recent_ticks(symbols: List[str], minutes: int = 60, db_path: str = DB_PATH) -> pd.DataFrame:
    """
    Fetch recent tick-level rows for given symbols.
    - symbols: list like ['BTCUSDT','ETHUSDT']
    - minutes: window length to fetch (relative to latest timestamp in DB)
    Returns DataFrame with columns: ['timestamp','symbol','price'] at minimum.
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found: {db_path}")

    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        if TABLE_NAME in tables:
            table = TABLE_NAME
        elif tables:
            table = tables[0]
        else:
            raise RuntimeError("No tables found in DB.")

        # Fetch a large recent chunk (ordered desc) and filter in-memory after timestamp conversion.
        query = f"SELECT * FROM {table} ORDER BY timestamp DESC LIMIT 200000"
        df = pd.read_sql_query(query, conn)

    if df.empty:
        return pd.DataFrame()

    # normalize column names
    df.columns = [c.lower() for c in df.columns]
    # common column names mapping
    tcol = next((c for c in ["timestamp", "time", "datetime"] if c in df.columns), None)
    scol = next((c for c in ["symbol", "sym", "pair"] if c in df.columns), None)
    pcol = next((c for c in ["price", "p", "last_price"] if c in df.columns), None)

    if not all([tcol, scol, pcol]):
        raise RuntimeError(f"Table {table} missing required columns. Found: {df.columns.tolist()}")

    df = df[[tcol, scol, pcol]].rename(columns={tcol: "timestamp", scol: "symbol", pcol: "price"})
    df["timestamp"] = _maybe_convert_timestamp_series(df["timestamp"])
    df = df.dropna(subset=["timestamp", "symbol", "price"])
    df["symbol"] = df["symbol"].astype(str)

    # filter symbols
    symbols_lower = [s.lower() for s in symbols]
    df = df[df["symbol"].str.lower().isin(symbols_lower)].copy()
    if df.empty:
        return pd.DataFrame()

    # scope to lookback relative to latest timestamp to avoid using stale history
    newest = df["timestamp"].max()
    cutoff = newest - pd.Timedelta(minutes=minutes)
    df = df[df["timestamp"] >= cutoff].copy()
    df = df.sort_values("timestamp").reset_index(drop=True)
    # ensure numeric price
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df.dropna(subset=["price"])
    return df

# -------------------------
# Robust resampling per symbol
# -------------------------
def resample_ticks_to_series(df: pd.DataFrame, timeframe: str = "1m") -> pd.DataFrame:
    """
    Resample tick DataFrame into a wide DataFrame: index = datetime, columns = symbols.
    Each column contains last price in the bin (close price).
    Implementation detail:
     - We resample per symbol independently to avoid MultiIndex pitfalls.
     - Return empty DataFrame if no data.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    if not {"timestamp", "symbol", "price"}.issubset(df.columns):
        raise ValueError("DataFrame must contain timestamp, symbol, price columns")

    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp", "symbol", "price"])
    if df.empty:
        return pd.DataFrame()

    resampled_dict = {}
    for sym, group in df.groupby("symbol"):
        g = group.set_index("timestamp").sort_index()
        # last price in bin = close price
        rs = g["price"].resample(timeframe).last()
        resampled_dict[sym] = rs

    if not resampled_dict:
        return pd.DataFrame()

    pivot = pd.concat(resampled_dict, axis=1)
    pivot = pivot.sort_index().dropna(how="all")
    return pivot

# -------------------------
# Data sufficiency check
# -------------------------
def check_data_sufficiency(bars: pd.DataFrame, min_bars: int = 10,
                           symbol_x: str = DEFAULT_BASE, symbol_y: str = DEFAULT_QUOTE) -> bool:
    """
    Check if resampled bars have enough overlapping data for analytics.
    Returns True if aligned bars >= min_bars.
    """
    if bars is None or bars.empty:
        logger.warning("Resampled bars empty.")
        return False
    # if fewer than 2 columns, cannot continue
    if bars.shape[1] < 2:
        logger.warning("Resampled bars do not include both symbols.")
        return False
    aligned = bars.dropna().shape[0]
    total = bars.shape[0]
    overlap_pct = (aligned / total * 100) if total > 0 else 0.0
    if aligned < min_bars:
        logger.warning(f"Data insufficient: {aligned}/{total} aligned ({overlap_pct:.1f}%). Need >= {min_bars}.")
        return False
    logger.info(f"Data sufficiency OK: {aligned}/{total} aligned ({overlap_pct:.1f}%) for {symbol_x}-{symbol_y}")
    return True

# -------------------------
# OLS hedge ratio (static)
# Formula: y = alpha + beta * x + eps
# -------------------------
def compute_hedge_ratio_ols(x: pd.Series, y: pd.Series) -> Tuple[float, float]:
    """
    Return (beta, alpha). If insufficient points, return (1.0, 0.0) fallback.
    """
    df = pd.concat([x, y], axis=1).dropna()
    if len(df) < 10:
        logger.warning(f"OLS fallback: only {len(df)} points (need >=10). Using beta=1.0")
        return 1.0, 0.0
    X = sm.add_constant(df.iloc[:, 0])
    model = sm.OLS(df.iloc[:, 1], X).fit()
    beta = float(model.params[1])
    alpha = float(model.params[0])
    return beta, alpha

# -------------------------
# Kalman filter for dynamic hedge ratio
# -------------------------
def compute_hedge_ratio_kalman(x: pd.Series, y: pd.Series,
                               delta: float = 1e-5, vt: float = 1e-3) -> pd.DataFrame:
    """
    Returns DataFrame with columns ['beta','alpha'] aligned with index of inputs.
    Implementation: simple 2-state Kalman filter estimating [beta_t, alpha_t].
    delta: process noise scale (smaller -> slower parameter change)
    vt: measurement noise variance (observation noise)
    """
    df = pd.concat([x, y], axis=1).dropna()
    n = len(df)
    if n < 5:
        raise ValueError(f"Not enough data for Kalman: {n} (need >=5)")
    X = df.iloc[:, 0].values
    Y = df.iloc[:, 1].values
    theta = np.zeros(2)  # [beta, alpha]
    P = np.eye(2) * 1.0
    Q = np.eye(2) * delta
    R = vt
    betas = np.zeros(n)
    alphas = np.zeros(n)
    for t in range(n):
        H = np.array([X[t], 1.0]).reshape(1, 2)  # 1x2
        theta_pred = theta
        P_pred = P + Q
        y_pred = H.dot(theta_pred)[0]
        e = Y[t] - y_pred
        S = H.dot(P_pred).dot(H.T) + R  # scalar
        K = P_pred.dot(H.T) / S
        theta = theta_pred + (K.flatten() * e)
        P = P_pred - K.dot(H).dot(P_pred)
        betas[t] = theta[0]
        alphas[t] = theta[1]
    return pd.DataFrame({"beta": betas, "alpha": alphas}, index=df.index)

# -------------------------
# Spread, z-score, ADF, rolling correlation
# -------------------------
def compute_spread(y: pd.Series, x: pd.Series, beta: pd.Series, alpha: pd.Series) -> pd.Series:
    """
    spread_t = y_t - (beta_t * x_t + alpha_t)
    If beta/alpha are scalars, they will be broadcast across series.
    """
    return y - (beta * x + alpha)

def compute_zscore(spread: pd.Series, window: int = 60) -> pd.Series:
    """(spread - rolling_mean) / rolling_std"""
    mu = spread.rolling(window=window, min_periods=max(3, int(window / 4))).mean()
    sigma = spread.rolling(window=window, min_periods=max(3, int(window / 4))).std()
    return (spread - mu) / sigma

def run_adf_test(spread: pd.Series) -> Dict[str, Any]:
    """
    Run Augmented Dickey-Fuller test on spread.
    Returns dict with adf_stat, pvalue; if insufficient data returns NaNs.
    """
    s = spread.dropna()
    if len(s) < 20:
        return {"adf_stat": float("nan"), "pvalue": float("nan")}
    res = adfuller(s, maxlag=10, autolag="AIC")
    return {"adf_stat": float(res[0]), "pvalue": float(res[1]), "critical_values": res[4]}

def compute_rolling_correlation(x: pd.Series, y: pd.Series, window: int = 60) -> pd.Series:
    """Rolling Pearson correlation between x and y."""
    return x.rolling(window=window, min_periods=max(3, int(window / 4))).corr(y)

# -------------------------
# Orchestrator: run_full_analytics
# -------------------------
def run_full_analytics(symbol_x: str = DEFAULT_BASE,
                       symbol_y: str = DEFAULT_QUOTE,
                       timeframe: str = "1m",
                       lookback_minutes: int = 120,
                       zscore_window: int = 60) -> Dict[str, Any]:
    """
    High-level pipeline:
     1) determine dynamic lookback (limit to last 6 hours)
     2) fetch ticks, resample to bars (timeframe)
     3) check data sufficiency; fallback to 10s if needed
     4) compute OLS; compute Kalman (or fallback)
     5) compute spread, zscore, adf, rolling corr
     6) assemble df_out and results dict
    Returns: {"results": results_dict, "df": df_out}
    """
    # --- Dynamic lookback bounded to last 6 hours to avoid historical tail skew ---
    try:
        with sqlite3.connect(DB_PATH) as conn:
            df_info = pd.read_sql_query(f"""
                SELECT symbol, MIN(timestamp) AS oldest, MAX(timestamp) AS newest
                FROM {TABLE_NAME}
                WHERE symbol IN ('{symbol_x}', '{symbol_y}')
                  AND timestamp >= strftime('%s','now','-6 hours')*1000
                GROUP BY symbol
            """, conn)
        if len(df_info) == 2:
            oldest = max(pd.to_datetime(df_info["oldest"]))
            newest = min(pd.to_datetime(df_info["newest"]))
            duration_min = (newest - oldest).total_seconds() / 60
            # use 80% of overlap duration, but not exceeding requested lookback
            lookback_minutes = int(min(lookback_minutes, max(10, duration_min * 0.8)))
            logger.info(f"Dynamic lookback adjusted to {lookback_minutes} minutes")
    except Exception as e:
        logger.warning(f"Dynamic lookback check failed: {e}")

    # --- Fetch ticks and resample ---
    ticks = fetch_recent_ticks([symbol_x, symbol_y], minutes=lookback_minutes)
    if ticks.empty:
        raise ValueError("No tick data available for requested symbols in lookback window.")

    bars = resample_ticks_to_series(ticks, timeframe)
    # if not sufficient, fallback to 10s timeframe
    if not check_data_sufficiency(bars, min_bars=10, symbol_x=symbol_x, symbol_y=symbol_y):
        logger.info("Falling back to 10s timeframe to attempt better overlap.")
        bars = resample_ticks_to_series(ticks, "10s")
        if not check_data_sufficiency(bars, min_bars=5, symbol_x=symbol_x, symbol_y=symbol_y):
            raise ValueError("Insufficient data even after fallback resampling.")

    # Ensure both symbols present
    if bars.shape[1] < 2:
        raise RuntimeError("Resampled bars do not contain both symbols.")

    # Align series
    # pick the first two columns as x and y (consistent order depends on symbol names)
    sym_cols = list(bars.columns[:2])
    x = bars[sym_cols[0]].astype(float)
    y = bars[sym_cols[1]].astype(float)
    df_pair = pd.concat([x, y], axis=1).dropna()
    df_pair.columns = ["x_price", "y_price"]
    if df_pair.empty:
        raise ValueError("No aligned bars after resampling.")

    logger.info(f"Resampled bars count: {len(df_pair)}")

    # --- OLS static hedge ratio ---
    beta_ols, alpha_ols = compute_hedge_ratio_ols(df_pair["x_price"], df_pair["y_price"])

    # --- Kalman dynamic hedge ratio (fallback to OLS if Kalman fails) ---
    try:
        kalman_df = compute_hedge_ratio_kalman(df_pair["x_price"], df_pair["y_price"])
    except Exception as e:
        logger.warning(f"Kalman failed: {e}. Falling back to static OLS values.")
        kalman_df = pd.DataFrame({
            "beta": np.repeat(beta_ols, len(df_pair)),
            "alpha": np.repeat(alpha_ols, len(df_pair))
        }, index=df_pair.index)

    # --- Spread computed using dynamic beta/alpha ---
    spread = compute_spread(df_pair["y_price"], df_pair["x_price"], kalman_df["beta"], kalman_df["alpha"])

    # --- Z-score (rolling) ---
    zscore = compute_zscore(spread, window=zscore_window)

    # --- ADF test on spread (static or dynamic spread? We use dynamic spread here) ---
    adf_res = run_adf_test(spread)

    # --- Rolling correlation ---
    rolling_corr = compute_rolling_correlation(df_pair["x_price"], df_pair["y_price"], window=zscore_window)

    # --- Compose output DataFrame (fixed column order for downstream)
    df_out = pd.DataFrame({
        "x_price": df_pair["x_price"],
        "y_price": df_pair["y_price"],
        "beta_kalman": kalman_df["beta"],
        "alpha_kalman": kalman_df["alpha"],
        "spread": spread,
        "zscore": zscore,
        "rolling_corr": rolling_corr
    }, index=df_pair.index)

    # Latest available metrics (dropna to find last valid row)
    latest_idx = df_out.dropna().index[-1]
    results = {
        "symbol_x": sym_cols[0],
        "symbol_y": sym_cols[1],
        "num_bars": int(df_out.shape[0]),
        "hedge_ratio_ols": float(beta_ols),
        "intercept_ols": float(alpha_ols),
        "kalman_beta_latest": float(df_out.loc[latest_idx, "beta_kalman"]),
        "kalman_alpha_latest": float(df_out.loc[latest_idx, "alpha_kalman"]),
        "zscore_latest": float(df_out.loc[latest_idx, "zscore"]) if not pd.isna(df_out.loc[latest_idx, "zscore"]) else float("nan"),
        "adf_pvalue": adf_res.get("pvalue"),
        "adf_stat": adf_res.get("adf_stat"),
        "rolling_corr_latest": float(df_out.loc[latest_idx, "rolling_corr"]) if not pd.isna(df_out.loc[latest_idx, "rolling_corr"]) else float("nan")
    }

    logger.info(f"Analytics complete: {results['symbol_x']}-{results['symbol_y']} | OLS beta={beta_ols:.6f} | Latest kalman={results['kalman_beta_latest']:.6f} | z={results['zscore_latest']:.4f}")

    return {"results": results, "df": df_out}

# -------------------------
# Save metrics to DB
# -------------------------
def save_analytics_results_to_db(results: Dict[str, Any],
                                 db_path: str = DB_PATH,
                                 table_name: str = ANALYTICS_TABLE) -> None:
    """
    Save a flattened set of metrics to the analytics_results table.
    Schema (id, symbol, metric_name, metric_value, timestamp)
    Only writes keys in METRICS_TO_WRITE (except symbol_x/symbol_y which are used to form pair).
    """
    import sqlite3
    from datetime import datetime

    sym_pair = f"{results.get('symbol_x')}_{results.get('symbol_y')}"
    rows = []

    # Prepare rows for insertion
    for metric in METRICS_TO_WRITE:
        if metric in results:
            val = results[metric]
            try:
                valf = float(val)
            except Exception:
                valf = None
            if valf is not None and not pd.isna(valf):
                # Add explicit timestamp for each metric
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                rows.append((sym_pair, metric, valf, now))

    if not rows:
        logger.info("No metrics to save this cycle.")
        return

    # Write safely to SQLite
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        # Ensure table exists with correct structure
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name}(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                timestamp DATETIME NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)
        # Explicit timestamp inclusion
        cur.executemany(
            f"INSERT INTO {table_name}(symbol, metric_name, metric_value, timestamp) VALUES (?, ?, ?, ?)",
            rows
        )
        conn.commit()

    logger.info(f"Saved {len(rows)} metrics for {sym_pair}")

# -------------------------
# Visualization helper (debug / streamlit prototype)
# -------------------------
def visualize_analytics(df: pd.DataFrame, results: Dict[str, Any]):
    """
    Quick debug visualization: top panel = Kalman beta vs OLS; bottom = spread + zscore.
    Meant for local debugging only; Streamlit should use plotly or equivalent.
    """
    if df is None or df.empty:
        logger.warning("No data to visualize.")
        return
    plt.style.use("dark_background")
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    fig.suptitle(f"Analytics: {results.get('symbol_x')} vs {results.get('symbol_y')}")
    axes[0].plot(df.index, df["beta_kalman"], label="Kalman beta")
    axes[0].axhline(results.get("hedge_ratio_ols", 0.0), linestyle="--", label="OLS beta")
    axes[0].set_ylabel("beta")
    axes[0].legend()
    axes[1].plot(df.index, df["spread"], label="spread")
    axes[1].plot(df.index, df["zscore"], label="zscore")
    axes[1].axhline(2.0, linestyle="--", color="red")
    axes[1].axhline(-2.0, linestyle="--", color="green")
    axes[1].legend()
    plt.tight_layout()
    plt.show()

# -------------------------
# Main continuous loop
# -------------------------
if __name__ == "__main__":
    # Production-run loop:
    check_db_structure()
    logger.info("Starting analytics loop...")
    while True:
        try:
            out = run_full_analytics()  # default symbols/timeframe
            save_analytics_results_to_db(out["results"])
            # csv preview (for debugging / streamlit quick-load)
            csv_path = os.path.join(os.path.dirname(__file__), "analytics_preview.csv")
            out["df"].to_csv(csv_path)
            logger.info(f"CSV preview updated: {csv_path}")
            # optional local visualization (comment out for headless servers)
            # visualize_analytics(out["df"], out["results"])
            # Pause until next cycle
            time.sleep(60)
        except ValueError as ve:
            # expected recoverable conditions: insufficient data, etc.
            logger.warning(f"Skipping analytics cycle: {ve}")
            time.sleep(30)
        except KeyboardInterrupt:
            logger.info("Analytics loop stopped manually.")
            break
        except Exception as e:
            logger.error(f"Unexpected analytics error: {e}")
            time.sleep(10)
