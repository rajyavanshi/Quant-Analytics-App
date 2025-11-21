# =====================================================
# File: backend/websocket_ingest.py
# Purpose: Stage 2 — Binance Futures WebSocket → SQLite (tick_data)
# Author: Suraj Prakash | Quant Developer Project
# =====================================================

# =====================================================
# 2.1 — SETUP & DEPENDENCIES
# =====================================================
# Libraries required for:
#   • Live WebSocket streaming (Binance Futures)
#   • JSON parsing and data normalization
#   • SQLite storage and batch insertion
#   • Logging and threading for concurrency
# Database Impact: None — setup only.
# =====================================================

import websocket
import json
import sqlite3
import threading
import datetime
import time
import logging
import os

# =====================================================
# 2.2 — LOGGING CONFIGURATION
# =====================================================
# Purpose:
#   • Logs to both console and file (websocket_ingestion.log)
#   • Tracks all connection, error, and insertion events
# Database Impact: None.
# =====================================================

LOG_DIR = os.path.join(os.path.dirname(__file__), '..', 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'websocket_ingestion.log')

logger = logging.getLogger()
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
console_handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s — %(levelname)s — %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# =====================================================
# 2.3 — DATABASE CONNECTION
# =====================================================
# Purpose:
#   • Connect to SQLite (quant_data.db)
#   • Enable WAL mode for concurrent reads/writes
#   • Used by flusher thread for bulk inserts
# Database Impact:
#   • Opens persistent connection to tick_data
# =====================================================

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'database', 'quant_data.db')

def get_db_connection():
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn
    except Exception as e:
        logging.error(f"Database connection failed: {e}")
        raise

# =====================================================
# 2.4 — BUFFERED WRITE OPTIMIZATION
# =====================================================
# Purpose:
#   • Collect ticks in a memory buffer
#   • Flush to SQLite in batches (100 rows or every 3 seconds)
# Benefits:
#   • 10x faster than single inserts
#   • Avoids database lock errors
# Database Impact:
#   • Inserts multiple tick rows per batch flush
# =====================================================

tick_buffer = []             #  In-memory tick storage
BUFFER_LOCK = threading.Lock()
BATCH_SIZE = 100             # Flush when buffer >= 100 ticks
FLUSH_INTERVAL = 3           # Or flush every 3 seconds

def flush_buffer(conn):
    """
    Background thread: periodically flushes buffered ticks to database.
    """
    while True:
        time.sleep(FLUSH_INTERVAL)
        try:
            BUFFER_LOCK.acquire()
            if len(tick_buffer) > 0:
                batch = tick_buffer.copy()
                tick_buffer.clear()
                BUFFER_LOCK.release()

                cursor = conn.cursor()
                cursor.executemany('''
                    INSERT INTO tick_data (symbol, timestamp, price, volume)
                    VALUES (?, ?, ?, ?)
                ''', batch)
                conn.commit()
                logging.info(f" Flushed {len(batch)} ticks to database.")
            else:
                BUFFER_LOCK.release()
        except Exception as e:
            logging.error(f"Buffer flush failed: {e}")
            BUFFER_LOCK.release()

def insert_tick(symbol, timestamp, price, volume):
    """
    Appends tick to in-memory buffer for batch insertion.
    """
    try:
        BUFFER_LOCK.acquire()
        tick_buffer.append((symbol, timestamp, price, volume))
        BUFFER_LOCK.release()

        # Optional log when buffer fills
        if len(tick_buffer) >= BATCH_SIZE:
            logging.info(f"Buffer reached {BATCH_SIZE} ticks (will flush soon).")
    except Exception as e:
        logging.error(f"Buffer append failed: {e}")
        BUFFER_LOCK.release()

# =====================================================
# 2.5 — PARSE & NORMALIZE TICK DATA
# =====================================================
# Purpose:
#   • Converts Binance JSON → (symbol, timestamp, price, volume)
#   • Ensures valid, positive, consistent trade data
# Database Impact:
#   • Provides clean data for tick_data insertion
# =====================================================

