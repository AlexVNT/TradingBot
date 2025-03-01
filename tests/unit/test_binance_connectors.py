import pytest
from src.binance_connector import BinanceConnector, BinanceTestnetConnector

@pytest.fixture
def live_connector():
    return BinanceConnector()

@pytest.fixture
def testnet_connector():
    return BinanceTestnetConnector()

def test_live_server_time(live_connector):
    response = live_connector.get_server_time()
    assert "serverTime" in response

def test_testnet_server_time(testnet_connector):
    response = testnet_connector.get_server_time()
    assert "serverTime" in response
