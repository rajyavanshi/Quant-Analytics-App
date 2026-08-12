"""Application entry point for the Quant Analytics backend."""

from __future__ import annotations

import logging
import os
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

from api.flask_server import app as flask_app
from backend.alert_system import run_alert_system
from backend.analytics_engine import run_full_analytics, save_analytics_results_to_db
from backend.data_storage import init_db
from backend.websocket_ingest import start_stream

PROJECT_ROOT = Path(__file__).resolve().parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger("quant_app")
DEFAULT_SYMBOLS = ["btcusdt", "ethusdt", "bnbusdt", "solusdt", "dogeusdt"]


def _symbols_from_env() -> list[str]:
    raw = os.getenv("BINANCE_SYMBOLS", "")
    return [s.strip().lower() for s in raw.split(",") if s.strip()] or DEFAULT_SYMBOLS.copy()


def analytics_worker(stop_event: threading.Event) -> None:
    interval = max(10, int(os.getenv("ANALYTICS_INTERVAL_SECONDS", "60")))
    symbol_x = os.getenv("ANALYTICS_SYMBOL_X", "BTCUSDT").upper()
    symbol_y = os.getenv("ANALYTICS_SYMBOL_Y", "ETHUSDT").upper()
    timeframe = os.getenv("ANALYTICS_TIMEFRAME", "1min")
    lookback = max(10, int(os.getenv("ANALYTICS_LOOKBACK_MINUTES", "120")))
    zwindow = max(3, int(os.getenv("ANALYTICS_ZSCORE_WINDOW", "60")))

    while not stop_event.is_set():
        try:
            result = run_full_analytics(symbol_x, symbol_y, timeframe, lookback, zwindow)
            save_analytics_results_to_db(result["results"])
            preview = result["df"].copy()
            preview.index.name = "timestamp"
            preview.reset_index().to_csv(PROJECT_ROOT / "backend" / "analytics_preview.csv", index=False)
            try:
                run_alert_system()
            except Exception:
                logger.exception("Alert generation failed for analytics cycle")
            logger.info("Analytics and signal cycle completed")
        except Exception:
            logger.exception("Analytics cycle failed; retrying on next cycle")
        stop_event.wait(interval)


def configure_logging() -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    file_handler = RotatingFileHandler(
        LOG_DIR / "app.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.setLevel(level)
    root.addHandler(console)
    root.addHandler(file_handler)


def main() -> None:
    configure_logging()
    db_path = init_db()
    logger.info("Starting Quant Analytics App; database=%s", db_path)

    stop_event = threading.Event()
    threading.Thread(target=start_stream, args=(_symbols_from_env(),), name="binance-ingestion", daemon=True).start()
    threading.Thread(target=analytics_worker, args=(stop_event,), name="analytics-worker", daemon=True).start()

    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0").lower() in {"1", "true", "yes"}
    try:
        flask_app.run(host=host, port=port, debug=debug, use_reloader=False)
    finally:
        stop_event.set()
        logger.info("Application shutdown requested")


if __name__ == "__main__":
    main()
