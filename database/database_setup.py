"""Canonical SQLite schema and initialization.

The application has one runtime database: ``database/quant_data.db``.
Schema creation is idempotent and safe to call during application startup.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "database" / "quant_data.db"


def get_connection() -> sqlite3.Connection:
    """Return a configured SQLite connection."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db(db_path: str | os.PathLike[str] = DB_PATH) -> Path:
    """Create all application tables and indexes if they do not exist."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(path), timeout=30) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tick_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                price REAL NOT NULL,
                volume REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS resampled_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                interval TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL
            );

            CREATE TABLE IF NOT EXISTS analytics_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL,
                timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS analytics_cleaned (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pair_symbol TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                hedge_ratio REAL,
                zscore REAL,
                adf_pvalue REAL,
                rolling_corr REAL,
                spread REAL,
                mean_spread REAL,
                std_spread REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(pair_symbol, timestamp)
            );

            CREATE TABLE IF NOT EXISTS alerts_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol_pair TEXT,
                timestamp TEXT,
                signal TEXT,
                zscore REAL,
                spread REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_tick_symbol_timestamp
                ON tick_data(symbol, timestamp);
            CREATE INDEX IF NOT EXISTS idx_tick_timestamp
                ON tick_data(timestamp);
            CREATE INDEX IF NOT EXISTS idx_analytics_symbol_metric_timestamp
                ON analytics_results(symbol, metric_name, timestamp);
            CREATE INDEX IF NOT EXISTS idx_cleaned_pair_timestamp
                ON analytics_cleaned(pair_symbol, timestamp);
            CREATE INDEX IF NOT EXISTS idx_alerts_pair_timestamp
                ON alerts_data(symbol_pair, timestamp);
            """
        )
        conn.commit()

    return path


# Preserve the old script-style behavior.
if __name__ == "__main__":
    print(f"Initializing database: {DB_PATH}")
    print(f"Database ready: {init_db()}")
