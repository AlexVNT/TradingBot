# src/order_execution.py
from risk_management import calculate_position_size
from utils import logger

def execute_order(exchange, symbol, signal, account_balance: float, entry_price: float, stop_loss_price: float):
    """
    Führt einen Marktauftrag aus, basierend auf dem Signal und berechnet die Positionsgröße dynamisch.
    account_balance: Aktueller Kontostand.
    entry_price: Der Preis, zu dem die Order eröffnet wird.
    stop_loss_price: Der Preis, bei dem der Trade geschlossen wird (Stop-Loss).
    """
    # Berechne die Positionsgröße
    position_size = calculate_position_size(account_balance, risk_pct=0.01, entry_price=entry_price, stop_loss_price=stop_loss_price)
    try:
        if signal == "BUY":
            order = exchange.create_market_order(symbol, 'buy', amount=position_size)
            logger.info(f"Buy Order platziert: {order}")
        elif signal == "SELL":
            order = exchange.create_market_order(symbol, 'sell', amount=position_size)
            logger.info(f"Sell Order platziert: {order}")
    except Exception as e:
        logger.error(f"Fehler bei Orderausführung: {e}")
