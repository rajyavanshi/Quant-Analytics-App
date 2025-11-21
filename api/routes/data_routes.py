# =====================================================
# File: api/routes/data_routes.py
# Purpose: Provide tick and symbol data from SQLite DB
# Author: Suraj Prakash (Quant Developer)
# =====================================================

from flask import Blueprint, jsonify, request
import sqlite3
import os
import pandas as pd
import logging

# -------------------------------------------------------
# 1️⃣ Create Flask Blueprint
# -------------------------------------------------------
data_bp = Blueprint("data_bp", __name__, url_prefix="/api/data")

# -------------------------------------------------------
# 2️⃣ Database connection helper
# -------------------------------------------------------
DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "database", "quant_data.db"
)

def get_db_connection():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn, None
    except Exception as e:
        logging.error(f"DB connection failed: {str(e)}")
        return None, str(e)


# -------------------------------------------------------
# 3️⃣ Endpoint: /api/data/symbols
# -------------------------------------------------------
@data_bp.route("/symbols", methods=["GET"])
def get_symbols():
    conn, err = get_db_connection()
    if err:
        return jsonify({"status": "error", "message": err}), 500

    try:
        query = "SELECT DISTINCT symbol FROM tick_data ORDER BY symbol;"
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            msg = "No symbols found in tick_data table."
            logging.warning(msg)
            return jsonify({"status": "error", "message": msg, "data": []}), 404

        symbols = df["symbol"].dropna().tolist()
        logging.info(f"Fetched {len(symbols)} symbols successfully.")
        return jsonify({"status": "success", "count": len(symbols), "data": symbols}), 200

    except Exception as e:
        logging.error(f"Error fetching symbols: {str(e)}")
        return jsonify({"status": "error", "message": str(e), "data": []}), 500


# -------------------------------------------------------
# 4️⃣ Endpoint: /api/data/recent_ticks
# -------------------------------------------------------
@data_bp.route("/recent_ticks", methods=["GET"])
def get_recent_ticks():
    symbol = request.args.get("symbol")
    limit = request.args.get("limit", default=10, type=int)

    if not symbol:
        return jsonify({"status": "error", "message": "Missing required parameter 'symbol'"}), 400
    if limit <= 0:
        return jsonify({"status": "error", "message": "Limit must be positive."}), 400
    if limit > 1000:
        limit = 1000

    conn, err = get_db_connection()
    if err:
        return jsonify({"status": "error", "message": err}), 500

    try:
        query = """
            SELECT timestamp, price, volume
            FROM tick_data
            WHERE symbol = ?
            ORDER BY timestamp DESC
            LIMIT ?;
        """
        df = pd.read_sql_query(query, conn, params=(symbol, limit))
        conn.close()

        if df.empty:
            msg = f"No tick data found for symbol '{symbol}'."
            logging.warning(msg)
            return jsonify({"status": "error", "message": msg, "data": []}), 404

        df = df.iloc[::-1].reset_index(drop=True)
        df["timestamp"] = df["timestamp"].astype(str)

        logging.info(f"Fetched {len(df)} recent ticks for {symbol}.")
        return jsonify({
            "status": "success",
            "symbol": symbol,
            "count": len(df),
            "limit": limit,
            "data": df.to_dict(orient="records"),
        }), 200

    except Exception as e:
        logging.error(f"Error fetching recent ticks: {str(e)}")
        return jsonify({"status": "error", "message": str(e), "data": []}), 500


# -------------------------------------------------------
# 5️⃣ Endpoint: /api/data/volume_summary
# -------------------------------------------------------
@data_bp.route("/volume_summary", methods=["GET"])
def get_volume_summary():
    conn, err = get_db_connection()
    if err:
        return jsonify({"status": "error", "message": err}), 500

    try:
        query = """
            SELECT symbol, ROUND(SUM(volume), 2) AS total_volume
            FROM tick_data
            GROUP BY symbol
            ORDER BY total_volume DESC;
        """
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            msg = "No volume data available."
            logging.warning(msg)
            return jsonify({"status": "error", "message": msg, "data": []}), 404

        result = df.to_dict(orient="records")
        logging.info("Fetched volume summary successfully.")
        return jsonify({"status": "success", "count": len(result), "data": result}), 200

    except Exception as e:
        logging.error(f"Error fetching volume summary: {str(e)}")
        return jsonify({"status": "error", "message": str(e), "data": []}), 500


# -------------------------------------------------------
# 6️⃣ Debug Route — Pair Health Check
# -------------------------------------------------------
@data_bp.route("/debug_pairs", methods=["GET"])
def debug_pairs():
    """
    Shows all symbols in tick_data and detects missing pair legs.
    """
    try:
        conn, err = get_db_connection()
        if err:
            return jsonify({"status": "error", "message": err}), 500

        df = pd.read_sql_query("SELECT symbol, COUNT(*) AS n FROM tick_data GROUP BY symbol ORDER BY symbol;", conn)
        conn.close()

        if df.empty:
            return jsonify({
                "status": "warning",
                "message": "No tick data found in database.",
                "symbols": []
            }), 200

        pairs = ["BTCUSDT_ETHUSDT", "BNBUSDT_ETHUSDT", "BTCUSDT_BNBUSDT"]
        missing = [p for p in pairs if any(x not in df["symbol"].values for x in p.split("_"))]

        return jsonify({
            "status": "success",
            "symbols": df.to_dict(orient="records"),
            "missing_pairs": missing,
            "message": "Symbol health check complete."
        }), 200

    except Exception as e:
        logging.exception("Error in debug_pairs")
        return jsonify({"status": "error", "message": str(e)}), 500
