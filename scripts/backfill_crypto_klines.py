"""Backfill Binance Futures 1-minute klines for pair-selection research.

Usage:
    python scripts/backfill_crypto_klines.py --days 30
    python scripts/backfill_crypto_klines.py --days 30 --symbols BTCUSDT ETHUSDT BNBUSDT SOLUSDT DOGEUSDT

The script uses Binance's public USD-M Futures klines endpoint, paginates in
1,000-bar chunks, writes only closed 1-minute candles, and upserts them into
the existing SQLite resampled_data table. It does not touch tick_data.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.database_setup import DB_PATH, init_db

BASE_URL = "https://fapi.binance.com/fapi/v1/klines"
INTERVAL = "1m"
LIMIT = 1000
DEFAULT_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "DOGEUSDT",
    "XRPUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT",
]
REQUEST_TIMEOUT = 20


def fetch_klines(symbol: str, start_ms: int, end_ms: int) -> list[list]:
    rows: list[list] = []
    cursor = start_ms
    session = requests.Session()

    while cursor < end_ms:
        params = {
            "symbol": symbol,
            "interval": INTERVAL,
            "startTime": cursor,
            "endTime": end_ms,
            "limit": LIMIT,
        }
        response = session.get(BASE_URL, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break

        rows.extend(batch)
        last_open = int(batch[-1][0])
        next_cursor = last_open + 60_000
        if next_cursor <= cursor:
            break
        cursor = next_cursor

        if len(batch) < LIMIT:
            break
        time.sleep(0.05)

    return rows


def normalize_klines(rows: list[list], symbol: str) -> pd.DataFrame:
    columns = [
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_buy_base",
        "taker_buy_quote", "ignore",
    ]
    if not rows:
        return pd.DataFrame(columns=["symbol", "interval", "timestamp", "open", "high", "low", "close", "volume"])

    df = pd.DataFrame(rows, columns=columns)
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["symbol"] = symbol.upper()
    df["interval"] = INTERVAL
    return df[["symbol", "interval", "timestamp", "open", "high", "low", "close", "volume"]].dropna()


def upsert_dataframe(df: pd.DataFrame, db_path=DB_PATH) -> int:
    if df.empty:
        return 0
    init_db(db_path)
    import sqlite3

    with sqlite3.connect(str(db_path), timeout=30) as conn:
        # Research backfill databases are expected to contain unique candle
        # keys. Fail clearly if a legacy database contains duplicate keys
        # rather than silently corrupting historical observations.
        duplicate_count = conn.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT symbol, interval, timestamp
                FROM resampled_data
                GROUP BY symbol, interval, timestamp
                HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]
        if duplicate_count:
            raise RuntimeError(
                "resampled_data contains duplicate candle keys; clean those "
                "duplicates before running the historical backfill."
            )

        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_resampled_symbol_interval_timestamp "
            "ON resampled_data(symbol, interval, timestamp)"
        )
        rows = list(df.itertuples(index=False, name=None))
        conn.executemany(
            """
            INSERT INTO resampled_data(symbol, interval, timestamp, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, interval, timestamp) DO UPDATE SET
                open=excluded.open,
                high=excluded.high,
                low=excluded.low,
                close=excluded.close,
                volume=excluded.volume
            """,
            rows,
        )
        conn.commit()
    return len(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    parser.add_argument("--end", default=None, help="UTC end timestamp, e.g. 2026-08-13T00:00:00Z")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.days <= 0:
        raise SystemExit("--days must be positive")

    end = pd.Timestamp.now(tz="UTC").floor("min")
    if args.end:
        end = pd.Timestamp(args.end)
        if end.tzinfo is None:
            end = end.tz_localize("UTC")
        else:
            end = end.tz_convert("UTC")
        end = end.floor("min")

    start = end - pd.Timedelta(days=args.days)

    print("=" * 70)
    print("BINANCE 1-MINUTE HISTORICAL BACKFILL")
    print("=" * 70)
    print("Database:", DB_PATH)
    print("Range:", start, "->", end)
    print("Symbols:", ", ".join(s.upper() for s in args.symbols))

    total = 0
    for symbol in [s.upper() for s in args.symbols]:
        print(f"\n{symbol}: downloading...")
        rows = fetch_klines(symbol, int(start.timestamp() * 1000), int(end.timestamp() * 1000))
        df = normalize_klines(rows, symbol)
        written = upsert_dataframe(df)
        total += written
        print(f"{symbol}: {len(df)} candles fetched, {written} rows upserted")
        if not df.empty:
            print(f"  {df['timestamp'].min()} -> {df['timestamp'].max()}")

    print("\nTotal rows upserted:", total)
    print("Backfill complete.")


if __name__ == "__main__":
    main()
