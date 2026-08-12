"""Scan historical 1-minute crypto candles for statistically suitable pairs.

The scanner deliberately does not backtest a trading rule. It ranks candidate
pairs using independent statistical diagnostics: return correlation,
log-price cointegration residual ADF, half-life, and rolling hedge-ratio
stability. Only the longest contiguous segment is used for each pair.

Usage:
    python scripts/scan_crypto_pairs.py
    python scripts/scan_crypto_pairs.py --symbols BTCUSDT ETHUSDT BNBUSDT SOLUSDT DOGEUSDT --min-bars 500
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.pair_selection import generate_pair_list, screen_pair
from database.database_setup import DB_PATH, init_db

DEFAULT_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "DOGEUSDT",
    "XRPUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT",
]


def load_candles(symbols: list[str], db_path=DB_PATH) -> pd.DataFrame:
    init_db(db_path)
    placeholders = ",".join("?" for _ in symbols)
    with sqlite3.connect(str(db_path)) as conn:
        query = f"""
            SELECT symbol, timestamp, close
            FROM resampled_data
            WHERE interval = '1m'
              AND symbol IN ({placeholders})
            ORDER BY timestamp
        """
        df = pd.read_sql_query(query, conn, params=[s.upper() for s in symbols])

    if df.empty:
        return df

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, format="mixed")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df["symbol"] = df["symbol"].str.upper()
    df = df.dropna(subset=["timestamp", "close"])
    return df.pivot_table(index="timestamp", columns="symbol", values="close", aggfunc="last").sort_index()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    parser.add_argument("--min-bars", type=int, default=500)
    parser.add_argument("--min-correlation", type=float, default=0.70)
    parser.add_argument("--max-adf-pvalue", type=float, default=0.05)
    parser.add_argument("--min-half-life", type=float, default=1.0)
    parser.add_argument("--max-half-life", type=float, default=120.0)
    parser.add_argument("--beta-window", type=int, default=120)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    symbols = sorted({s.upper() for s in args.symbols})
    prices = load_candles(symbols)

    print("=" * 78)
    print("CRYPTO PAIR STATISTICAL SCREEN")
    print("=" * 78)
    print("Symbols:", ", ".join(symbols))
    print("1-minute rows:", len(prices))
    print("Range:", prices.index.min(), "->", prices.index.max())
    print("Minimum contiguous bars:", args.min_bars)
    print("Return-correlation threshold:", args.min_correlation)
    print("ADF p-value threshold:", args.max_adf_pvalue)
    print("Half-life range:", args.min_half_life, "->", args.max_half_life, "minutes")

    results = []
    pairs = generate_pair_list(symbols)

    for x, y in pairs:
        if x not in prices.columns or y not in prices.columns:
            continue
        pair = prices[[x, y]].dropna()
        result = screen_pair(
            pair,
            x,
            y,
            timeframe="1min",
            min_bars=args.min_bars,
            min_correlation=args.min_correlation,
            max_adf_pvalue=args.max_adf_pvalue,
            min_half_life=args.min_half_life,
            max_half_life=args.max_half_life,
            beta_window=args.beta_window,
        )
        results.append(result)

    if not results:
        raise SystemExit("No candidate pairs could be evaluated.")

    df = pd.DataFrame(results).sort_values(
        ["eligible", "score", "correlation"],
        ascending=[False, False, False],
    )

    display = [
        "symbol_x", "symbol_y", "bars", "correlation", "beta",
        "adf_pvalue", "half_life_minutes", "beta_mean", "beta_std",
        "beta_cv", "eligible", "score", "reason",
    ]

    print("\nALL PAIRS")
    print(df[display].to_string(index=False, float_format=lambda x: f"{x:.6f}"))

    eligible = df[df["eligible"]].copy()
    print("\n" + "=" * 78)
    print("ELIGIBLE CANDIDATES")
    print("=" * 78)
    if eligible.empty:
        print("No pairs passed the statistical filters.")
    else:
        print(eligible[display].to_string(index=False, float_format=lambda x: f"{x:.6f}"))

    output_dir = PROJECT_ROOT / "results" / "pair_selection"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "pair_screen_results.csv"
    df.to_csv(path, index=False)
    print("\nSaved:", path)


if __name__ == "__main__":
    main()
