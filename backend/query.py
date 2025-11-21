# Test queries to verify data ingestion


import sqlite3, pandas as pd

path = r"D:\Quant Analytics App\database\quant_data.db"
conn = sqlite3.connect(path)
print("Tables:", pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table'", conn))

# Quick look at latest 5 rows
df = pd.read_sql_query("SELECT * FROM tick_data ORDER BY timestamp DESC LIMIT 5", conn)
print(df)
conn.close()

print("\n---\n")
import sqlite3, pandas as pd
path = r"D:\Quant Analytics App\database\quant_data.db"
conn = sqlite3.connect(path)
df = pd.read_sql_query("""
SELECT symbol, MIN(timestamp) as first, MAX(timestamp) as last, COUNT(*) as n
FROM tick_data
WHERE symbol IN ('BTCUSDT','ETHUSDT')
GROUP BY symbol;
""", conn)
print(df)
conn.close()
