"""Application entry point for the Quant Analytics backend.

Startup order:
1. initialize the canonical SQLite database
2. start Binance ingestion in a background thread
3. start the analytics worker in a background thread
4. serve the Flask API

Streamlit remains a separate UI process and consumes the Flask API.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

from backend.data_storage import init_db
from backend.analytics_engine import run_full_analytics, save_analytics_results_to_db
from api.flask_server import app as flask_app
from backend.websocket_ingest import start_stream

PROJECT_ROOT = Path(__file__).resolve().parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("quant_app")

DEFAULT_SYMBOLS = ["btcusdt", "ethusdt", "bnbusdt", "solusdt", "dogeusdt"]


def _symbols_from_env() -> list[str]:
    raw = os.getenv("BINANCE_SYMBOLS", "")
    if not raw.strip():
        return DEFAULT_SYMBOLS.copy()
    return [s.strip().lower() for s in raw.split(",") if s.strip()]


def analytics_worker(stop_event: threading.Event) -> None:
    """Run analytics periodically without blocking the API server."""
    interval = max(10, int(os.getenv("ANALYTICS_INTERVAL_SECONDS", "60")))
    symbol_x = os.getenv("ANALYTICS_SYMBOL_X", "BTCUSDT").upper()
    symbol_y = os.getenv("ANALYTICS_SYMBOL_Y", "ETHUSDT").upper()
    timeframe = os.getenv("ANALYTICS_TIMEFRAME", "1min")
    lookback = max(10, int(os.getenv("ANALYTICS_LOOKBACK_MINUTES", "120")))
    zwindow = max(3, int(os.getenv("ANALYTICS_ZSCORE_WINDOW", "60")))

    while not stop_event.is_set():
        try:
            result = run_full_analytics(
                symbol_x=symbol_x,
                symbol_y=symbol_y,
                timeframe=timeframe,
                lookback_minutes=lookback,
                zscore_window=zwindow,
            )
            save_analytics_results_to_db(result["results"])
            preview = result["df"].copy()
            preview.index.name = "timestamp"
            preview.reset_index().to_csv(
                PROJECT_ROOT / "backend" / "analytics_preview.csv", index=False
            )
            logger.info("Analytics cycle completed successfully")
        except Exception:
            logger.exception("Analytics cycle failed; retrying on next cycle")

        stop_event.wait(interval)


def configure_logging() -> None:
    """Configure application logging once at process startup."""
    if logging.getLogger().handlers:
        return
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler()],
    )


def main() -> None:
    configure_logging()
    logger.info("Starting Quant Analytics App")

    db_path = init_db()
    logger.info("Database initialized at %s", db_path)

    stop_event = threading.Event()

    ingestion_thread = threading.Thread(
        target=start_stream,
        args=(_symbols_from_env(),),
        name="binance-ingestion",
        daemon=True,
    )
    ingestion_thread.start()

    analytics_thread = threading.Thread(
        target=analytics_worker,
        args=(stop_event,),
        name="analytics-worker",
        daemon=True,
    )
    analytics_thread.start()

    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0").lower() in {"1", "true", "yes"}

    try:
        logger.info("Starting Flask API on %s:%s", host, port)
        flask_app.run(host=host, port=port, debug=debug, use_reloader=False)
    finally:
        stop_event.set()
        logger.info("Application shutdown requested")


if __name__ == "__main__":
    main()
