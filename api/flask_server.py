"""Flask API application factory and HTTP server."""

from __future__ import annotations

import datetime as dt
import logging
import os
import time
from pathlib import Path

from flask import Flask, g, jsonify, request
from flask_cors import CORS

from api.routes.analytics_routes import analytics_bp
from api.routes.alert_routes import alert_bp
from api.routes.data_routes import data_bp
from api.routes.backtest_routes import backtest_bp
from api.routes.system_routes import system_bp

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)

# Keep permissive CORS for local development, but allow production callers to
# restrict the origin through an environment variable.
frontend_origin = os.getenv("FRONTEND_ORIGIN")
if frontend_origin:
    CORS(app, resources={r"/api/*": {"origins": frontend_origin}})
else:
    CORS(app, resources={r"/api/*": {"origins": "*"}})

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
    elapsed_ms = (time.monotonic() - getattr(g, "start_time", time.monotonic())) * 1000
    logger.info("%s %s -> %s (%.2f ms)", request.method, request.path, response.status_code, elapsed_ms)
    return response


@app.get("/api/ping")
def ping():
    return make_response(
        "success",
        {"server_time": dt.datetime.now(dt.timezone.utc).isoformat()},
        "Flask API server is alive",
    )


@app.get("/api/health/live")
def health_live():
    return make_response("success", {"status": "alive"}, "Liveness check passed")


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
    logger.warning("404 Not Found: %s", request.path)
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
    port = int(os.getenv("FLASK_PORT", "5000"))
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    debug = os.getenv("FLASK_DEBUG", "0").lower() in {"1", "true", "yes"}
    app.run(host=host, port=port, debug=debug, use_reloader=False)
