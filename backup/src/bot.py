# src/bot.py
import ccxt
import pandas as pd
from strategy import CompositeStrategy
from order_execution import execute_order
from utils import logger
from ohlcv_fetcher import fetch_ohlcv

class TradingBot:
    def __init__(self, config):
        self.config = config
        
        # Testnet-Instanz für Futures
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
        self.exchange.urls["api"] = "https://testnet.binancefuture.com"
        self.exchange.urls["fapiPrivate"] = "https://testnet.binancefuture.com/fapi/v1"
        
        self.strategy = CompositeStrategy(config)
    
    def fetch_data(self):
        symbol = self.config['trading']['symbol']
        timeframe = self.config['trading']['timeframe']
        ohlcv_df = fetch_ohlcv(symbol, timeframe, limit=500)
        logger.info(f"Fetched Hourly Data (Sample):\n{ohlcv_df.head()}")
        return ohlcv_df

    def fetch_daily_data(self):
        """
        Holt die übergeordnete Chart-Daten basierend auf dem in der Config gesetzten
        higher_timeframe. Da Binance Testnet keine dedizierten Daily‑Endpoints bietet,
        wird eine separate Exchange-Instanz (Mainnet) genutzt.
        """
        symbol = self.config['trading']['symbol']
        higher_tf = self.config['trading'].get('higher_timeframe', '1d')
        exchange_daily = ccxt.binance({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
                'adjustForTimeDifference': True,
            },
            # Mainnet-Daten abrufen
        })
        ohlcv_daily = exchange_daily.fetch_ohlcv(symbol, higher_tf, limit=500)
        df_daily = pd.DataFrame(ohlcv_daily, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_daily['timestamp'] = pd.to_datetime(df_daily['timestamp'], unit='ms')
        df_daily.set_index('timestamp', inplace=True)
        df_daily.columns = [col.strip().lower().replace(' ', '_') for col in df_daily.columns]
        return df_daily


    def start(self):
        df_1h = self.fetch_data()
        df_daily = self.fetch_daily_data()
        # Übergebe beide DataFrames an die Strategie
        signal = self.strategy.generate_signal(df_1h, df_daily)
        logger.info(f"Generiertes Signal: {signal}")
        if signal != "HOLD":
            execute_order(self.exchange, self.config['trading']['symbol'], signal)
