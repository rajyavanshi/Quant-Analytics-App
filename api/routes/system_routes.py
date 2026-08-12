"""System log endpoint."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, request

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_FILE = PROJECT_ROOT / "logs" / "app.log"
system_bp = Blueprint("system_bp", __name__)


@system_bp.get("/api/system/logs")
def get_system_logs():
    try:
        limit = request.args.get("limit", default=200, type=int)
        if limit is None or not 1 <= limit <= 5000:
            return jsonify({"status": "error", "message": "limit must be between 1 and 5000", "data": []}), 400
        if not LOG_FILE.exists():
            return jsonify({"status": "warning", "message": "No application log has been created yet", "data": []}), 200
        lines = LOG_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()
        return jsonify({"status": "success", "count": min(len(lines), limit), "data": lines[-limit:][::-1]})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc), "data": []}), 500
