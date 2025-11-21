# ======================================================
# File: backend/backtest_engine.py
# Purpose: Backtest engine with edge-trigger entries, fees/slippage, and notional PnL
# Author: Suraj Prakash (Quant Developer) - Updated
# Created: 2025-11-08 (updated)
# ======================================================

"""
Features:
- Edge-trigger entry/exit (configurable)
- Transaction costs: fee_per_trade (cash) + slippage_pct (fraction of notional)
- Notional PnL: convert spread unit moves to cash via notional_per_unit
- Outputs:
    - backtest/backtest_results.csv (row-by-row)
    - backtest/backtest_metrics.json (summary)
    - backtest/pnl_curve.png (plot)
Notes:
- Input CSV must contain: timestamp, spread, signal
- For notional conversions it's helpful if csv also contains x_price, y_price, beta_kalman,
  but primary notional uses spread difference × notional_per_unit.
"""

import os
import json
from datetime import datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ---------------- CONFIG ----------------
PROJECT_ROOT = r"D:\Quant Analytics App"
ALERT_CSV = os.path.join(PROJECT_ROOT, "alerts", "alerts_output.csv")
BACKTEST_DIR = os.path.join(PROJECT_ROOT, "backtest")
RESULTS_CSV = os.path.join(BACKTEST_DIR, "backtest_results.csv")
METRICS_JSON = os.path.join(BACKTEST_DIR, "backtest_metrics.json")
PNL_PLOT = os.path.join(BACKTEST_DIR, "pnl_curve.png")

# Backtest params (tweak these)
POSITION_SIZE = 1.0            # units (spread-units) per trade (keeps sign)
NOTIONAL_PER_UNIT = 1000.0     # $ value of 1 unit of spread (important to scale tiny spreads to dollars)
FEE_PER_TRADE = 0.5           # $ fee per trade side (entry or exit)
SLIPPAGE_PCT = 0.0005         # 0.05% slippage applied to notional per side
ENTRY_ON_EDGE = True          # If True: only enter on HOLD -> LONG/SHORT changes (edge-trigger)
ANNUAL_TRADING_DAYS = 252

# -------------------------------------------------


def ensure_dirs():
    """Create output directory if missing."""
    if not os.path.exists(BACKTEST_DIR):
        os.makedirs(BACKTEST_DIR)


