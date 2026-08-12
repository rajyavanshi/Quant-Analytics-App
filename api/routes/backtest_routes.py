"""Backtest result API."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from flask import Blueprint, jsonify, request

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKTEST_DIR = PROJECT_ROOT / "backtest"
RESULTS_CSV = BACKTEST_DIR / "backtest_results.csv"
METRICS_JSON = BACKTEST_DIR / "backtest_metrics.json"

backtest_bp = Blueprint("backtest_bp", __name__)


@backtest_bp.get("/api/backtest/results")
def get_backtest_results():
    try:
        limit = request.args.get("limit", default=500, type=int)
        if limit is None or not 1 <= limit <= 5000:
            return jsonify({"status": "error", "message": "limit must be between 1 and 5000", "data": []}), 400
        if not RESULTS_CSV.exists():
            return jsonify({"status": "warning", "message": "No backtest results found", "data": [], "metrics": {}}), 200

        df = pd.read_csv(RESULTS_CSV).tail(limit).reset_index(drop=True)
        symbol_pair = request.args.get("symbol_pair")
        if symbol_pair and "symbol_pair" in df.columns:
            df = df[df["symbol_pair"].astype(str).str.upper() == symbol_pair.upper()]

        metrics = {}
        if METRICS_JSON.exists():
            metrics = json.loads(METRICS_JSON.read_text(encoding="utf-8"))

        return jsonify({
            "status": "success",
            "message": "Backtest results fetched successfully",
            "count": len(df),
            "data": df.to_dict(orient="records"),
            "metrics": metrics,
        })
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc), "data": []}), 500
