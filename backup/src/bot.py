import os
import time
import requests
import pandas as pd
import urllib.parse
import hashlib
import hmac
import yaml
from dotenv import load_dotenv
from utils import logger

# Lade .env (sicherstellen, dass alle benötigten Variablen verfügbar sind)
load_dotenv()

# Lade die Konfigurationsdatei
CONFIG_PATH = "config/config.yaml"

def load_config():
    with open(CONFIG_PATH, "r") as file:
        return yaml.safe_load(file)

config = load_config()

# Importiere die Connectoren
from binance_connector import BinanceConnector, BinanceTestnetConnector
from metatrader_connector import MetaTraderConnector

class TradingBot:
    def __init__(self, config):
        self.config = config

        # Wähle die Plattform anhand der Konfiguration: Falls beide aktiv, priorisiere z. B. MetaTrader
        if config["platforms"].get("metatrader", False):
            self.platform = "metatrader"
        elif config["platforms"].get("binance", False):
            self.platform = "binance"
        else:
            raise Exception("Keine Plattform aktiviert!")

        # Plattform-abhängige Einstellungen laden
        if self.platform == "binance":
            trade_conf = config["trading"]["binance"]
            use_testnet = trade_conf.get("use_testnet", True)
            self.connector = BinanceTestnetConnector() if use_testnet else BinanceConnector()
            # Für Binance nehmen wir das Standard-Handelspaar aus den Einstellungen
            self.symbol = trade_conf["trade_pair"]
            self.timeframe = trade_conf["timeframe"]
            self.higher_timeframe = trade_conf["higher_timeframe"]
            self.leverage = trade_conf.get("leverage", 1)
        elif self.platform == "metatrader":
            trade_conf = config["trading"]["metatrader"]
            self.connector = MetaTraderConnector()  # Lädt die Zugangsdaten aus der .env
            self.symbol = trade_conf["symbol"]
            self.timeframe = trade_conf["timeframe"]
            self.higher_timeframe = trade_conf["higher_timeframe"]
            self.leverage = trade_conf.get("leverage", 1)

        # Strategie und Risikomanagement (plattformunabhängig)
        from strategy import CompositeStrategy
        self.strategy = CompositeStrategy(config)
        # Für Risiko-Management können wir feste Werte aus risk_management nehmen (eventuell später erweitern)
        self.stop_loss_pct = config["risk_management"].get("stop_loss_pct", 0.05)
        self.take_profit_pct = config["risk_management"].get("take_profit_pct", 0.10)

    def _map_timeframe_mt(self, tf_str):
        import MetaTrader5 as mt5
        mapping = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
            "W1": mt5.TIMEFRAME_W1,
            "MN1": mt5.TIMEFRAME_MN1
        }
        return mapping.get(tf_str.upper(), mt5.TIMEFRAME_H1)

    def fetch_data(self) -> pd.DataFrame:
        if self.platform == "binance":
            return self.connector.get_ohlcv(self.symbol, self.timeframe)
        elif self.platform == "metatrader":
            import MetaTrader5 as mt5
            mt_tf = self._map_timeframe_mt(self.timeframe)
            return self.connector.get_ohlcv(self.symbol, mt_tf)

    def fetch_daily_data(self) -> pd.DataFrame:
        if self.platform == "binance":
            return self.connector.get_ohlcv(self.symbol, self.higher_timeframe)
        elif self.platform == "metatrader":
            import MetaTrader5 as mt5
            mt_tf = self._map_timeframe_mt(self.higher_timeframe)
            return self.connector.get_ohlcv(self.symbol, mt_tf)

    def get_current_position(self) -> str:
        if self.platform == "binance":
            # Bestehende Logik für Binance (über REST-API)
            endpoint = "/fapi/v2/positionRisk"
            timestamp = int(time.time() * 1000)
            params = {"timestamp": timestamp}
            query_string = urllib.parse.urlencode(params)
            signature = hmac.new(self.connector.secret_key.encode(), query_string.encode(), hashlib.sha256).hexdigest()
            params["signature"] = signature
            headers = {"X-MBX-APIKEY": self.connector.api_key}
            url = f"{self.connector.base_url}{endpoint}?{urllib.parse.urlencode(params)}"

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
        elif self.platform == "metatrader":
            # Hier könntest du die offenen Positionen via mt5.positions_get() abrufen.
            # Für den Moment setzen wir standardmäßig "NONE".
            return "NONE"

    def start(self):
        df = self.fetch_data()
        daily_df = self.fetch_daily_data()
        current_position = self.get_current_position()
        logger.info(f"Aktuelle Position ({self.platform}): {current_position}")

        # Signalgenerierung
        signal = self.strategy.generate_signal(df, daily_df, current_position=current_position)
        logger.info(f"Generiertes Signal: {signal}")

        # Verhindere doppelte Orders
        if (current_position == "LONG" and signal == "BUY") or (current_position == "SHORT" and signal == "SELL"):
            logger.warning(f"Signal {signal} unterdrückt – bereits eine offene {current_position}-Position!")
            return

        if signal != "HOLD":
            entry_price = df['close'].iloc[-1]
            # Stop-Loss und Take-Profit (hier als einfacher Prozentsatz; später evtl. anpassen)
            stop_loss_price = entry_price * (1 - self.stop_loss_pct) if signal == "BUY" else entry_price * (1 + self.stop_loss_pct)
            take_profit_price = entry_price * (1 + self.take_profit_pct) if signal == "BUY" else entry_price * (1 - self.take_profit_pct)

            if self.platform == "binance":
                from order_execution import execute_order
                execute_order(self.connector, self.symbol, signal, entry_price, stop_loss_price, take_profit_price)
            elif self.platform == "metatrader":
                import MetaTrader5 as mt5
                order_type = mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL
                volume = 0.1  # Platzhalter – hier sollte die Lot-Größe basierend auf deinem Risikomanagement berechnet werden
                result = self.connector.execute_order(self.symbol, order_type, volume)
                logger.info(f"MetaTrader Order-Ergebnis: {result}")
