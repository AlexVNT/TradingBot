# src/metatrader_connector.py
import os
from dotenv import load_dotenv
import MetaTrader5 as mt5
import pandas as pd
from src.utils import logger

# Lade die .env-Datei (ggf. passe den Pfad an)
load_dotenv()

class MetaTraderConnector:
    def __init__(self):
        self.account = os.getenv("MT_ACCOUNT")
        self.password = os.getenv("MT_PASSWORD")
        self.server  = os.getenv("MT_SERVER")
        
        if not self.account or not self.password or not self.server:
            raise ValueError("MetaTrader-Zugangsdaten nicht gefunden! Bitte prüfe deine .env.")
        
        # Initialisiere MetaTrader5
        if not mt5.initialize(login=int(self.account), password=self.password, server=self.server):
            raise Exception("MetaTrader5 konnte nicht initialisiert werden.")
        else:
            print("MetaTrader5 erfolgreich initialisiert.")

    def shutdown(self):
        mt5.shutdown()
    
    def get_account_info(self) -> dict:
        info = mt5.account_info()
        if info is None:
            raise Exception("Konnte Account-Info nicht abrufen.")
        return info._asdict()
    
    # In metatrader_connector.py
    def get_ohlcv(self, symbol, timeframe, limit=1000, shift=0):
        rates = mt5.copy_rates_from_pos(symbol, timeframe, shift, limit)
        if rates is None or len(rates) == 0:
            logger.error(f"Keine Daten für {symbol} im Zeitrahmen {timeframe}")
            return None
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        df = df[['open', 'high', 'low', 'close', 'tick_volume']]
        return df

    def execute_order(self, symbol: str, order_type: int, volume: float, price: float = 0):
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "magic": 234000,
            "comment": "Python script order",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        result = mt5.order_send(request)
        return result
