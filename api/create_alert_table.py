# =====================================================
# File: create_alerts_table.py
# Purpose: Create 'alerts_data' table in main quant_data.db
# Author: Suraj Prakash (Quant Developer)
# =====================================================

import sqlite3
import os

# -----------------------------------------------------
# ✅ Database Path (fixed to your main database)
# -----------------------------------------------------
DB_PATH = r"D:\Quant Analytics App\database\quant_data.db"

# Ensure directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# -----------------------------------------------------
# ✅ Connect and create table
# -----------------------------------------------------
try:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS alerts_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            symbol1 TEXT NOT NULL,
            symbol2 TEXT NOT NULL,
            signal TEXT NOT NULL,
            reason TEXT,
            zscore REAL,
            spread REAL,
            hedge_ratio REAL
        );
    """)

    conn.commit()

    # -------------------------------------------------
    # ✅ Verification — print all tables in the database
    # -------------------------------------------------
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cur.fetchall()]
    print("✅ Table 'alerts_data' created successfully.")
    print("📋 Existing tables in DB:", tables)

except sqlite3.Error as e:
    print(f"❌ SQLite error: {e}")

finally:
    if conn:
        conn.close()
