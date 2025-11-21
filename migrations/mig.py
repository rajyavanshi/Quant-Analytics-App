import os
import sqlite3

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQL_PATH = os.path.join(BASE_DIR, "create_pair_tables.sql")
DB_PATH = "D:/Quant Analytics App/database/quant_data.db"

# Read SQL script
with open(SQL_PATH, "r") as f:
    sql_script = f.read()

# Connect and execute
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

try:
    cur.executescript(sql_script)  # Executes multiple SQL statements
    conn.commit()
    print(" Tables created successfully.")
except Exception as e:
    print(f" Error creating tables: {e}")
finally:
    conn.close()
