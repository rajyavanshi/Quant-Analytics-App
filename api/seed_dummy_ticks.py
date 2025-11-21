import sqlite3, os, pandas as pd
from datetime import datetime, timedelta
import numpy as np

DB_PATH = os.path.join("..", "database", "quant_data.db")
conn = sqlite3.connect(DB_PATH)

times = [datetime.now() - timedelta(seconds=i*30) for i in range(200)]
btc = np.linspace(67000, 67300, 200) + np.random.randn(200)*40
eth = np.linspace(3500, 3520, 200) + np.random.randn(200)*3
vol_btc = np.random.randint(50, 500, size=200)
vol_eth = np.random.randint(20, 300, size=200)

btc_df = pd.DataFrame({
    "symbol": "BTCUSDT",  # uppercase key
    "timestamp": times,
    "price": btc,
    "volume": vol_btc
})
eth_df = pd.DataFrame({
    "symbol": "ETHUSDT",  # uppercase key
    "timestamp": times,
    "price": eth,
    "volume": vol_eth
})

# clear old tick_data to avoid duplicates
conn.execute("DELETE FROM tick_data WHERE symbol IN ('BTCUSDT','ETHUSDT');")
conn.commit()

df = pd.concat([btc_df, eth_df])
df.to_sql("tick_data", conn, if_exists="append", index=False)

conn.close()
print("✅ Reinserted BTCUSDT + ETHUSDT data in uppercase")
