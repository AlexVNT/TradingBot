import time
import hashlib
import hmac
import urllib.parse
import requests
from src.risk_management import calculate_position_size
from src.utils import logger

def execute_order(connector, symbol, signal, entry_price: float, stop_loss_price: float, take_profit_price: float = None, leverage: int = 1):
    try:
        symbol = symbol.replace("/", "")
        account_balance = connector.get_balance(asset="USDT")
        base_url = connector.base_url
        api_key = connector.api_key
        secret_key = connector.secret_key

        risk_pct = 0.01  # Aus config["risk_management"]["base_risk"]
        raw_position_size = calculate_position_size(account_balance, risk_pct, entry_price, stop_loss_price) * leverage
        position_size = round(raw_position_size, 3)

        if position_size <= 0:
            logger.error("Position Size ist zu klein oder 0.")
            return None

        order_params = {
            "symbol": symbol,
            "side": "BUY" if signal.upper() == "BUY" else "SELL",
            "type": "MARKET",
            "quantity": position_size,
            "timestamp": int(time.time() * 1000),
        }
        query_string = urllib.parse.urlencode(order_params)
        signature = hmac.new(secret_key.encode(), query_string.encode(), hashlib.sha256).hexdigest()
        order_params["signature"] = signature
        headers = {"X-MBX-APIKEY": api_key}

        response_order = requests.post(f"{base_url}/fapi/v1/order", params=order_params, headers=headers)
        order_data = response_order.json()
        if response_order.status_code != 200:
            logger.error(f"Fehler bei Marktorder: {order_data}")
            return None
        logger.info(f"Marktorder platziert: {order_data}")

        sl_params = {
            "symbol": symbol,
            "side": "SELL" if signal.upper() == "BUY" else "BUY",
            "type": "STOP_MARKET",
            "stopPrice": round(stop_loss_price, 3),
            "quantity": position_size,
            "reduceOnly": "true",
            "timestamp": int(time.time() * 1000),
        }
        sl_query = urllib.parse.urlencode(sl_params)
        sl_signature = hmac.new(secret_key.encode(), sl_query.encode(), hashlib.sha256).hexdigest()
        sl_params["signature"] = sl_signature
        response_sl = requests.post(f"{base_url}/fapi/v1/order", params=sl_params, headers=headers)
        if response_sl.status_code == 200:
            logger.info(f"Stop-Loss gesetzt: {response_sl.json()}")
        else:
            logger.error(f"Fehler beim Stop-Loss: {response_sl.json()}")

        return order_data
    except Exception as e:
        logger.error(f"Fehler in execute_order: {str(e)}")
        return None