def normalize_trade(json_data):
    """
    Validates and cleans Binance trade JSON.
    Converts timestamp → datetime object.
    Returns tuple (symbol, timestamp, price, volume).
    """
    try:
        required_keys = ['s', 'T', 'p', 'q']
        if not all(k in json_data for k in required_keys):
            logging.warning(f"Skipping incomplete trade: {json_data}")
            return None

        ts = datetime.datetime.utcfromtimestamp(json_data['T'] / 1000.0)
        symbol = json_data['s'].upper()
        price = float(json_data['p'])
        volume = float(json_data['q'])

        if price <= 0 or volume <= 0:
            logging.warning(f"Invalid trade (zero/negative): {symbol}, {price}, {volume}")
            return None

        return symbol, ts, price, volume

    except Exception as e:
        logging.error(f"Normalization failed: {e}")
        return None

# =====================================================
# 2.6 — WEBSOCKET EVENT HANDLERS
# =====================================================
# Purpose:
#   • Handle connection lifecycle: open, message, error, close
#   • Parse each incoming trade → normalize → buffer insert
# Database Impact:
#   • Indirect: tick_buffer grows until flush writes it to DB
# =====================================================

def on_message(ws, message, conn):
    try:
        data = json.loads(message)

        # Handle both single and multi-stream formats
        if 'data' in data:
            data = data['data']

        if data.get("e") == "trade":
            parsed = normalize_trade(data)
            if parsed:
                symbol, ts, price, volume = parsed
                insert_tick(symbol, ts, price, volume)

    except Exception as e:
        logging.error(f"on_message error: {e}")

def on_error(ws, error):
    logging.error(f"WebSocket error: {error}")

def on_close(ws, close_status_code, close_msg):
    logging.warning(f"WebSocket closed (code={close_status_code}, msg={close_msg})")

def on_open(ws):
    logging.info(" WebSocket connection established successfully.")

# =====================================================
# 2.7 — STREAM STARTER (MULTI-SYMBOL SUPPORT)
# =====================================================
# Purpose:
#   • Connect to Binance Futures multi-stream endpoint
#   • Launch threads: WebSocket listener, buffer flusher, heartbeat
# Database Impact:
#   • Continuous tick insertion into tick_data
# =====================================================

def start_stream(symbols):
    conn = get_db_connection()
    base_url = "wss://fstream.binance.com/stream?streams="
    streams = "/".join([f"{sym.lower()}@trade" for sym in symbols])
    socket_url = base_url + streams

    logging.info(f"Connecting to Binance Futures stream → {socket_url}")

    ws = websocket.WebSocketApp(
        socket_url,
        on_open=on_open,
        on_message=lambda ws, msg: on_message(ws, msg, conn),
        on_error=on_error,
        on_close=on_close
    )

    # WebSocket thread (async connection)
    wst = threading.Thread(target=ws.run_forever, kwargs={'ping_interval': 30})
    wst.daemon = True
    wst.start()

    # Background flusher thread
    flush_thread = threading.Thread(target=flush_buffer, args=(conn,))
    flush_thread.daemon = True
    flush_thread.start()

    # Heartbeat thread
    def heartbeat():
        while True:
            logging.info("Listening for trades... (WebSocket active)")
            time.sleep(10)

    hb = threading.Thread(target=heartbeat)
    hb.daemon = True
    hb.start()

    # Main loop — keeps everything alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt — closing WebSocket.")
        ws.close()

        # Final flush on shutdown
        BUFFER_LOCK.acquire()
        if len(tick_buffer) > 0:
            cursor = conn.cursor()
            cursor.executemany('''
                INSERT INTO tick_data (symbol, timestamp, price, volume)
                VALUES (?, ?, ?, ?)
            ''', tick_buffer)
            conn.commit()
            logging.info(f" Final flush: {len(tick_buffer)} ticks saved before exit.")
        BUFFER_LOCK.release()

        conn.close()
        logging.info("WebSocket ingestion stopped gracefully.")

# =====================================================
# 2.8 — ENTRY POINT
# =====================================================
# Purpose:
#   • Defines target symbols for streaming
#   • Starts the entire ingestion pipeline
# =====================================================

if __name__ == "__main__":
    symbols_to_track = ["btcusdt", "ethusdt", "bnbusdt", "solusdt", "dogeusdt"]
    logging.info(" Starting Binance WebSocket ingestion service (Stage 2: Complete)")
    start_stream(symbols_to_track)
