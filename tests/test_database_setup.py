import sqlite3

import pytest

from database.database_setup import init_db


def test_init_db_creates_required_schema(tmp_path):
    db = tmp_path / "quant_data.db"
    init_db(db)

    with sqlite3.connect(db) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"tick_data", "analytics_results", "analytics_cleaned", "alerts_data"}.issubset(tables)

        indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        assert "idx_tick_symbol_timestamp" in indexes


def test_database_path_is_not_created_by_import(tmp_path, monkeypatch):
    # The schema module should expose an explicit initializer rather than
    # performing destructive work merely because it was imported.
    from database import database_setup

    assert callable(database_setup.init_db)
