# Quant Analytics App

## Overview
The **Quant Analytics App** is a full-stack quantitative research and live market analytics platform.  
It collects **real-time Binance Futures tick data**, runs advanced **quant analytics**, generates **trading signals**, performs **backtests**, and displays everything through an interactive **Streamlit dashboard**.

This project mirrors real trading infrastructure with:
- Live tick ingestion  
- SQLite storage  
- Statistical modelling (OLS, Kalman, ADF, Z-score)  
- REST API (Flask)  
- Dashboard visualization  
- Modular backend design  

**Status:**  
✔ Backend complete  
✔ Frontend basic working  
⏳ API integration in progress  

---

## Features
- Real-time WebSocket ingestion (BTCUSDT, ETHUSDT)
- Tick database using SQLite
- Analytics engine:
  - OLS hedge ratio
  - Kalman filter hedge ratio
  - Z-score computation
  - Spread modelling
  - ADF stationarity testing
  - Rolling correlations
- Alert system using Z-score thresholds
- Mean-reversion backtester  
- Streamlit dashboard with dark mode  
- Flask REST API (WIP)  

---

## Project Structure
```
Quant-Analytics-App/
│
├── backend/
│   ├── analytics_engine.py
│   ├── websocket_ingest.py
│   ├── alert_system.py
│   ├── backtest_engine.py
│   └── data_storage.py
│
├── api/
│   ├── flask_server.py
│   └── routes/
│
├── frontend/
│   ├── streamlit_app.py
│   ├── components/
│   └── assets/
│       └── dark_theme.css
│
├── database/
│   └── ticks.db
│
├── architecture/
│   ├── system_architecture.drawio
│   └── system_architecture.png
│
├── logs/
│   └── app.log
│
├── requirements.txt
├── app.py
└── README.md
```

---

## Installation

### 1. Clone the repository
```
git clone https://github.com/rajyavanshi/Quant-Analytics-App
cd Quant-Analytics-App
```

### 2. Create virtual environment
```
python -m venv venv
venv\Scriptsctivate
```

### 3. Install dependencies
```
pip install -r requirements.txt
```

### 4. Initialize the database
```
python -c "from backend.data_storage import init_db; init_db()"
```

---

## Running the Application

### Start live ingestion
```
python backend/websocket_ingest.py
```

### Run analytics manually
```
python -c "from backend.analytics_engine import run_full_analytics; print(run_full_analytics())"
```

### Start Streamlit dashboard
```
streamlit run frontend/streamlit_app.py
```

### Start Flask API (WIP)
```
python api/flask_server.py
```

### Run entire system (after API is complete)
```
python app.py
```

---

## Example Analytics Output
```json
{
  "symbol": "BTCUSDT",
  "timeframe": "1m",
  "hedge_ratio_ols": 0.98,
  "hedge_ratio_kalman": 0.99,
  "zscore_latest": 2.1,
  "adf_pvalue": 0.04
}
```

---

## Technologies Used
- Python  
- WebSocket (aiohttp, websocket-client)  
- SQLite  
- Flask  
- Streamlit  
- Pandas, NumPy, SciPy, Statsmodels  
- Plotly  

---

## Author
**Suraj Prakash**  
B.Tech Electronics & Communication Engineering  
BIT Mesra  

GitHub: https://github.com/rajyavanshi  

---

## Future Improvements
- Complete API → dashboard integration  
- Add Redis caching  
- Multi-asset correlation & portfolio analytics  
- Docker deployment  
- Backtest visualization UI  
- Live paper trading engine  

---



