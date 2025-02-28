# src/order_execution.py
import time
import hashlib
import hmac
import urllib.parse
import requests
from risk_management import calculate_position_size
from utils import logger

def execute_order(api_key, secret_key, symbol, signal, account_balance: float, entry_price: float, stop_loss_price: float, base_url: str):
    """
    Führt einen Marktauftrag via Binance Futures REST API aus.
    :param api_key: API Key aus der Config.
    :param secret_key: Secret Key aus der Config.
    :param symbol: Das Handelspaar, z. B. "BTC/USDT".
    :param signal: "BUY" oder "SELL".
    :param account_balance: Aktueller Kontostand.
    :param entry_price: Der aktuelle Preis, an dem der Trade eröffnet wird.
    :param stop_loss_price: Berechneter Stop-Loss-Preis.
    :param base_url: Die Basis-URL (Testnet).
    """
    # Berechne die Positionsgröße (hier risk_pct kann ebenfalls aus der Config kommen)
    risk_pct = 0.01  # Beispiel; alternativ aus der Config
    raw_position_size = calculate_position_size(account_balance, risk_pct, entry_price, stop_loss_price)
    
    # Für BTC/USDT beträgt die zulässige Präzision (zum Beispiel) 3 Dezimalstellen.
    # Diesen Wert kannst du in deiner Config hinterlegen oder dynamisch über die API abfragen.
    allowed_precision = 3
    position_size = round(raw_position_size, allowed_precision)
    
    endpoint = "/fapi/v1/order"
    url = base_url + endpoint
    timestamp = int(time.time() * 1000)
    params = {
        "symbol": symbol.replace("/", ""),
        "side": "BUY" if signal == "BUY" else "SELL",
        "type": "MARKET",
        "quantity": position_size,
        "timestamp": timestamp,
    }
    query_string = urllib.parse.urlencode(params)
    signature = hmac.new(secret_key.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    params["signature"] = signature
    headers = {
        "X-MBX-APIKEY": api_key
    }
    response = requests.post(url, params=params, headers=headers)
    if response.status_code == 200:
        order = response.json()
        logger.info(f"Order platziert: {order}")
    else:
        logger.error(f"Fehler bei Orderausführung: {response.text}")
