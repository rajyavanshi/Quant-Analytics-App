# =====================================================
# File: api/routes/alert_routes.py
# Purpose: Expose generated trading alerts via Flask API (DB-backed)
# Author: Suraj Prakash (Quant Developer)
# =====================================================

from flask import Blueprint, jsonify, request
import pandas as pd
import sqlite3
import os
import logging

# -------------------------------------------------------
# 1️⃣ Create Flask Blueprint
# -------------------------------------------------------
alert_bp = Blueprint("alert_bp", __name__, url_prefix="/api/alerts")

# -------------------------------------------------------
# 2️⃣ Database connection helper
# -------------------------------------------------------
DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "database", "quant_data.db"
)

def get_db_connection():
    """Establish SQLite connection safely."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logging.error(f"DB connection failed: {e}")
        raise


# -------------------------------------------------------
# 3️⃣ Endpoint: /api/alerts/latest
# -------------------------------------------------------
@alert_bp.route("/latest", methods=["GET"])
def get_latest_alert():
    """
    Returns the most recent alert entry.
    Example: /api/alerts/latest
    """
    try:
        conn = get_db_connection()
        query = """
            SELECT * FROM alerts_data
            ORDER BY timestamp DESC
            LIMIT 1;
        """
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            msg = "No alerts available in the database."
            logging.warning(msg)
            return jsonify({"status": "error", "message": msg, "data": None}), 404

        latest_alert = df.to_dict(orient="records")[0]
        logging.info("Fetched latest alert from DB successfully.")

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Fetched latest alert.",
                    "count": 1,
                    "data": latest_alert,
                }
            ),
            200,
        )

    except Exception as e:
        msg = f"Error fetching latest alert: {str(e)}"
        logging.error(msg)
        return jsonify({"status": "error", "message": msg, "data": None}), 500


# -------------------------------------------------------
# 4️⃣ Endpoint: /api/alerts/recent
# -------------------------------------------------------
@alert_bp.route("/recent", methods=["GET"])
def get_recent_alerts():
    """
    Returns last N alerts (default = 10).
    Example: /api/alerts/recent?limit=20
    """
    try:
        limit = int(request.args.get("limit", 10))
        if limit <= 0:
            return (
                jsonify(
                    {"status": "error", "message": "Limit must be positive.", "data": []}
                ),
                400,
            )
        if limit > 500:
            limit = 500

        conn = get_db_connection()
        query = f"""
            SELECT * FROM alerts_data
            ORDER BY timestamp DESC
            LIMIT {limit};
        """
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            msg = "No alert records available in the database."
            logging.warning(msg)
            return jsonify({"status": "error", "message": msg, "data": []}), 404

        # Sort chronologically for front-end charting clarity
        if "timestamp" in df.columns:
            df = df.sort_values(by="timestamp").reset_index(drop=True)

        logging.info(f"Fetched {len(df)} recent alerts from DB.")
        return (
            jsonify(
                {
                    "status": "success",
                    "message": f"Fetched {len(df)} alerts successfully.",
                    "count": len(df),
                    "limit": limit,
                    "data": df.to_dict(orient="records"),
                }
            ),
            200,
        )

    except Exception as e:
        msg = f"Error fetching recent alerts: {str(e)}"
        logging.error(msg)
        return jsonify({"status": "error", "message": msg, "data": []}), 500


# -------------------------------------------------------
# 5️⃣ Endpoint: /api/alerts/stats
# -------------------------------------------------------
@alert_bp.route("/stats", methods=["GET"])
def get_alert_stats():
    """
    Returns summary statistics of alert signals.
    Example response:
    {
        "TOTAL": 132,
        "LONG": 70,
        "SHORT": 62
    }
    """
    try:
        conn = get_db_connection()
        query = """
            SELECT signal, COUNT(*) AS count
            FROM alerts_data
            GROUP BY signal;
        """
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            msg = "No alert statistics available."
            logging.warning(msg)
            return jsonify({"status": "error", "message": msg, "data": {}}), 404

        stats = {row["signal"]: int(row["count"]) for _, row in df.iterrows()}
        stats["TOTAL"] = int(df["count"].sum())

        logging.info("Fetched alert statistics successfully.")
        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Fetched alert summary stats.",
                    "data": stats,
                }
            ),
            200,
        )

    except Exception as e:
        msg = f"Error fetching alert statistics: {str(e)}"
        logging.error(msg)
        return jsonify({"status": "error", "message": msg, "data": {}}), 500
