# src/bot.py
import os
import time
import requests
import pandas as pd
import urllib.parse
import hashlib
import talib
import hmac
import yaml
from dotenv import load_dotenv
from src.utils import logger
from src.strategy import CompositeStrategy
from src.order_execution import execute_order
from src.binance_connector import BinanceConnector, BinanceTestnetConnector
from src.metatrader_connector import MetaTraderConnector
import MetaTrader5 as mt5

load_dotenv()
CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')

def load_config():
    with open(CONFIG_PATH, "r") as file:
        return yaml.safe_load(file)

config = load_config()

class TradingBot:
    def __init__(self, config):
        self.config = config
        self.connectors = {}
        self.strategies = {}
        self.running = False  # Zustand des Bots
        
        # Initialisiere Plattformen und Symbole
        self.platforms = []
        if config["platforms"].get("binance", False):
            self.platforms.append("binance")
            trade_conf = config["trading"]["binance"]
            use_testnet = trade_conf.get("use_testnet", True)
            self.connectors["binance"] = BinanceTestnetConnector() if use_testnet else BinanceConnector()
            for symbol in trade_conf["symbols"].keys():
                self.strategies[symbol] = CompositeStrategy(config, symbol=symbol)
        
        if config["platforms"].get("metatrader", False):
            self.platforms.append("metatrader")
            self.connectors["metatrader"] = MetaTraderConnector()
            trade_conf = config["trading"]["metatrader"]
            for symbol in trade_conf["symbols"].keys():
                self.strategies[symbol] = CompositeStrategy(config, symbol=symbol)

    def _map_timeframe_mt(self, tf_str):
        mapping = {
            "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1, "MN1": mt5.TIMEFRAME_MN1
        }
        return mapping.get(tf_str.upper(), mt5.TIMEFRAME_H1)

    def fetch_data(self, platform, symbol, timeframe):
        connector = self.connectors[platform]
        if platform == "binance":
            return connector.get_ohlcv(symbol, timeframe)
        elif platform == "metatrader":
            mt_tf = self._map_timeframe_mt(timeframe)
            return connector.get_ohlcv(symbol, mt_tf, limit=100)

    def get_current_position(self, platform, symbol):
        connector = self.connectors[platform]
        if platform == "binance":
            endpoint = "/fapi/v2/positionRisk"
            timestamp = int(time.time() * 1000)
            params = {"timestamp": timestamp, "symbol": symbol}
            query_string = urllib.parse.urlencode(params)
            signature = hmac.new(connector.secret_key.encode(), query_string.encode(), hashlib.sha256).hexdigest()
            params["signature"] = signature
            headers = {"X-MBX-APIKEY": connector.api_key}
            url = f"{connector.base_url}{endpoint}?{urllib.parse.urlencode(params)}"
            try:
                response = requests.get(url, headers=headers)
                data = response.json()
                pos_amt = float(data[0].get("positionAmt", 0))
                if pos_amt > 0:
                    return "LONG"
                elif pos_amt < 0:
                    return "SHORT"
                return "NONE"
            except Exception as e:
                logger.error(f"Fehler beim Abrufen der Position für {symbol}: {e}")
                return "NONE"
        elif platform == "metatrader":
            positions = mt5.positions_get(symbol=symbol)
            if positions:
                pos = positions[0]
                return "LONG" if pos.type == mt5.ORDER_TYPE_BUY else "SHORT"
            return "NONE"

    def manage_trailing_tp(self, platform, symbol, position, entry_price, highest_price, lowest_price):
        connector = self.connectors[platform]
        strategy = self.strategies[symbol]
        df = self.fetch_data(platform, symbol, self.config["trading"][platform]["timeframe"])
        atr = talib.ATR(df['high'], df['low'], df['close'], timeperiod=strategy.atr_period).iloc[-1]
        current_price = df['close'].iloc[-1]

        if position == "LONG":
            stop_loss = entry_price - strategy.atr_sl_multiplier * atr
            trailing_tp = highest_price - strategy.atr_tp_multiplier * atr
            if current_price <= stop_loss or current_price <= trailing_tp:
                if platform == "binance":
                    params = {
                        "symbol": symbol,
                        "side": "SELL",
                        "type": "MARKET",
                        "quantity": connector.get_position_size(symbol),
                        "timestamp": int(time.time() * 1000)
                    }
                    query = urllib.parse.urlencode(params)
                    signature = hmac.new(connector.secret_key.encode(), query.encode(), hashlib.sha256).hexdigest()
                    params["signature"] = signature
                    requests.post(f"{connector.base_url}/fapi/v1/order", params=params, headers={"X-MBX-APIKEY": connector.api_key})
                elif platform == "metatrader":
                    mt5.Close(symbol)
                logger.info(f"{platform}/{symbol}: Position geschlossen bei {current_price}")
        elif position == "SHORT":
            stop_loss = entry_price + strategy.atr_sl_multiplier * atr
            trailing_tp = lowest_price + strategy.atr_tp_multiplier * atr
            if current_price >= stop_loss or current_price >= trailing_tp:
                if platform == "binance":
                    params = {
                        "symbol": symbol,
                        "side": "BUY",
                        "type": "MARKET",
                        "quantity": connector.get_position_size(symbol),
                        "timestamp": int(time.time() * 1000)
                    }
                    query = urllib.parse.urlencode(params)
                    signature = hmac.new(connector.secret_key.encode(), query.encode(), hashlib.sha256).hexdigest()
                    params["signature"] = signature
                    requests.post(f"{connector.base_url}/fapi/v1/order", params=params, headers={"X-MBX-APIKEY": connector.api_key})
                elif platform == "metatrader":
                    mt5.Close(symbol)
                logger.info(f"{platform}/{symbol}: Position geschlossen bei {current_price}")

    def start(self):
        self.running = True
        logger.info("TradingBot gestartet")
        while self.running:
            try:
                for platform in self.platforms:
                    trade_conf = self.config["trading"][platform]
                    symbols = trade_conf["symbols"].keys()
                    for symbol in symbols:
                        df = self.fetch_data(platform, symbol, trade_conf["timeframe"])
                        daily_df = self.fetch_data(platform, symbol, trade_conf["higher_timeframe"])
                        current_position = self.get_current_position(platform, symbol)
                        logger.info(f"Aktuelle Position ({platform}/{symbol}): {current_position}")

                        signal = self.strategies[symbol].generate_signal(df, daily_df, current_position, symbol)
                        logger.info(f"Generiertes Signal für {platform}/{symbol}: {signal}")

                        if signal in ["BUY", "SELL"] and current_position == "NONE":
                            entry_price = df['close'].iloc[-1]
                            atr = talib.ATR(df['high'], df['low'], df['close'], timeperiod=self.strategies[symbol].atr_period).iloc[-1]
                            stop_loss_price = entry_price - atr * self.strategies[symbol].atr_sl_multiplier if signal == "BUY" else entry_price + atr * self.strategies[symbol].atr_sl_multiplier
                            execute_order(self.connectors[platform], symbol, signal, entry_price, stop_loss_price, None, trade_conf["leverage"])
                        elif current_position != "NONE":
                            highest_price = self.strategies[symbol].highest_price or df['close'].max()
                            lowest_price = self.strategies[symbol].lowest_price or df['close'].min()
                            self.manage_trailing_tp(platform, symbol, current_position, df['close'].iloc[0], highest_price, lowest_price)
            except Exception as e:
                logger.error(f"Fehler im Bot: {e}")
            time.sleep(60)  # Warte 60 Sekunden vor der nächsten Iteration

    def stop(self):
        self.running = False
        logger.info("TradingBot gestoppt")

if __name__ == "__main__":
    bot = TradingBot(config)
    bot.start()