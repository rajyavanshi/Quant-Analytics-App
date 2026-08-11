import os

import pandas as pd
import pytest

os.environ["FLASK_DEBUG"] = "0"

from api.flask_server import app


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
