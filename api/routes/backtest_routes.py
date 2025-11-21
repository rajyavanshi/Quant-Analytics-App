# =====================================================
# File: api/routes/backtest_routes.py
# Purpose: Serve stored backtest performance results from backend files
# Author: Suraj Prakash (Quant Developer)
# =====================================================

from flask import Blueprint, jsonify, request
import os
import json
import pandas as pd

backtest_bp = Blueprint("backtest_bp", __name__)

# Paths
PROJECT_ROOT = r"D:\Quant Analytics App"
BACKTEST_DIR = os.path.join(PROJECT_ROOT, "backtest")
RESULTS_CSV = os.path.join(BACKTEST_DIR, "backtest_results.csv")
METRICS_JSON = os.path.join(BACKTEST_DIR, "backtest_metrics.json")

@backtest_bp.route("/api/backtest/results", methods=["GET"])
def get_backtest_results():
    """Serve stored backtest results as JSON."""
    limit = int(request.args.get("limit", 500))
    symbol_pair = request.args.get("symbol_pair", None)  # for future filtering

    # Check existence
    if not os.path.exists(RESULTS_CSV):
        return jsonify({
            "status": "error",
            "message": "No backtest results found. Run the backtest engine first.",
            "data": []
        }), 200

    try:
        df = pd.read_csv(RESULTS_CSV)
        df = df.tail(limit).reset_index(drop=True)

        # Add symbol pair field for consistency (optional, if you plan multi-pair)
        if "symbol_pair" not in df.columns and symbol_pair:
            df["symbol_pair"] = symbol_pair

        # Load metrics
        metrics = {}
        if os.path.exists(METRICS_JSON):
            with open(METRICS_JSON, "r") as f:
                metrics = json.load(f)

        return jsonify({
            "status": "success",
            "message": "Backtest results fetched successfully",
            "data": df.to_dict(orient="records"),
            "metrics": metrics
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to read backtest results: {str(e)}",
            "data": []
        }), 500
