# =====================================================
# File: api/routes/system_routes.py
# Purpose: Backend system and log endpoints
# Author: Suraj Prakash (Quant Developer)
# =====================================================

from flask import Blueprint, jsonify, request
import os
import logging

# Create blueprint
system_bp = Blueprint("system_bp", __name__)

# -----------------------------------------------------
# 🧾 LOG READER — /api/system/logs
# -----------------------------------------------------
@system_bp.route("/api/system/logs", methods=["GET"])
def get_system_logs():
    """
    Returns the last N lines from the app log file.
    Query params:
        limit (int): number of lines (default = 200)
    """
    try:
        log_file_path = os.path.join(os.path.dirname(__file__), "..", "..", "logs", "app.log")

        log_file_path = os.path.abspath(log_file_path)

        limit = int(request.args.get("limit", 200))

        if not os.path.exists(log_file_path):
            return jsonify({
                "status": "error",
                "message": f"Log file not found at {log_file_path}"
            }), 404

        # Read last N lines efficiently
        with open(log_file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-limit:]

        return jsonify({
            "status": "success",
            "count": len(lines),
            "data": lines[::-1]  # reverse chronological for display
        })

    except Exception as e:
        logging.exception("Error while reading logs.")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
