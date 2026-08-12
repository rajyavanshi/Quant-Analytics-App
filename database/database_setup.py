"""Canonical SQLite schema and idempotent migrations."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "database" / "quant_data.db"


def get_connection(db_path: str | os.PathLike[str] = DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {definition}')


def _migrate_legacy_alerts_table(conn: sqlite3.Connection) -> None:
    """Migrate the pre-hardening alerts schema without losing existing events.

    Older databases used required ``symbol1``/``symbol2`` columns while the
    application now uses one canonical ``symbol_pair`` column. SQLite cannot
    drop NOT NULL columns in-place, so rebuild the table when those legacy
    columns are present.
    """
    info = conn.execute('PRAGMA table_info("alerts_data")').fetchall()
    columns = {row[1]: row for row in info}
    if "symbol1" not in columns and "symbol2" not in columns:
        return

    conn.execute("DROP TABLE IF EXISTS alerts_data_v2")
    conn.execute(
        """
        CREATE TABLE alerts_data_v2 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol_pair TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            signal TEXT NOT NULL,
            zscore REAL,
            spread REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    has_pair = "symbol_pair" in columns
    has_zscore = "zscore" in columns
    has_spread = "spread" in columns
    has_created_at = "created_at" in columns
    pair_expr = (
        "COALESCE(NULLIF(symbol_pair, ''), symbol1 || '_' || symbol2)"
        if has_pair
        else "symbol1 || '_' || symbol2"
    )
    zscore_expr = "zscore" if has_zscore else "NULL"
    spread_expr = "spread" if has_spread else "NULL"
    created_expr = "created_at" if has_created_at else "CURRENT_TIMESTAMP"

    conn.execute(
        f"""
        INSERT INTO alerts_data_v2(id, symbol_pair, timestamp, signal, zscore, spread, created_at)
        SELECT id, {pair_expr}, timestamp, signal, {zscore_expr}, {spread_expr}, {created_expr}
        FROM alerts_data
        WHERE {pair_expr} IS NOT NULL
        """
    )
    conn.execute("DROP TABLE alerts_data")
    conn.execute("ALTER TABLE alerts_data_v2 RENAME TO alerts_data")


def init_db(db_path: str | os.PathLike[str] = DB_PATH) -> Path:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(path), timeout=30) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tick_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                trade_id INTEGER,
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
                symbol_pair TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                signal TEXT NOT NULL,
                zscore REAL,
                spread REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # Existing databases predate trade identity. The new column is nullable
        # so historical rows remain valid; live Binance rows receive a trade_id.
        _ensure_columns(conn, "tick_data", {
            "trade_id": "INTEGER",
            "volume": "REAL",
        })
        _ensure_columns(conn, "analytics_cleaned", {
            "hedge_ratio": "REAL", "zscore": "REAL", "adf_pvalue": "REAL",
            "rolling_corr": "REAL", "spread": "REAL", "mean_spread": "REAL",
            "std_spread": "REAL", "created_at": "TIMESTAMP",
        })
        _ensure_columns(conn, "alerts_data", {
            "symbol_pair": "TEXT", "zscore": "REAL", "spread": "REAL",
            "created_at": "TIMESTAMP",
        })

        # Migrate legacy alert tables before enforcing the canonical schema.
        _migrate_legacy_alerts_table(conn)

        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_tick_symbol_timestamp ON tick_data(symbol, timestamp);
            CREATE INDEX IF NOT EXISTS idx_tick_timestamp ON tick_data(timestamp);
            CREATE INDEX IF NOT EXISTS idx_tick_symbol_trade_id
                ON tick_data(symbol, trade_id)
                WHERE trade_id IS NOT NULL;
            CREATE UNIQUE INDEX IF NOT EXISTS uq_tick_symbol_trade_id
                ON tick_data(symbol, trade_id)
                WHERE trade_id IS NOT NULL;
            CREATE INDEX IF NOT EXISTS idx_analytics_symbol_metric_timestamp ON analytics_results(symbol, metric_name, timestamp);
            CREATE INDEX IF NOT EXISTS idx_cleaned_pair_timestamp ON analytics_cleaned(pair_symbol, timestamp);
            CREATE INDEX IF NOT EXISTS idx_alerts_pair_timestamp ON alerts_data(symbol_pair, timestamp);
            """
        )
        conn.commit()
    return path


if __name__ == "__main__":
    print(f"Database ready: {init_db()}")
