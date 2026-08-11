import os

import pytest

os.environ["FLASK_DEBUG"] = "0"

from api.flask_server import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    # API route smoke tests do not depend on live Binance data.
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
