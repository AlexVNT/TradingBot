# test_mt.py
from src.metatrader_connector import MetaTraderConnector
import MetaTrader5 as mt5

try:
    mt_connector = MetaTraderConnector()
    account_info = mt_connector.get_account_info()
    print("Account Info:", account_info)
    
    # Beispiel: Hole 1-Stunden-Daten für EURUSD
    df = mt_connector.get_ohlcv("EURUSD", mt5.TIMEFRAME_H1, limit=10)
    print(df.head())
    
    mt_connector.shutdown()
except Exception as e:
    print("Fehler:", e)
