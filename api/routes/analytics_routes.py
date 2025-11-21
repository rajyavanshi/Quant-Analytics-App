# =====================================================
# File: api/routes/analytics_routes.py
# Purpose: Expose analytics data directly from DB or computed from tick data
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
analytics_bp = Blueprint("analytics_bp", __name__, url_prefix="/api/analytics")

# -------------------------------------------------------
# 2️⃣ Database connection helper
# -------------------------------------------------------
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "database", "quant_data.db")

def get_db_connection():
    """Establish SQLite connection with dict-like row access."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logging.error(f"DB connection failed: {e}")
        raise

# -------------------------------------------------------
# 💾 Helper: Save cleaned analytics to DB
# -------------------------------------------------------
def save_cleaned_analytics(df: pd.DataFrame, pair_symbol: str):
    """Insert cleaned analytics data into analytics_cleaned table."""
    if df is None or df.empty:
        logging.warning(f"[DB] Skipped saving analytics for {pair_symbol} — empty DataFrame.")
        return

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # ensure table exists
        cur.execute("""
        CREATE TABLE IF NOT EXISTS analytics_cleaned (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair_symbol TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            hedge_ratio REAL,
            zscore REAL,
            adf_pvalue REAL,
            rolling_corr REAL,
            spread REAL,
            mean_spread REAL,
            std_spread REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # avoid duplicates
        existing_ts = set(
            r[0]
            for r in cur.execute(
                "SELECT timestamp FROM analytics_cleaned WHERE pair_symbol=?",
                (pair_symbol,)
            ).fetchall()
        )

        new_rows = df[~df["timestamp"].astype(str).isin(existing_ts)]
        if new_rows.empty:
            logging.info(f"[DB] No new records to insert for {pair_symbol}.")
            conn.close()
            return

        new_rows["pair_symbol"] = pair_symbol
        cols = [
            "pair_symbol", "timestamp", "hedge_ratio",
            "zscore", "adf_pvalue", "rolling_corr",
            "spread", "mean_spread", "std_spread"
        ]
        new_rows = new_rows.reindex(columns=cols, fill_value=None)
        new_rows.to_sql("analytics_cleaned", conn, if_exists="append", index=False)

        conn.commit()
        conn.close()
        logging.info(f"[DB] ✅ Saved {len(new_rows)} cleaned analytics rows for {pair_symbol}.")

    except Exception as e:
        logging.exception(f"[DB] Error saving analytics for {pair_symbol}: {e}")


# -------------------------------------------------------
# 3️⃣ Imports for Pair Analytics
# -------------------------------------------------------
from api.db_pair_prices import get_conn
from api.analytics_engine_from_ticks import compute_analytics_for_pair


# -------------------------------------------------------
# 4️⃣ Endpoint: /api/analytics/recent
# -------------------------------------------------------
@analytics_bp.route('/recent', methods=['GET'])
def get_recent_analytics():
    symbol_pair = request.args.get('symbol_pair') or request.args.get('symbol') or request.args.get('pair')
    if not symbol_pair:
        return jsonify({"status": "error", "message": "Missing 'symbol_pair' parameter"}), 400

    limit = int(request.args.get("limit", 500))
    window = int(request.args.get("window", 100))
    logging.info(f"[Analytics Route] Request received for {symbol_pair} (limit={limit}, window={window})")

    try:
        if '_' in symbol_pair:  # Pair mode
            df = compute_analytics_for_pair(symbol_pair, window=window, limit=limit)
            if df.empty:
                return jsonify({
                    "status": "error",
                    "message": f"No pair price data found for {symbol_pair}",
                    "data": []
                }), 404
        else:  # Single symbol mode
            conn = get_conn()
            q = """
                SELECT timestamp, price
                FROM tick_data
                WHERE UPPER(symbol) = ?
                ORDER BY timestamp DESC
                LIMIT ?;
            """
            df = pd.read_sql_query(q, conn, params=(symbol_pair.upper(), limit))
            conn.close()

            if df.empty:
                return jsonify({
                    "status": "error",
                    "message": f"No tick data found for symbol {symbol_pair}",
                    "data": []
                }), 404

            df = df.sort_values(by="timestamp")
            df["rolling_mean"] = df["price"].rolling(window, min_periods=1).mean()
            df["rolling_std"] = df["price"].rolling(window, min_periods=1).std()
            df["zscore"] = (df["price"] - df["rolling_mean"]) / df["rolling_std"]

        # JSON conversion
        df["timestamp"] = df["timestamp"].astype(str)
        records = df.to_dict(orient="records")

        try:
            save_cleaned_analytics(df, symbol_pair)
        except Exception as err:
            logging.warning(f"[DB] Could not save cleaned analytics: {err}")

        return jsonify({
            "status": "success",
            "message": "Computed analytics successfully.",
            "symbol_pair": symbol_pair,
            "mode": "pair" if '_' in symbol_pair else "single",
            "data": records
        }), 200

    except Exception as e:
        logging.exception("Error computing analytics")
        return jsonify({"status": "error", "message": str(e)}), 500


# -------------------------------------------------------
# 5️⃣ Endpoint: /api/analytics/cleaned
# -------------------------------------------------------
@analytics_bp.route("/cleaned", methods=["GET"])
def get_cleaned_analytics():
    symbol = request.args.get("symbol", "BTCUSDT_ETHUSDT")
    limit = int(request.args.get("limit", 200))
    try:
        conn = get_conn()
        q = """
            SELECT * FROM analytics_cleaned
            WHERE pair_symbol = ?
            ORDER BY timestamp DESC
            LIMIT ?;
        """
        df = pd.read_sql_query(q, conn, params=(symbol, limit))
        conn.close()

        if df.empty:
            return jsonify({
                "status": "warning",
                "message": f"No analytics found for {symbol}",
                "data": []
            })

        data = df.to_dict(orient="records")
        return jsonify({"status": "success", "count": len(data), "data": data})

    except Exception as e:
        logging.exception("Error fetching cleaned analytics.")
        return jsonify({"status": "error", "message": str(e)}), 500
