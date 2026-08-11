# Quant Analytics App

A full-stack quantitative market-analytics prototype for Binance Futures. The system ingests live trade ticks, stores them in SQLite, computes pair-trading analytics, exposes them through Flask, and renders the results in Streamlit.

## Current architecture

```text
Binance Futures WebSocket
        ↓
Buffered tick ingestion
        ↓
SQLite (WAL)
        ↓
OLS / Kalman / spread / z-score / ADF / correlation
        ↓
Flask REST API
        ↓
Streamlit dashboard
```

The live backend is started by `app.py`; Streamlit remains a separate UI process.

## Requirements

- Python 3.11 recommended
- Internet access for Binance Futures WebSocket
- Windows, macOS or Linux

## Installation

```bash
git clone https://github.com/rajyavanshi/Quant-Analytics-App.git
cd Quant-Analytics-App
python -m venv venv
```

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

Install runtime and development dependencies:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Optional configuration:

```bash
copy .env.example .env       # PowerShell/CMD equivalent may vary by shell
```

The database is initialized automatically when the application starts. You can also initialize it explicitly:

```bash
python -c "from backend.data_storage import init_db; print(init_db())"
```

## Run

Start the backend, ingestion service, analytics worker and Flask API together:

```bash
python app.py
```

Start the Streamlit dashboard in a second terminal:

```bash
streamlit run frontend/streamlit_app.py
```

The API defaults to `http://127.0.0.1:5000` and Streamlit to its normal port `8501`.

## API highlights

- `GET /api/ping`
- `GET /api/health/live`
- `GET /api/system/status`
- `GET /api/data/symbols`
- `GET /api/data/pairs`
- `GET /api/data/recent_ticks?symbol=BTCUSDT`
- `GET /api/analytics/recent?symbol_pair=BTCUSDT_ETHUSDT`
- `GET /api/analytics/latest?symbol_pair=BTCUSDT_ETHUSDT`
- `GET /api/analytics/cleaned`

## Quant analytics

The canonical analytics engine computes:

- Static OLS hedge ratio and intercept
- Dynamic Kalman hedge ratio
- Hedged spread
- Rolling z-score
- Augmented Dickey-Fuller stationarity test
- Rolling Pearson correlation

The frontend should consume these backend values rather than independently recomputing financial statistics.

## Configuration

See `.env.example` for supported settings, including:

- Binance symbols
- WebSocket batching and reconnect limits
- Flask host/port/debug mode
- Analytics pair, timeframe and lookback
- API request timeout
- Logging level

## Testing

Unit and regression tests live under `tests/` and run without a live Binance connection:

```bash
pytest -q
```

GitHub Actions runs the same test suite on pushes and pull requests.

## Data and generated files

The runtime SQLite database, logs, Python caches and generated analytics/backtest artifacts are intentionally excluded from version control. Do not commit live market data or secrets.

## Author

**Suraj Prakash**  
B.Tech Electronics & Communication Engineering, BIT Mesra

GitHub: https://github.com/rajyavanshi
