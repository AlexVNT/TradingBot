import os
import time
import requests
import pandas as pd
import urllib.parse
import hashlib
import hmac
from strategy import CompositeStrategy
from order_execution import execute_order
from utils import logger

class TradingBot:
    def __init__(self, config):
        self.config = config
        # API-Zugangsdaten aus der Config:
        self.api_key = config['binance']['api_key']
        self.secret_key = config['binance']['secret']
        # Basis-URL für Binance Futures Testnet:
        self.base_url = "https://testnet.binancefuture.com"
        # Handelsparameter:
        self.symbol = config['trading']['symbol']
        self.timeframe = config['trading']['timeframe']
        self.higher_timeframe = config['trading'].get('higher_timeframe', '1d')
        # Erstelle die Strategie-Instanz (CompositeStrategy erwartet sowohl den 1h- als auch den Daily-DataFrame)
        self.strategy = CompositeStrategy(config)

    def fetch_data(self) -> pd.DataFrame:
        """Lädt OHLCV-Daten vom /fapi/v1/klines-Endpoint für den aktuellen Timeframe."""
        url = f"{self.base_url}/fapi/v1/klines"
        params = {
            "symbol": self.symbol.replace("/", ""),
            "interval": self.timeframe,
            "limit": 500
        }
        response = requests.get(url, params=params)
        data = response.json()
        # Umwandlung der Kline-Daten in ein DataFrame
        df = pd.DataFrame(data, columns=[
            "timestamp", "open", "high", "low", "close", "volume", 
            "close_time", "quote_volume", "num_trades", "taker_buy_base", 
            "taker_buy_quote", "ignore"
        ])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        # Konvertiere numerische Spalten:
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        logger.info(f"Fetched Hourly Data (Sample):\n{df.head()}")
        return df

    def fetch_daily_data(self) -> pd.DataFrame:
        """Lädt OHLCV-Daten für den höheren Timeframe (z. B. 1d) vom gleichen Endpoint."""
        url = f"{self.base_url}/fapi/v1/klines"
        params = {
            "symbol": self.symbol.replace("/", ""),
            "interval": self.higher_timeframe,
            "limit": 500
        }
        response = requests.get(url, params=params)
        data = response.json()
        df = pd.DataFrame(data, columns=[
            "timestamp", "open", "high", "low", "close", "volume", 
            "close_time", "quote_volume", "num_trades", "taker_buy_base", 
            "taker_buy_quote", "ignore"
        ])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        return df

    def get_current_position(self) -> str:
        """
        Ruft den aktuellen Positionsstatus für das gehandelte Symbol ab.
        Verwendet den Endpoint /fapi/v2/positionRisk von Binance Futures Testnet.
        Gibt "LONG", "SHORT" oder "NONE" zurück.
        """
        endpoint = "/fapi/v2/positionRisk"
        timestamp = int(time.time() * 1000)
        params = {
            "timestamp": timestamp,
        }
        query_string = urllib.parse.urlencode(params)
        signature = hmac.new(self.secret_key.encode(), query_string.encode(), hashlib.sha256).hexdigest()
        params["signature"] = signature

        headers = {
            "X-MBX-APIKEY": self.api_key
        }

        url = f"{self.base_url}{endpoint}?{urllib.parse.urlencode(params)}"
        try:
            response = requests.get(url, headers=headers)
            data = response.json()
            symbol_no_slash = self.symbol.replace("/", "")
            for pos in data:
                if pos.get("symbol") == symbol_no_slash:
                    pos_amt = float(pos.get("positionAmt", 0))
                    if pos_amt > 0:
                        return "LONG"
                    elif pos_amt < 0:
                        return "SHORT"
            return "NONE"
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der aktuellen Position: {e}")
            return "NONE"

    def start(self):
        # Hole 1h-Daten:
        df = self.fetch_data()
        # Hole Daily-Daten:
        daily_df = self.fetch_daily_data()
        # Bestimme den aktuellen Positionsstatus (über REST-API)
        current_position = self.get_current_position()
        logger.info(f"Aktuelle Position: {current_position}")
        # Erzeuge Signal mithilfe der Strategie (übergebe beide DataFrames und current_position)
        signal = self.strategy.generate_signal(df, daily_df, current_position=current_position)
        logger.info(f"Generiertes Signal: {signal}")

        if signal != "HOLD":
            entry_price = df['close'].iloc[-1]
            stop_loss_pct = self.config['risk_management'].get('stop_loss_pct', 0.05)
            if signal == "BUY":
                stop_loss_price = entry_price * (1 - stop_loss_pct)
            elif signal == "SELL":
                stop_loss_price = entry_price * (1 + stop_loss_pct)
            else:
                stop_loss_price = entry_price
            account_balance = self.config.get('account_balance', 100000)
            try:
                execute_order(
                    self.api_key,
                    self.secret_key,
                    self.symbol,
                    signal,
                    account_balance,
                    entry_price,
                    stop_loss_price,
                    self.base_url
                )
                # Optional: Aktualisiere den internen Positionsstatus, falls Order erfolgreich war
                if signal == "BUY":
                    logger.info("LONG-Position eröffnet.")
                elif signal == "SELL":
                    logger.info("SHORT-Position eröffnet.")
            except Exception as e:
                logger.error(f"Fehler bei Orderausführung: {e}")
