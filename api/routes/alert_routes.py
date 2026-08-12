"""Alert API routes."""

from __future__ import annotations

import sqlite3

import pandas as pd
from flask import Blueprint, jsonify, request

from database.database_setup import DB_PATH, init_db

alert_bp = Blueprint("alert_bp", __name__, url_prefix="/api/alerts")


def _limit(default=10, maximum=500):
    value = request.args.get("limit", default=default, type=int)
    if value is None or not 1 <= value <= maximum:
        raise ValueError(f"limit must be between 1 and {maximum}")
    return value


def _fetch(query, params=()):
    init_db()
    with sqlite3.connect(str(DB_PATH)) as conn:
        return pd.read_sql_query(query, conn, params=params)


@alert_bp.get("/latest")
def get_latest_alert():
    try:
        df = _fetch("SELECT * FROM alerts_data ORDER BY timestamp DESC LIMIT 1")
        if df.empty:
            return jsonify({"status": "warning", "message": "No alerts available", "data": None}), 404
        return jsonify({"status": "success", "count": 1, "data": df.iloc[0].to_dict()})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc), "data": None}), 500


@alert_bp.get("/recent")
def get_recent_alerts():
    try:
        limit = _limit()
        df = _fetch("SELECT * FROM alerts_data ORDER BY timestamp DESC LIMIT ?", (limit,))
        df = df.sort_values("timestamp") if not df.empty else df
        return jsonify({"status": "success", "count": len(df), "limit": limit, "data": df.to_dict(orient="records")})
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc), "data": []}), 400
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc), "data": []}), 500


@alert_bp.get("/stats")
def get_alert_stats():
    try:
        df = _fetch("SELECT signal, COUNT(*) AS count FROM alerts_data GROUP BY signal")
        stats = {row["signal"]: int(row["count"]) for _, row in df.iterrows()}
        stats["TOTAL"] = int(df["count"].sum()) if not df.empty else 0
        return jsonify({"status": "success", "data": stats})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc), "data": {}}), 500
