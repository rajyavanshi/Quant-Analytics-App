"""Flask API application and health endpoints."""

from __future__ import annotations

import datetime as dt
import logging
import os
import sqlite3
import time
from pathlib import Path

from flask import Flask, g, jsonify, request
from flask_cors import CORS

from api.routes.analytics_routes import analytics_bp
from api.routes.alert_routes import alert_bp
from api.routes.backtest_routes import backtest_bp
from api.routes.data_routes import data_bp
from api.routes.system_routes import system_bp
from database.database_setup import DB_PATH, init_db
from backend.websocket_ingest import health_snapshot

PROJECT_ROOT = Path(__file__).resolve().parent.parent
app = Flask(__name__)
frontend_origin = os.getenv("FRONTEND_ORIGIN")
CORS(app, resources={r"/api/*": {"origins": frontend_origin or "*"}})
logger = logging.getLogger(__name__)
for blueprint in (analytics_bp, alert_bp, data_bp, backtest_bp, system_bp):
    app.register_blueprint(blueprint)
_START_TIME = time.monotonic()


def make_response(status: str, data=None, message: str = "", code: int = 200):
    return jsonify({"status": status, "message": message, "data": data}), code


@app.before_request
def before_request():
    g.start_time = time.monotonic()


@app.after_request
def after_request(response):
    elapsed = (time.monotonic() - getattr(g, "start_time", time.monotonic())) * 1000
    logger.info("%s %s -> %s (%.2f ms)", request.method, request.path, response.status_code, elapsed)
    return response


@app.get("/api/ping")
def ping():
    return make_response("success", {"server_time": dt.datetime.now(dt.timezone.utc).isoformat()}, "API is alive")


@app.get("/api/health/live")
def health_live():
    return make_response("success", {"status": "alive"}, "Liveness check passed")


@app.get("/api/health/ready")
def health_ready():
    checks = {"database": False, "websocket": False}
    try:
        init_db()
        with sqlite3.connect(str(DB_PATH), timeout=2) as conn:
            conn.execute("SELECT 1").fetchone()
        checks["database"] = True
    except Exception as exc:
        checks["database_error"] = str(exc)

    ws = health_snapshot()
    checks["websocket"] = bool(ws.get("running"))
    checks["websocket_snapshot"] = ws
    ready = checks["database"]
    return make_response("success" if ready else "error", checks, "Readiness check", 200 if ready else 503)


@app.get("/api/system/status")
def system_status():
    routes = sorted(rule.rule for rule in app.url_map.iter_rules())
    return make_response(
        "success",
        {
            "server": "running",
            "uptime_seconds": round(time.monotonic() - _START_TIME, 3),
            "available_routes": routes,
        },
        "System status OK",
    )


@app.errorhandler(404)
def not_found_error(_error):
    return make_response("error", message="Endpoint not found", code=404)


@app.errorhandler(500)
def internal_error(_error):
    logger.exception("500 Internal Server Error")
    return make_response("error", message="Internal server error", code=500)


@app.errorhandler(Exception)
def unhandled_exception(error):
    logger.exception("Unhandled exception")
    return make_response("error", message=str(error), code=500)


if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0").lower() in {"1", "true", "yes"}
    app.run(host=host, port=port, debug=debug, use_reloader=False)
