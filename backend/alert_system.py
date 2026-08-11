"""Stateful z-score signal engine and alert persistence."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pandas as pd

from database.database_setup import DB_PATH, init_db

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ALERT_DIR = PROJECT_ROOT / "alerts"
INPUT_CSV = PROJECT_ROOT / "backend" / "analytics_preview.csv"
OUTPUT_CSV = ALERT_DIR / "alerts_output.csv"
UPPER_Z = float(os.getenv("ALERT_UPPER_Z", "2.0"))
LOWER_Z = float(os.getenv("ALERT_LOWER_Z", "-2.0"))


def get_db_connection():
    init_db()
    return sqlite3.connect(str(DB_PATH), timeout=30)


def _signal_for_z(z):
    if pd.isna(z):
        return "HOLD", "Insufficient z-score data."
    if z > UPPER_Z:
        return "SHORT", f"Z-score > +{UPPER_Z:g}: spread is relatively overbought."
    if z < LOWER_Z:
        return "LONG", f"Z-score < {LOWER_Z:g}: spread is relatively oversold."
    return "HOLD", "Z-score is inside the neutral range."


def generate_alerts(df: pd.DataFrame) -> pd.DataFrame:
    """Generate the complete signal state series without writing to the DB."""
    if "zscore" not in df.columns:
        raise ValueError("Input DataFrame must contain a zscore column")
    out = df.copy()
    values = out["zscore"].apply(_signal_for_z)
    out["signal"] = values.map(lambda x: x[0])
    out["reason"] = values.map(lambda x: x[1])
    return out


def _transition_events(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["previous_signal"] = out["signal"].shift(1).fillna("HOLD")
    return out[out["signal"] != out["previous_signal"]].copy()


def insert_alert_record(alert: dict) -> None:
    """Insert one signal transition, ignoring an already stored transition."""
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO alerts_data
                (symbol_pair, timestamp, signal, zscore, spread)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                alert["symbol_pair"],
                alert["timestamp"],
                alert["signal"],
                alert.get("zscore"),
                alert.get("spread"),
            ),
        )
        conn.commit()


def run_alert_system(input_csv=INPUT_CSV, output_csv=OUTPUT_CSV) -> pd.DataFrame:
    """Read analytics output, export states, and persist only signal transitions."""
    input_csv = Path(input_csv)
    output_csv = Path(output_csv)
    if not input_csv.exists():
        raise FileNotFoundError(f"Analytics file not found: {input_csv}")

    df = pd.read_csv(input_csv)
    if "timestamp" not in df.columns:
        raise ValueError("Analytics CSV must contain a timestamp column")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    alerts = generate_alerts(df)

    ALERT_DIR.mkdir(parents=True, exist_ok=True)
    alerts.to_csv(output_csv, index=False)

    symbol_x = os.getenv("ANALYTICS_SYMBOL_X", "BTCUSDT").upper()
    symbol_y = os.getenv("ANALYTICS_SYMBOL_Y", "ETHUSDT").upper()
    pair = f"{symbol_x}_{symbol_y}"

    for _, row in _transition_events(alerts).iterrows():
        insert_alert_record({
            "symbol_pair": pair,
            "timestamp": row["timestamp"].isoformat(),
            "signal": row["signal"],
            "zscore": float(row["zscore"]) if pd.notna(row.get("zscore")) else None,
            "spread": float(row["spread"]) if pd.notna(row.get("spread")) else None,
        })

    return alerts


def prepare_realtime_output(alerts_df: pd.DataFrame) -> dict:
    if alerts_df is None or alerts_df.empty:
        return {}
    latest = alerts_df.iloc[-1]
    return {
        "timestamp": str(latest["timestamp"]),
        "signal": latest["signal"],
        "reason": latest["reason"],
        "zscore": float(latest["zscore"]) if pd.notna(latest.get("zscore")) else None,
        "spread": float(latest["spread"]) if pd.notna(latest.get("spread")) else None,
    }


if __name__ == "__main__":
    result = run_alert_system()
    print(prepare_realtime_output(result))
