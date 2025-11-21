# =====================================================
# File: backend/alert_system.py
# Purpose: Generate and store trading alerts (DB + CSV)
# Author: Suraj Prakash (Quant Developer)
# =====================================================

import pandas as pd
import json
import os
import sqlite3
from datetime import datetime
import logging

# ================= CONFIGURATION ======================
ALERT_DIR = r"D:\Quant Analytics App\alerts"
INPUT_CSV = r"D:\Quant Analytics App\backend\analytics_preview.csv"
OUTPUT_CSV = os.path.join(ALERT_DIR, "alerts_output.csv")
DB_PATH = r"D:\Quant Analytics App\database\quant_data.db"

UPPER_Z = 2.0   # Overbought threshold -> SHORT
LOWER_Z = -2.0  # Oversold threshold  -> LONG

# =====================================================
# Helper: Ensure DB connection
# =====================================================
def get_db_connection():
    """Return SQLite connection object."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# =====================================================
# Helper: Insert alert into DB
# =====================================================
def insert_alert_record(alert_dict):
    """Insert a single alert into the alerts_data table."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO alerts_data
            (timestamp, symbol1, symbol2, signal, reason, zscore, spread, hedge_ratio)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            alert_dict["timestamp"],
            alert_dict.get("symbol1", "BTCUSDT"),
            alert_dict.get("symbol2", "ETHUSDT"),
            alert_dict["signal"],
            alert_dict["reason"],
            alert_dict.get("zscore"),
            alert_dict.get("spread"),
            alert_dict.get("hedge_ratio")
        ))

        conn.commit()
        conn.close()
        logging.info(f" Alert inserted into DB: {alert_dict['signal']} @ {alert_dict['timestamp']}")

    except Exception as e:
        logging.error(f" Error inserting alert into DB: {str(e)}")


# =====================================================
# Function: Generate alerts from analytics DataFrame
# =====================================================
def generate_alerts(df: pd.DataFrame) -> pd.DataFrame:
    """Generate trading signals based on z-score thresholds."""
    signals, reasons = [], []

    for z in df["zscore"]:
        if z > UPPER_Z:
            signals.append("SHORT")
            reasons.append("Z-score > +2 → Spread overbought, short the pair.")
        elif z < LOWER_Z:
            signals.append("LONG")
            reasons.append("Z-score < -2 → Spread oversold, long the pair.")
        else:
            signals.append("HOLD")
            reasons.append("Within neutral range → No trade signal.")

    df["signal"] = signals
    df["reason"] = reasons
    return df


# =====================================================
# Function: Main Alert System Runner
# =====================================================
def run_alert_system():
    """Generate alerts and store results (to DB + CSV)."""
    if not os.path.exists(ALERT_DIR):
        os.makedirs(ALERT_DIR)

    if not os.path.exists(INPUT_CSV):
        raise FileNotFoundError(f"Analytics file not found: {INPUT_CSV}")

    df = pd.read_csv(INPUT_CSV)
    if "zscore" not in df.columns:
        raise ValueError("Input CSV must contain a 'zscore' column.")

    # Generate alert signals
    df_alerts = generate_alerts(df)

    # Save alerts to CSV
    df_alerts.to_csv(OUTPUT_CSV, index=False)
    print(f"[{datetime.now()}]  Alerts saved to CSV → {OUTPUT_CSV}")

    # Save alerts to DB
    for _, row in df_alerts.iterrows():
        alert_dict = {
            "timestamp": str(row.get("timestamp")),
            "symbol1": str(row.get("symbol1", "BTCUSDT")),
            "symbol2": str(row.get("symbol2", "ETHUSDT")),
            "signal": row.get("signal"),
            "reason": row.get("reason"),
            "zscore": float(row.get("zscore", 0)),
            "spread": float(row.get("spread", 0)),
            "hedge_ratio": float(row.get("beta_kalman", 0))
        }
        insert_alert_record(alert_dict)

    print(f"[{datetime.now()}]  Alerts stored into database → {DB_PATH}")
    return df_alerts


# =====================================================
# Helper: Print Latest Signal
# =====================================================
def print_latest_signal(alerts_df):
    """Print the most recent signal with reasoning."""
    latest = alerts_df.iloc[-1]
    print("\n Latest Alert Summary")
    print("──────────────────────────────")
    print(f"Timestamp : {latest['timestamp']}")
    print(f"Z-Score   : {latest['zscore']:.3f}")
    print(f"Signal    : {latest['signal']}")
    print(f"Reason    : {latest['reason']}")
    print("──────────────────────────────\n")


# =====================================================
# Helper: Prepare Real-time Output Dict
# =====================================================
def prepare_realtime_output(alerts_df):
    """Return dict containing the latest alert for downstream modules."""
    latest = alerts_df.iloc[-1]
    return {
        "timestamp": str(latest["timestamp"]),
        "symbol1": str(latest.get("symbol1", "BTCUSDT")),
        "symbol2": str(latest.get("symbol2", "ETHUSDT")),
        "signal": latest["signal"],
        "reason": latest["reason"],
        "zscore": float(latest.get("zscore", 0)),
        "spread": float(latest.get("spread", 0)),
        "hedge_ratio": float(latest.get("beta_kalman", 0))
    }


# =====================================================
# Run Standalone (for testing)
# =====================================================
if __name__ == "__main__":
    df_alerts = run_alert_system()
    print_latest_signal(df_alerts)
    latest_output = prepare_realtime_output(df_alerts)
    print("Realtime Output Dict:")
    print(json.dumps(latest_output, indent=4))
