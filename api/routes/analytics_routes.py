"""Analytics API routes with strict parameter validation."""

from __future__ import annotations

import sqlite3

import pandas as pd
from flask import Blueprint, jsonify, request

from api.analytics_engine_from_ticks import compute_analytics_for_pair
from backend.analytics_engine import run_full_analytics
from api.db_pair_prices import parse_pair
from database.database_setup import DB_PATH, init_db

analytics_bp = Blueprint("analytics_bp", __name__, url_prefix="/api/analytics")


def _limit(default=500, maximum=5000) -> int:
    value = request.args.get("limit", default=default, type=int)
    if value is None or not 1 <= value <= maximum:
        raise ValueError(f"limit must be between 1 and {maximum}")
    return value


def _window(default=100, maximum=1000) -> int:
    value = request.args.get("window", default=default, type=int)
    if value is None or not 3 <= value <= maximum:
        raise ValueError(f"window must be between 3 and {maximum}")
    return value


def _serialize(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []
    out = df.copy()
    if "timestamp" in out.columns:
        out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce").astype(str)
    return out.where(pd.notna(out), None).to_dict(orient="records")


@analytics_bp.get("/recent")
def get_recent_analytics():
    symbol_pair = request.args.get("symbol_pair") or request.args.get("symbol") or request.args.get("pair")
    if not symbol_pair:
        return jsonify({"status": "error", "message": "Missing 'symbol_pair' parameter", "data": []}), 400

    try:
        limit = _limit()
        window = _window()
        if "_" in symbol_pair:
            df = compute_analytics_for_pair(symbol_pair, window=window, limit=limit)
        else:
            init_db()
            with sqlite3.connect(str(DB_PATH)) as conn:
                df = pd.read_sql_query(
                    "SELECT timestamp, price, volume FROM tick_data WHERE UPPER(symbol)=? ORDER BY timestamp DESC LIMIT ?",
                    conn,
                    params=(symbol_pair.upper(), limit),
                )
            if not df.empty:
                df = df.sort_values("timestamp")
                df["price"] = pd.to_numeric(df["price"], errors="coerce")
                df["rolling_mean"] = df["price"].rolling(window, min_periods=max(3, window // 4)).mean()
                df["rolling_std"] = df["price"].rolling(window, min_periods=max(3, window // 4)).std()
                df["zscore"] = (df["price"] - df["rolling_mean"]) / df["rolling_std"]

        if df.empty:
            return jsonify({"status": "warning", "message": f"No data found for {symbol_pair}", "data": []}), 404

        return jsonify({
            "status": "success",
            "message": "Computed analytics successfully",
            "symbol_pair": symbol_pair.upper(),
            "mode": "pair" if "_" in symbol_pair else "single",
            "count": len(df),
            "data": _serialize(df),
        })
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc), "data": []}), 400
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc), "data": []}), 500


@analytics_bp.get("/latest")
def get_latest_analytics():
    symbol_pair = request.args.get("symbol_pair", "BTCUSDT_ETHUSDT").upper()
    try:
        window = _window(default=60)
        limit = _limit(500)
        symbol_x, symbol_y = parse_pair(symbol_pair)
        result = run_full_analytics(
            symbol_x=symbol_x,
            symbol_y=symbol_y,
            timeframe="1min",
            lookback_minutes=max(120, window * 2),
            zscore_window=window,
        )
        if result["df"].empty:
            return jsonify({"status": "warning", "message": f"No analytics found for {symbol_pair}", "data": None}), 404

        # Return the canonical summary so the latest endpoint does not expose
        # an all-NaN tail merely because the requested rolling window exceeds
        # the amount of currently accumulated live data.
        data = dict(result["results"])
        data["timestamp"] = result["df"].index[-1].isoformat()
        data["count"] = min(len(result["df"]), limit)
        return jsonify({
            "status": "success",
            "message": "Latest analytics returned",
            "symbol_pair": symbol_pair,
            "data": _serialize(pd.DataFrame([data]))[0],
        })
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc), "data": None}), 400
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc), "data": None}), 500


@analytics_bp.get("/cleaned")
def get_cleaned_analytics():
    symbol_pair = request.args.get("symbol_pair", request.args.get("symbol", "BTCUSDT_ETHUSDT")).upper()
    try:
        limit = _limit(200)
        init_db()
        with sqlite3.connect(str(DB_PATH)) as conn:
            df = pd.read_sql_query(
                "SELECT * FROM analytics_cleaned WHERE pair_symbol=? ORDER BY timestamp DESC LIMIT ?",
                conn,
                params=(symbol_pair, limit),
            )
        return jsonify({"status": "success", "count": len(df), "data": _serialize(df)})
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc), "data": []}), 400
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc), "data": []}), 500
