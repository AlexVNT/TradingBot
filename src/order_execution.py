# src/order_execution.py
from risk_management import calculate_order_volume
from utils import logger

def execute_order(exchange, symbol, signal, balance, stop_loss_distance, current_price):
    try:
        # Beispiel: Risikoprofil 20%
        risk_percent = 0.20  
        volume = calculate_order_volume(balance, risk_percent, stop_loss_distance, current_price)
        if volume <= 0:
            logger.error("Berechnetes Ordervolumen ist 0 oder negativ.")
            return
        
        if signal == "BUY":
            order = exchange.create_market_order(symbol, 'buy', amount=volume)
            logger.info(f"Buy Order platziert: {order}")
        elif signal == "SELL":
            order = exchange.create_market_order(symbol, 'sell', amount=volume)
            logger.info(f"Sell Order platziert: {order}")
    except Exception as e:
        logger.error(f"Fehler bei Orderausführung: {e}")