def load_alerts(path=ALERT_CSV):
    """Load alerts CSV into a DataFrame and validate required columns."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Alerts CSV not found at: {path}")

    df = pd.read_csv(path)

    # Required columns
    required = ["timestamp", "spread", "signal"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Required column '{col}' not found in alerts CSV.")

    # Parse timestamp and sort
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    df["spread"] = pd.to_numeric(df["spread"], errors="coerce")
    if df["spread"].isnull().any():
        raise ValueError("Spread column contains NaN or non-numeric values. Clean your analytics data.")

    # Optional helpful columns - coerce numeric if exist
    for col in ("x_price", "y_price", "beta_kalman"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def infer_periods_per_day(df):
    """Estimate number of periods per day for annualization."""
    if len(df) < 3:
        return 1
    deltas = df["timestamp"].diff().dt.total_seconds().dropna()
    median_seconds = deltas.median()
    if median_seconds <= 0:
        return 1
    return max(1.0, 86400.0 / median_seconds)


def simulate_backtest(df,
                      position_size=POSITION_SIZE,
                      notional_per_unit=NOTIONAL_PER_UNIT,
                      fee_per_trade=FEE_PER_TRADE,
                      slippage_pct=SLIPPAGE_PCT,
                      entry_on_edge=ENTRY_ON_EDGE):
    """
    Simulate backtest with:
    - edge-trigger logic if entry_on_edge True
    - costs (fee and slippage) applied at position changes
    Returns: df with columns: position, position_prev, pnl, trade_cost, cum_pnl, cash_pnl
    """
    df = df.copy().reset_index(drop=True)

    # Prepare baseline columns
    # map simple signals to numeric requested positions (desired)
    signal_to_pos = {"LONG": +1.0 * position_size, "SHORT": -1.0 * position_size, "HOLD": 0.0}
    df["desired_pos"] = df["signal"].map(signal_to_pos).fillna(0.0)

    # We'll build actual position under edge-trigger rules
    df["position"] = 0.0
    in_trade = False

    for i in range(len(df)):
        if i == 0:
            prev_signal = "HOLD"
            prev_pos = 0.0
        else:
            prev_signal = df.at[i - 1, "signal"]
            prev_pos = df.at[i - 1, "position"]

        curr_signal = df.at[i, "signal"]
        desired_pos = df.at[i, "desired_pos"]

        # Default copy previous position (hold)
        position_now = prev_pos

        if entry_on_edge:
            # Open entry only when previous signal was HOLD and current is LONG/SHORT
            if (prev_signal == "HOLD" or prev_pos == 0.0) and curr_signal in ("LONG", "SHORT"):
                # open a new trade
                position_now = desired_pos
            # Close when current is HOLD
            elif curr_signal == "HOLD" and prev_pos != 0.0:
                position_now = 0.0
            # Flip: if currently in trade and signal changes to opposite (e.g. LONG->SHORT), then close then open opposite
            elif prev_pos != 0.0 and curr_signal in ("LONG", "SHORT") and np.sign(desired_pos) != np.sign(prev_pos):
                # We implement flip by closing (set 0) at this timestamp, then opening opposite next timestamp.
                # Simpler: close now, and open opposite immediately (with two costs). To keep logic clear,
                # we will close now and open opposite immediately (position_now = desired_pos)
                # but we will count costs for both exit and entry (abs change > 1).
                position_now = desired_pos
            # Otherwise keep prev_pos
        else:
            # direct mapping (legacy): position is desired_pos
            position_now = desired_pos

        df.at[i, "position"] = float(position_now)

    # Now compute pnl: use spread differences and previous position
    df["spread_prev"] = df["spread"].shift(1)
    df["spread_diff"] = df["spread"] - df["spread_prev"]
    df["position_prev"] = df["position"].shift(1).fillna(0.0)

    # Base cash pnl from spread movement scaled to notional per unit
    # cash_pnl = position_prev * spread_diff * notional_per_unit
    df["cash_pnl_raw"] = df["position_prev"] * df["spread_diff"] * notional_per_unit
    df["cash_pnl_raw"] = df["cash_pnl_raw"].fillna(0.0)

    # Compute trade costs at times where position changes (i.e., abs(position - position_prev) > 0)
    df["pos_change"] = (df["position"] - df["position_prev"]).abs()
    # number_of_sides = pos_change, but for flip from +1 to -1 pos_change=2 -> two sides (exit+entry)
    # trade_cost = (fee_per_trade + slippage_pct * notional_per_unit) * pos_change
    df["trade_cost"] = (fee_per_trade + (slippage_pct * notional_per_unit)) * df["pos_change"]

    # Final pnl after costs
    df["pnl"] = df["cash_pnl_raw"] - df["trade_cost"]

    # cumulative PnL
    df["cum_pnl"] = df["pnl"].cumsum()

    # Return columns of interest
    cols_keep = ["timestamp", "x_price", "y_price", "beta_kalman", "spread", "signal",
                 "desired_pos", "position", "position_prev", "spread_diff",
                 "cash_pnl_raw", "trade_cost", "pnl", "cum_pnl"]
    # Some may not exist (x_price etc.), handle gracefully
    cols_keep = [c for c in cols_keep if c in df.columns]
    return df[cols_keep]


def _extract_trades(df):
    """
    Extract trades from the actual position series.
    Each trade = contiguous period where position != 0 (entry index included, exit index is the last index of trade).
    Returns list of dicts with entry/exit indices, timestamps, position, trade_pnl (after costs).
    """
    trades = []
    pos = df["position"].values
    pnl = df["pnl"].values
    ts = df["timestamp"].values

    in_trade = False
    entry_idx = None
    entry_pos = 0.0
    acc_pnl = 0.0

    for i in range(len(pos)):
        current_pos = pos[i]
        if not in_trade and current_pos != 0.0:
            # start trade at i (entry happens at i)
            in_trade = True
            entry_idx = i
            entry_pos = current_pos
            acc_pnl = 0.0

        if in_trade:
            acc_pnl += pnl[i]

        # check if trade ends here (next position is zero or different sign)
        next_pos = pos[i + 1] if i + 1 < len(pos) else 0.0
        if in_trade and (next_pos == 0.0 or np.sign(next_pos) != np.sign(current_pos)):
            # trade exit effective here
            exit_idx = i
            trades.append({
                "entry_idx": int(entry_idx),
                "exit_idx": int(exit_idx),
                "entry_ts": str(ts[entry_idx]),
                "exit_ts": str(ts[exit_idx]),
                "position": float(entry_pos),
                "trade_pnl": float(acc_pnl)
            })
            in_trade = False
            entry_idx = None
            acc_pnl = 0.0

    return trades


def compute_metrics(df):
    """Compute summary metrics including fees-aware totals and notional scaling."""
    total_pnl = float(df["cum_pnl"].iloc[-1]) if len(df) > 0 else 0.0
    returns = df["pnl"].fillna(0.0)

    periods_per_day = infer_periods_per_day(df)
    annual_factor = np.sqrt(ANNUAL_TRADING_DAYS * periods_per_day)

    mean_ret = returns.mean()
    std_ret = returns.std(ddof=1) if returns.std(ddof=1) != 0 else 0.0
    sharpe = (mean_ret / std_ret) * annual_factor if std_ret != 0 else None

    cum = df["cum_pnl"]
    running_max = cum.cummax()
    drawdown = cum - running_max
    max_drawdown = float(drawdown.min()) if len(drawdown) > 0 else 0.0

    trades = _extract_trades(df)
    n_trades = len(trades)
    winning_trades = sum(1 for t in trades if t["trade_pnl"] > 0)
    win_rate = (winning_trades / n_trades) if n_trades > 0 else None
    avg_trade_pnl = (sum(t["trade_pnl"] for t in trades) / n_trades) if n_trades > 0 else 0.0

    metrics = {
        "total_pnl": total_pnl,
        "sharpe": float(sharpe) if sharpe is not None else None,
        "max_drawdown": max_drawdown,
        "n_trades": n_trades,
        "win_rate": float(win_rate) if win_rate is not None else None,
        "avg_trade_pnl": avg_trade_pnl,
        "periods_per_day_est": periods_per_day,
    }
    metrics["trades_sample"] = trades[:50]
    return metrics


def plot_pnl_curve(df, path=PNL_PLOT):
    """Plot cumulative PnL curve and save to file."""
    plt.figure(figsize=(10, 5))
    plt.plot(df["timestamp"], df["cum_pnl"])
    plt.xlabel("Time")
    plt.ylabel("Cumulative PnL ($)")
    plt.title("Backtest — Cumulative PnL (cash)")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


def save_results(df, metrics):
    """Save backtest row-by-row results and metrics."""
    df_to_save = df.copy()
    df_to_save.to_csv(RESULTS_CSV, index=False)
    with open(METRICS_JSON, "w") as f:
        json.dump(metrics, f, indent=4, default=str)


def print_summary(metrics):
    """Print a concise summary to console."""
    print("\nBacktest Summary")
    print("-------------------------------")
    print(f"Total PnL      : ${metrics['total_pnl']:.6f}")
    print(f"Sharpe (ann.)  : {metrics['sharpe']}")
    print(f"Max Drawdown   : ${metrics['max_drawdown']:.6f}")
    print(f"Number Trades  : {metrics['n_trades']}")
    print(f"Win Rate       : {metrics['win_rate']}")
    print(f"Avg Trade PnL  : ${metrics['avg_trade_pnl']:.6f}")
    print("-------------------------------\n")


def main():
    ensure_dirs()
    df_alerts = load_alerts(ALERT_CSV)
    df_bt = simulate_backtest(df_alerts,
                              position_size=POSITION_SIZE,
                              notional_per_unit=NOTIONAL_PER_UNIT,
                              fee_per_trade=FEE_PER_TRADE,
                              slippage_pct=SLIPPAGE_PCT,
                              entry_on_edge=ENTRY_ON_EDGE)
    metrics = compute_metrics(df_bt)
    save_results(df_bt, metrics)
    plot_pnl_curve(df_bt)
    print_summary(metrics)
    return df_bt, metrics


if __name__ == "__main__":
    df_results, summary_metrics = main()
