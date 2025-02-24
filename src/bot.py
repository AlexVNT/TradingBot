# src/bot.py
import ccxt
import pandas as pd
from strategy import CompositeStrategy  # Neuer Import: CompositeStrategy statt SimpleRSIStrategy
from order_execution import execute_order
from utils import logger
from ohlcv_fetcher import fetch_ohlcv  # Funktion zum Abrufen von Marktdaten

class TradingBot:
    def __init__(self, config):
        self.config = config
        
        # Instanz für private Aufrufe (Testnet)
        self.exchange = ccxt.binance({
            'apiKey': config['binance']['api_key'],
            'secret': config['binance']['secret'],
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
                'adjustForTimeDifference': True,
            },
            'test': True,
        })
        # Setze Testnet-Endpunkte für private Operationen
        self.exchange.urls["api"] = "https://testnet.binancefuture.com"
        self.exchange.urls["fapiPrivate"] = "https://testnet.binancefuture.com/fapi/v1"
        
        # Verwende die neue CompositeStrategy
        self.strategy = CompositeStrategy(config)
    
    def fetch_data(self):
        symbol = self.config['trading']['symbol']
        timeframe = self.config['trading']['timeframe']
        # Verwende ohlcv_fetcher, um Live-Marktdaten zu holen
        ohlcv_df = fetch_ohlcv(symbol, timeframe, limit=500)
        return ohlcv_df

    def start(self):
        df = self.fetch_data()
        signal = self.strategy.generate_signal(df)
        logger.info(f"Generiertes Signal: {signal}")
        if signal != "HOLD":
            execute_order(self.exchange, self.config['trading']['symbol'], signal)
