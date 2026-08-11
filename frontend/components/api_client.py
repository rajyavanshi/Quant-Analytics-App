"""Centralized Flask API client used by the Streamlit frontend."""

from __future__ import annotations

import os

import requests
from dotenv import load_dotenv

load_dotenv()
BASE_URL = os.getenv("FLASK_API_URL", "http://127.0.0.1:5000").rstrip("/")
REQUEST_TIMEOUT = max(1, int(os.getenv("API_REQUEST_TIMEOUT_SECONDS", "10")))


def safe_get(endpoint: str, params: dict | None = None):
    url = f"{BASE_URL}{endpoint}"
    try:
        response = requests.get(url, params=params or {}, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {"status": "success", "message": "", "data": payload}
    except requests.exceptions.Timeout:
        return {"status": "error", "message": f"Request timed out: {url}", "data": None}
    except requests.exceptions.ConnectionError:
        return {"status": "error", "message": f"Unable to connect to {url}", "data": None}
    except requests.exceptions.HTTPError as exc:
        try:
            payload = exc.response.json()
        except Exception:
            payload = {"status": "error", "message": str(exc), "data": None}
        return payload
    except (requests.exceptions.RequestException, ValueError) as exc:
        return {"status": "error", "message": str(exc), "data": None}


def get_latest_analytics(symbol_pair="BTCUSDT_ETHUSDT", window=100):
    return safe_get("/api/analytics/latest", {"symbol_pair": symbol_pair, "window": window})


def get_recent_analytics(symbol_pair: str, limit: int = 500, window: int = 100):
    return safe_get("/api/analytics/recent", {"symbol_pair": symbol_pair, "limit": limit, "window": window})


def get_cleaned_analytics(symbol_pair: str | None = None, limit: int = 500):
    params = {"limit": limit}
    if symbol_pair:
        params["symbol_pair"] = symbol_pair
    return safe_get("/api/analytics/cleaned", params)


def get_latest_alert():
    return safe_get("/api/alerts/latest")


def get_recent_alerts(limit: int = 10):
    return safe_get("/api/alerts/recent", {"limit": limit})


def get_alert_stats():
    return safe_get("/api/alerts/stats")


def get_symbols():
    return safe_get("/api/data/symbols")


def get_pairs():
    return safe_get("/api/data/pairs")


def get_recent_ticks(symbol: str, limit: int = 10):
    return safe_get("/api/data/recent_ticks", {"symbol": symbol, "limit": limit})


def get_volume_summary():
    return safe_get("/api/data/volume_summary")


def get_backtest_results(symbol_pair: str | None = None, limit: int = 1000):
    params = {"limit": limit}
    if symbol_pair:
        params["symbol_pair"] = symbol_pair
    return safe_get("/api/backtest/results", params)


def get_logs(limit: int = 100):
    return safe_get("/api/system/logs", {"limit": limit})


def ping_server():
    return safe_get("/api/ping")


def get_system_status():
    return safe_get("/api/system/status")
