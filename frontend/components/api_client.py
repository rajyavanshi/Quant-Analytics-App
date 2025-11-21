# =====================================================
# File: frontend/components/api_client.py
# Purpose: Centralized API request handler for Flask backend
# Author: Suraj Prakash (Quant Developer)
# =====================================================

import requests
import os
from dotenv import load_dotenv

# -----------------------------------------------------
# 1️⃣ Load environment variables
# -----------------------------------------------------
load_dotenv()
BASE_URL = os.getenv("FLASK_API_URL", "http://127.0.0.1:5000")

# -----------------------------------------------------
# 2️⃣ Unified safe GET wrapper
# -----------------------------------------------------
def safe_get(endpoint: str, params: dict = None):
    """
    Perform a GET request safely and normalize response format.

    Returns:
        dict → {
            "status": "success" or "error",
            "message": "...",
            "data": ... or None
        }
    """
    url = f"{BASE_URL}{endpoint}"

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        json_data = response.json()

        # Normalize structure if backend returns plain data
        if "status" not in json_data:
            return {"status": "success", "message": "", "data": json_data}

        return json_data

    except requests.exceptions.Timeout:
        return {"status": "error", "message": f"Request to {url} timed out", "data": None}

    except requests.exceptions.ConnectionError:
        return {"status": "error", "message": f"Unable to connect to {url}", "data": None}

    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"Request failed: {e}", "data": None}

# =====================================================
# 🔹 ANALYTICS ENDPOINTS
# =====================================================
def get_latest_analytics():
    return safe_get("/api/analytics/latest")

def get_recent_analytics(symbol_pair: str, limit: int = 500, window: int = 100):
    """
    Fetch recent time-series analytics for a given symbol pair.
    Args:
        symbol_pair: str → like "BTCUSDT_ETHUSDT"
        limit: number of recent records to fetch
        window: rolling window for zscore/correlation
    """
    params = {"symbol_pair": symbol_pair, "limit": limit, "window": window}
    return safe_get("/api/analytics/recent", params)


# =====================================================
# 🔹 ALERTS ENDPOINTS
# =====================================================
def get_latest_alert():
    return safe_get("/api/alerts/latest")

def get_recent_alerts(limit: int = 10):
    return safe_get("/api/alerts/recent", {"limit": limit})

def get_alert_stats():
    return safe_get("/api/alerts/stats")

# =====================================================
# 🔹 DATA ENDPOINTS
# =====================================================
def get_symbols():
    return safe_get("/api/data/symbols")

def get_recent_ticks(symbol: str, limit: int = 10):
    params = {"symbol": symbol, "limit": limit}
    return safe_get("/api/data/recent_ticks", params)

def get_volume_summary():
    return safe_get("/api/data/volume_summary")

def get_backtest_results(symbol_pair: str = None, limit: int = 1000):
    params = {}
    if symbol_pair:
        params["symbol_pair"] = symbol_pair
    params["limit"] = limit
    return safe_get("/api/backtest/results", params=params)

# =====================================================
# Logs & data fetchers
# =====================================================
def get_logs(limit: int = 100):
    """Fetch backend or system logs (optional)."""
    return safe_get("/api/system/logs", params={"limit": limit})

def get_cleaned_analytics(symbol_pair: str = None, limit: int = 500):
    """Fetch cleaned analytics data saved server-side."""
    params = {"limit": limit}
    if symbol_pair:
        params["symbol_pair"] = symbol_pair
    return safe_get("/api/analytics/cleaned", params=params)


# =====================================================
# 🔹 SYSTEM / HEALTH ENDPOINTS
# =====================================================
def ping_server():
    return safe_get("/api/ping")

def get_system_status():
    return safe_get("/api/system/status")
