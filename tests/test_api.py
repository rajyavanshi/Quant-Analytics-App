import os

import pandas as pd
import pytest

os.environ["FLASK_DEBUG"] = "0"

from api.flask_server import app
from backend.backtest_engine import compute_metrics, simulate_backtest


@pytest.fixture
def client():
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client


def test_health_and_ping_endpoints(client):
    ping = client.get("/api/ping")
    assert ping.status_code == 200
    assert ping.get_json()["status"] == "success"

    live = client.get("/api/health/live")
    assert live.status_code == 200
    assert live.get_json()["data"]["status"] == "alive"


def test_data_pairs_endpoint_exists(client):
    response = client.get("/api/data/pairs")
    assert response.status_code in (200, 404)
    assert isinstance(response.get_json(), dict)


def test_invalid_analytics_parameters_are_rejected(client):
    response = client.get("/api/analytics/recent?symbol_pair=BTCUSDT_ETHUSDT&limit=999999")
    assert response.status_code == 400
    assert response.get_json()["status"] == "error"


def test_pair_analytics_route_uses_canonical_engine(monkeypatch, client):
    from api import analytics_engine_from_ticks as adapter

    timestamps = pd.date_range("2026-01-01", periods=3, freq="min", tz="UTC")
    canonical = pd.DataFrame(
        {
            "x_price": [100.0, 101.0, 102.0],
            "y_price": [200.0, 202.0, 204.0],
            "hedge_ratio": [2.0, 2.0, 2.0],
            "intercept": [0.0, 0.0, 0.0],
            "spread": [0.0, 0.0, 0.0],
            "mean_spread": [0.0, 0.0, 0.0],
            "std_spread": [0.0, 0.0, 0.0],
            "zscore": [None, None, None],
            "rolling_corr": [1.0, 1.0, 1.0],
            "adf_stat": [None, None, None],
            "adf_pvalue": [None, None, None],
        },
        index=timestamps,
    )

    called = {}

    def fake_run_full_analytics(**kwargs):
        called.update(kwargs)
        return {"results": {}, "df": canonical}

    monkeypatch.setattr(adapter, "run_full_analytics", fake_run_full_analytics)

    response = client.get("/api/analytics/recent?symbol_pair=BNBUSDT_BTCUSDT&window=3")
    assert response.status_code == 200
    assert called == {
        "symbol_x": "BNBUSDT",
        "symbol_y": "BTCUSDT",
        "timeframe": "1min",
        "lookback_minutes": 10,
        "zscore_window": 3,
    }
    assert response.get_json()["data"][0]["hedge_ratio"] == 2.0


def test_backtest_extracts_long_and_short_trade_pnl_from_cashflow_intervals():
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=7, freq="min", tz="UTC"),
            "spread": [0.0, 1.0, 3.0, 2.0, 0.0, -2.0, -4.0],
            "signal": ["HOLD", "LONG", "LONG", "HOLD", "HOLD", "SHORT", "SHORT"],
        }
    )
    result = simulate_backtest(df, notional_per_unit=1.0, fee_per_trade=0.0, slippage_pct=0.0)
    metrics = compute_metrics(result)

    assert metrics["total_pnl"] == pytest.approx(3.0)
    assert metrics["n_trades"] == 2
    assert [t["trade_pnl"] for t in metrics["trades_sample"]] == pytest.approx([1.0, 2.0])
    assert [t["position"] for t in metrics["trades_sample"]] == pytest.approx([1.0, -1.0])


def test_trade_pnl_includes_entry_and_exit_costs_and_reconciles_to_total_pnl():
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=5, freq="min", tz="UTC"),
            "spread": [0.0, 1.0, 3.0, 2.0, 2.0],
            "signal": ["HOLD", "LONG", "LONG", "HOLD", "HOLD"],
        }
    )
    result = simulate_backtest(df, notional_per_unit=1.0, fee_per_trade=1.0, slippage_pct=0.0)
    metrics = compute_metrics(result)

    assert metrics["total_pnl"] == pytest.approx(0.0)
    assert metrics["n_trades"] == 1
    assert metrics["trades_sample"][0]["trade_pnl"] == pytest.approx(0.0)


def test_reversal_cost_is_split_between_old_exit_and_new_entry():
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=6, freq="min", tz="UTC"),
            "spread": [0.0, 1.0, 3.0, 2.0, 4.0, 4.0],
            "signal": ["HOLD", "LONG", "LONG", "SHORT", "SHORT", "HOLD"],
        }
    )
    result = simulate_backtest(df, notional_per_unit=1.0, fee_per_trade=1.0, slippage_pct=0.0)
    metrics = compute_metrics(result)

    trades = metrics["trades_sample"]
    assert metrics["n_trades"] == 2
    assert sum(t["trade_pnl"] for t in trades) == pytest.approx(metrics["total_pnl"])
    assert [t["position"] for t in trades] == pytest.approx([1.0, -1.0])
    # Long: entry -1, market +2, reversal interval -1, reversal exit -1 => -1.
    # Short: reversal entry -1, market -2, final exit -1 => -4.
    assert [t["trade_pnl"] for t in trades] == pytest.approx([-1.0, -4.0])
