"""Shared pair-price retrieval for API and analytics code."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from database.database_setup import DB_PATH, init_db


def get_conn() -> sqlite3.Connection:
    init_db()
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def parse_pair(symbol_pair: str) -> tuple[str, str]:
    parts = [p.strip().upper() for p in str(symbol_pair).split("_")]
    if len(parts) != 2 or not all(parts):
        raise ValueError("symbol_pair must have the form BASE_QUOTE, e.g. BTCUSDT_ETHUSDT")
    if parts[0] == parts[1]:
        raise ValueError("A pair must contain two different symbols")
    return parts[0], parts[1]


def get_recent_pair_prices(symbol_pair: str, limit: int = 1000, tolerance_seconds: float = 2.0) -> pd.DataFrame:
    """Fetch both legs and align trades by nearest timestamp."""
    a, b = parse_pair(symbol_pair)
    limit = max(10, min(int(limit), 5000))

    with get_conn() as conn:
        query = """
            SELECT timestamp, price
            FROM tick_data
            WHERE UPPER(symbol) = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """
        x = pd.read_sql_query(query, conn, params=(a, limit))
        y = pd.read_sql_query(query, conn, params=(b, limit))

    if x.empty or y.empty:
        return pd.DataFrame()

    for frame in (x, y):
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
        frame["price"] = pd.to_numeric(frame["price"], errors="coerce")

    x = x.dropna().sort_values("timestamp").rename(columns={"price": "x_price"})
    y = y.dropna().sort_values("timestamp").rename(columns={"price": "y_price"})

    merged = pd.merge_asof(
        x,
        y,
        on="timestamp",
        direction="nearest",
        tolerance=pd.Timedelta(seconds=tolerance_seconds),
    )
    return merged.dropna(subset=["x_price", "y_price"]).reset_index(drop=True)
