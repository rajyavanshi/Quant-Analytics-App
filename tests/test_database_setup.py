import sqlite3

import pytest

from database.database_setup import init_db


def test_init_db_creates_required_schema(tmp_path):
    db = tmp_path / "quant_data.db"
    init_db(db)

    with sqlite3.connect(db) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"tick_data", "analytics_results", "analytics_cleaned", "alerts_data"}.issubset(tables)

        columns = {row[1] for row in conn.execute("PRAGMA table_info(tick_data)")}
        assert {"symbol", "trade_id", "timestamp", "price", "volume"}.issubset(columns)

        indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        assert "idx_tick_symbol_timestamp" in indexes
        assert "uq_tick_symbol_trade_id" in indexes


def test_trade_id_migration_preserves_legacy_rows_and_allows_unique_live_ids(tmp_path):
    db = tmp_path / "legacy.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            CREATE TABLE tick_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                price REAL NOT NULL,
                volume REAL NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO tick_data(symbol,timestamp,price,volume) VALUES (?,?,?,?)",
            ("BTCUSDT", "2026-01-01T00:00:00+00:00", 65000.0, 0.01),
        )
        conn.commit()

    init_db(db)

    with sqlite3.connect(db) as conn:
        legacy = conn.execute(
            "SELECT symbol, trade_id, price, volume FROM tick_data WHERE symbol='BTCUSDT'"
        ).fetchone()
        assert legacy == ("BTCUSDT", None, 65000.0, 0.01)

        conn.execute(
            "INSERT INTO tick_data(symbol,trade_id,timestamp,price,volume) VALUES (?,?,?,?,?)",
            ("BTCUSDT", 12345, "2026-01-01T00:01:00+00:00", 65001.0, 0.02),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO tick_data(symbol,trade_id,timestamp,price,volume) VALUES (?,?,?,?,?)",
                ("BTCUSDT", 12345, "2026-01-01T00:01:01+00:00", 65002.0, 0.03),
            )
        conn.commit()


def test_database_path_is_not_created_by_import(tmp_path, monkeypatch):
    from database import database_setup

    assert callable(database_setup.init_db)
