from backend.websocket_ingest import normalize_trade


def test_normalize_trade_accepts_binance_trade():
    row = normalize_trade({
        "e": "trade",
        "T": 1750000000000,
        "s": "BTCUSDT",
        "p": "65000.12",
        "q": "0.01",
    })
    assert row is not None
    symbol, timestamp, price, volume = row
    assert symbol == "BTCUSDT"
    assert timestamp.endswith("+00:00")
    assert price == 65000.12
    assert volume == 0.01


def test_normalize_trade_rejects_invalid_values():
    assert normalize_trade({"s": "BTCUSDT", "T": 1, "p": "0", "q": "1"}) is None
    assert normalize_trade({"s": "BTCUSDT", "T": 1, "p": "1", "q": "-1"}) is None
