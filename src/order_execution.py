import time
import hashlib
import hmac
import urllib.parse
import requests
from risk_management import calculate_position_size
from utils import logger

def execute_order(connector, symbol, signal, entry_price: float, stop_loss_price: float, take_profit_price: float, leverage: int = 10):
    """
    Führt eine Marktorder mit Stop Loss (SL) und Take Profit (TP) aus.

    :param connector: Instanz von BinanceConnector oder BinanceTestnetConnector.
    :param symbol: Handelspaar, z. B. "BTCUSDT".
    :param signal: "BUY" oder "SELL".
    :param entry_price: Einstiegspreis der Order.
    :param stop_loss_price: Stop-Loss-Preis.
    :param take_profit_price: Take-Profit-Preis.
    """
    try:
        # ✅ Symbol korrekt formatieren
        symbol = symbol.replace("/", "")

        # ✅ API-Zugangsdaten abrufen
        account_balance = connector.get_balance(asset="USDT")  # Futures Balance
        base_url = connector.base_url  # Dynamische Base-URL (Live/Testnet)
        api_key = connector.api_key
        secret_key = connector.secret_key

        # Hebel aus Config berücksichtigen (hier als Beispiel 10; idealerweise aus config lesen)
        leverage = 10

        # ✅ Berechne Positionsgröße basierend auf Risiko-Management
        risk_pct = 0.01  # Beispielwert; kann aus Config kommen
        # Ursprüngliche Berechnung multipliziert jetzt mit dem Hebel
        raw_position_size = calculate_position_size(account_balance, risk_pct, entry_price, stop_loss_price) * leverage
        allowed_precision = 3  # Binance Futures benötigt oft 3 Dezimalstellen für BTCUSDT
        position_size = round(raw_position_size, allowed_precision)

        if position_size <= 0:
            logger.error("❌ Fehler: Position Size ist zu klein oder 0. Order wird nicht platziert.")
            return None

        # ✅ Marktorder ausführen
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
            logger.error(f"❌ Fehler bei Marktorder-Ausführung: {order_data}")
            return None

        order_id = order_data.get("orderId")
        logger.info(f"✅ Marktorder erfolgreich platziert: {order_data}")

        # ✅ Stop-Loss Order setzen
        sl_params = {
            "symbol": symbol,
            "side": "SELL" if signal.upper() == "BUY" else "BUY",
            "type": "STOP_MARKET",
            "stopPrice": round(stop_loss_price, allowed_precision),
            "quantity": position_size,
            "reduceOnly": "true",  # Sicherstellen, dass keine neue Position geöffnet wird
            "timestamp": int(time.time() * 1000),
        }
        sl_query = urllib.parse.urlencode(sl_params)
        sl_signature = hmac.new(secret_key.encode(), sl_query.encode(), hashlib.sha256).hexdigest()
        sl_params["signature"] = sl_signature

        response_sl = requests.post(f"{base_url}/fapi/v1/order", params=sl_params, headers=headers)
        sl_data = response_sl.json()

        if response_sl.status_code == 200:
            logger.info(f"✅ Stop-Loss erfolgreich gesetzt: {sl_data}")
        else:
            logger.error(f"❌ Fehler beim Setzen des Stop-Loss: {sl_data}")

        # ✅ Take-Profit Order setzen
        tp_params = {
            "symbol": symbol,
            "side": "SELL" if signal.upper() == "BUY" else "BUY",
            "type": "TAKE_PROFIT_MARKET",
            "stopPrice": round(take_profit_price, allowed_precision),
            "quantity": position_size,
            "reduceOnly": "true",  # Sicherstellen, dass keine neue Position geöffnet wird
            "timestamp": int(time.time() * 1000),
        }
        tp_query = urllib.parse.urlencode(tp_params)
        tp_signature = hmac.new(secret_key.encode(), tp_query.encode(), hashlib.sha256).hexdigest()
        tp_params["signature"] = tp_signature

        response_tp = requests.post(f"{base_url}/fapi/v1/order", params=tp_params, headers=headers)
        tp_data = response_tp.json()

        if response_tp.status_code == 200:
            logger.info(f"✅ Take-Profit erfolgreich gesetzt: {tp_data}")
        else:
            logger.error(f"❌ Fehler beim Setzen des Take-Profit: {tp_data}")

        return order_data

    except Exception as e:
        logger.error(f"❌ Fehler in execute_order: {str(e)}")
        return None
