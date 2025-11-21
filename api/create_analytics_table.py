import sqlite3, os

DB_PATH = os.path.join("..", "database", "quant_data.db")
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

conn.commit()
conn.close()
print("✅ analytics_cleaned table created successfully.")
