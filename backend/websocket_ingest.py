"""Binance Futures trade ingestion with buffered SQLite writes and reconnects."""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path

import websocket

from database.database_setup import DB_PATH, init_db

logger = logging.getLogger(__name__)

BATCH_SIZE = max(10, int(os.getenv("WS_BATCH_SIZE", "100")))
FLUSH_INTERVAL = max(0.25, float(os.getenv("WS_FLUSH_INTERVAL_SECONDS", "3")))
MAX_BACKOFF = max(5, int(os.getenv("WS_MAX_RECONNECT_SECONDS", "60")))
BUFFER = []
BUFFER_LOCK = threading.Lock()
STOP_EVENT = threading.Event()
LAST_TICK_TIME = None
MESSAGE_COUNT = 0
INSERTED_COUNT = 0
RECONNECT_COUNT = 0


def get_db_connection() -> sqlite3.Connection:
    init_db()
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def flush_buffer() -> int:
    """Atomically detach the in-memory batch, then write it to SQLite."""
    global INSERTED_COUNT
    with BUFFER_LOCK:
        if not BUFFER:
            return 0
        batch = BUFFER[:]
        del BUFFER[:]

    try:
        with get_db_connection() as conn:
            conn.executemany(
                "INSERT INTO tick_data (symbol, timestamp, price, volume) VALUES (?, ?, ?, ?)",
                batch,
            )
            conn.commit()
        INSERTED_COUNT += len(batch)
        logger.info("Flushed %d ticks to database", len(batch))
        return len(batch)
    except Exception:
        # Put the batch back at the front so a transient DB error does not lose data.
        with BUFFER_LOCK:
            BUFFER[0:0] = batch
        logger.exception("Tick buffer flush failed; batch restored")
        return 0


def _flush_worker() -> None:
    while not STOP_EVENT.wait(FLUSH_INTERVAL):
        flush_buffer()


def normalize_trade(data: dict):
    """Normalize Binance trade payload into a database row."""
    try:
        required = ("s", "T", "p", "q")
        if not all(key in data for key in required):
            logger.warning("Skipping incomplete trade payload")
            return None

        symbol = str(data["s"]).upper()
        timestamp = dt.datetime.fromtimestamp(int(data["T"]) / 1000, tz=dt.timezone.utc)
        price = float(data["p"])
        volume = float(data["q"])

        if not symbol or price <= 0 or volume <= 0:
            return None
        return symbol, timestamp.isoformat(), price, volume
    except (TypeError, ValueError, OverflowError):
        logger.exception("Invalid trade payload")
        return None


def insert_tick(symbol, timestamp, price, volume) -> None:
    global LAST_TICK_TIME
    with BUFFER_LOCK:
        BUFFER.append((symbol, timestamp, price, volume))
    LAST_TICK_TIME = time.time()


def on_message(ws, message) -> None:
    global MESSAGE_COUNT
    MESSAGE_COUNT += 1
    try:
        data = json.loads(message)
        if isinstance(data, dict) and "data" in data:
            data = data["data"]
        if isinstance(data, dict) and data.get("e") == "trade":
            parsed = normalize_trade(data)
            if parsed:
                insert_tick(*parsed)
    except Exception:
        logger.exception("WebSocket message handling failed")


def on_error(ws, error) -> None:
    logger.error("WebSocket error: %s", error)


def on_close(ws, close_status_code, close_msg) -> None:
    logger.warning("WebSocket closed: code=%s message=%s", close_status_code, close_msg)


def on_open(ws) -> None:
    logger.info("Binance Futures WebSocket connected")


def _stream_url(symbols: list[str]) -> str:
    streams = "/".join(f"{symbol.lower()}@trade" for symbol in symbols)
    return f"wss://fstream.binance.com/stream?streams={streams}"


def start_stream(symbols: list[str]) -> None:
    """Run the ingestion loop forever, reconnecting with exponential backoff."""
    global RECONNECT_COUNT
    if not symbols:
        raise ValueError("At least one Binance symbol is required")

    init_db()
    threading.Thread(target=_flush_worker, name="tick-flusher", daemon=True).start()
    url = _stream_url(symbols)
    backoff = 1

    while not STOP_EVENT.is_set():
        logger.info("Connecting to Binance stream for %s", ", ".join(symbols))
        ws = websocket.WebSocketApp(
            url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        try:
            ws.run_forever(
                ping_interval=20,
                ping_timeout=10,
                ping_payload="quant-analytics",
            )
        except Exception:
            logger.exception("WebSocket run loop failed")

        if STOP_EVENT.is_set():
            break

        RECONNECT_COUNT += 1
        logger.warning("Reconnecting in %ss (attempt %s)", backoff, RECONNECT_COUNT)
        STOP_EVENT.wait(backoff)
        backoff = min(MAX_BACKOFF, backoff * 2)

    flush_buffer()
    logger.info("WebSocket ingestion stopped")


def stop_stream() -> None:
    STOP_EVENT.set()
    flush_buffer()


def health_snapshot() -> dict:
    age = None if LAST_TICK_TIME is None else max(0.0, time.time() - LAST_TICK_TIME)
    return {
        "message_count": MESSAGE_COUNT,
        "inserted_count": INSERTED_COUNT,
        "buffer_size": len(BUFFER),
        "last_tick_age_seconds": age,
        "reconnect_count": RECONNECT_COUNT,
        "running": not STOP_EVENT.is_set(),
    }


if __name__ == "__main__":
    symbols = [s.strip().lower() for s in os.getenv("BINANCE_SYMBOLS", "btcusdt,ethusdt,bnbusdt,solusdt,dogeusdt").split(",") if s.strip()]
    start_stream(symbols)
