# =====================================================
# File: api/flask_server.py
# Purpose: Flask API server with structured logging and unified response system
# Author: Suraj Prakash (Quant Developer)
# =====================================================

from flask import Flask, jsonify, request, g
from flask_cors import CORS
import logging
import os
import datetime
import time
import sys
import io

# -------------------------------------------------------
# Fix Windows Console Encoding for UTF-8
# -------------------------------------------------------
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# -------------------------------------------------------
# Import Blueprints (no relative dots here)
# -------------------------------------------------------
from api.routes.analytics_routes import analytics_bp
from api.routes.alert_routes import alert_bp
from api.routes.data_routes import data_bp
from api.routes.backtest_routes import backtest_bp
from api.routes.system_routes import system_bp

# -------------------------------------------------------
# Initialize Flask App
# -------------------------------------------------------
app = Flask(__name__)
CORS(app)

# -------------------------------------------------------
# Logging Setup
# -------------------------------------------------------
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logging.info("✅ Flask logging initialized successfully.")

# -------------------------------------------------------
# Register Blueprints
# -------------------------------------------------------
try:
    app.register_blueprint(analytics_bp)
    app.register_blueprint(alert_bp)
    app.register_blueprint(data_bp)
    app.register_blueprint(backtest_bp)
    app.register_blueprint(system_bp)
    logging.info("✅ All blueprints registered successfully.")
except Exception as e:
    logging.error(f"Blueprint registration failed: {str(e)}")

# -------------------------------------------------------
# Unified JSON Response
# -------------------------------------------------------
def make_response(status: str, data=None, message: str = "", code: int = 200):
    payload = {"status": status, "message": message, "data": data}
    return jsonify(payload), code

# -------------------------------------------------------
# Middleware: Request Duration Tracking
# -------------------------------------------------------
@app.before_request
def before_request():
    g.start_time = time.time()

@app.after_request
def after_request(response):
    if hasattr(g, "start_time"):
        elapsed_ms = (time.time() - g.start_time) * 1000
        logging.info(f"{request.method} {request.path} -> {response.status_code} ({elapsed_ms:.2f} ms)")
    return response

# -------------------------------------------------------
# Health Check & System Info
# -------------------------------------------------------
@app.route("/api/ping", methods=["GET"])
def ping():
    return make_response(
        "success",
        data={"server_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        message="Flask API server is alive 🚀",
        code=200,
    )

@app.route("/api/system/status", methods=["GET"])
def system_status():
    routes = sorted([rule.rule for rule in app.url_map.iter_rules()])
    status_data = {
        "server": "running",
        "uptime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "available_routes": routes,
    }
    return make_response("success", data=status_data, message="System status OK", code=200)

# -------------------------------------------------------
# Error Handlers
# -------------------------------------------------------
@app.errorhandler(404)
def not_found_error(e):
    logging.warning(f"404 Not Found: {request.path}")
    return make_response("error", message="Endpoint not found", code=404)

@app.errorhandler(500)
def internal_error(e):
    logging.error(f"500 Internal Server Error: {str(e)}")
    return make_response("error", message="Internal server error", code=500)

@app.errorhandler(Exception)
def unhandled_exception(e):
    logging.exception("Unhandled Exception:")
    return make_response("error", message=f"Unexpected error: {str(e)}", code=500)

# -------------------------------------------------------
# Run Server
# -------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", 5000))
    logging.info(f"🚀 Starting Flask server on http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=True)
