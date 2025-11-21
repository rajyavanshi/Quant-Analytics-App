# test_db_connection.py
from db_connection import get_db_session
from database_setup import TickData
from datetime import datetime

session = get_db_session()

# Insert a sample tick
sample_tick = TickData(
    symbol="BTCUSDT",
    timestamp=datetime.utcnow(),
    price=67000.25,
    volume=0.1234
)

session.add(sample_tick)
session.commit()

# Query back
result = session.query(TickData).all()
for row in result:
    print(row.id, row.symbol, row.price, row.timestamp)
