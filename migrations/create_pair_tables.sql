-- File: migrations/create_pair_tables.sql

PRAGMA foreign_keys = ON;

-- Table to store raw paired prices (tick/candle level)
CREATE TABLE IF NOT EXISTS pair_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol_pair TEXT NOT NULL,      -- e.g. BTCUSDT_ETHUSDT
    x_symbol TEXT NOT NULL,         -- e.g. BTCUSDT
    y_symbol TEXT NOT NULL,         -- e.g. ETHUSDT
    timestamp DATETIME NOT NULL,    -- ISO timestamp
    x_price REAL NOT NULL,
    y_price REAL NOT NULL
);

-- Table to store analytics snapshots computed over recent pair_prices
CREATE TABLE IF NOT EXISTS analytics_timeseries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol_pair TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    x_price REAL,
    y_price REAL,
    hedge_ratio_ols REAL,
    intercept_ols REAL,
    spread REAL,
    zscore REAL,
    rolling_corr REAL,
    adf_pvalue REAL,
    adf_stat REAL
);
