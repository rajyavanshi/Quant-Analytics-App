"""Market-data API routes."""

from __future__ import annotations

import sqlite3

import pandas as pd
from flask import Blueprint, jsonify, request

from database.database_setup import DB_PATH, init_db

data_bp = Blueprint("data_bp", __name__, url_prefix="/api/data")


def _conn():
    init_db()
    return sqlite3.connect(str(DB_PATH), timeout=30)


def _bounded_limit(default=100, maximum=5000):
    value = request.args.get("limit", default=default, type=int)
    if value is None or not 1 <= value <= maximum:
        raise ValueError(f"limit must be between 1 and {maximum}")
    return value


@data_bp.get("/symbols")
def get_symbols():
    try:
        with _conn() as conn:
            rows = conn.execute("SELECT DISTINCT UPPER(symbol) FROM tick_data ORDER BY 1").fetchall()
        symbols = [row[0] for row in rows if row[0]]
        return jsonify({"status": "success", "count": len(symbols), "data": symbols})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc), "data": []}), 500


@data_bp.get("/pairs")
def get_pairs():
    try:
        with _conn() as conn:
            rows = conn.execute("SELECT DISTINCT UPPER(symbol) FROM tick_data ORDER BY 1").fetchall()
        symbols = [row[0] for row in rows if row[0]]
        pairs = [f"{a}_{b}" for i, a in enumerate(symbols) for b in symbols[i + 1 :]]
        return jsonify({"status": "success", "count": len(pairs), "data": pairs})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc), "data": []}), 500


@data_bp.get("/recent_ticks")
def get_recent_ticks():
    symbol = request.args.get("symbol", "").strip().upper()
    if not symbol:
        return jsonify({"status": "error", "message": "Missing required parameter 'symbol'", "data": []}), 400
    try:
        limit = _bounded_limit(100, 5000)
        with _conn() as conn:
            df = pd.read_sql_query(
                "SELECT timestamp, price, volume FROM tick_data WHERE UPPER(symbol)=? ORDER BY timestamp DESC LIMIT ?",
                conn,
                params=(symbol, limit),
            )
        if df.empty:
            return jsonify({"status": "warning", "message": f"No tick data found for {symbol}", "data": []}), 404
        df = df.iloc[::-1].reset_index(drop=True)
        df["timestamp"] = df["timestamp"].astype(str)
        return jsonify({"status": "success", "symbol": symbol, "count": len(df), "data": df.to_dict(orient="records")})
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc), "data": []}), 400
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc), "data": []}), 500


@data_bp.get("/volume_summary")
def get_volume_summary():
    try:
        with _conn() as conn:
            df = pd.read_sql_query(
                "SELECT UPPER(symbol) AS symbol, ROUND(SUM(volume), 2) AS total_volume FROM tick_data GROUP BY UPPER(symbol) ORDER BY total_volume DESC",
                conn,
            )
        return jsonify({"status": "success", "count": len(df), "data": df.to_dict(orient="records")})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc), "data": []}), 500


@data_bp.get("/debug_pairs")
def debug_pairs():
    try:
        with _conn() as conn:
            df = pd.read_sql_query(
                "SELECT UPPER(symbol) AS symbol, COUNT(*) AS n FROM tick_data GROUP BY UPPER(symbol) ORDER BY symbol",
                conn,
            )
        symbols = set(df["symbol"].tolist()) if not df.empty else set()
        pairs = ["BTCUSDT_ETHUSDT", "BNBUSDT_ETHUSDT", "BTCUSDT_BNBUSDT"]
        missing = [pair for pair in pairs if not all(s in symbols for s in pair.split("_"))]
        return jsonify({"status": "success", "symbols": df.to_dict(orient="records"), "missing_pairs": missing})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500
