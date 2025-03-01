import os
import time
import requests
import pandas as pd
import urllib.parse
import hashlib
import hmac
import yaml
from dotenv import load_dotenv
from binance_connector import BinanceConnector, BinanceTestnetConnector
from strategy import CompositeStrategy
from order_execution import execute_order
from utils import logger

# ✅ Lade Umgebungsvariablen aus `.env`
load_dotenv(dotenv_path="c:/TradingBot/.env")

# Konfigurationsdatei laden
CONFIG_PATH = "config/config.yaml"

def load_config():
    """Lädt die Konfigurationsdatei."""
    with open(CONFIG_PATH, "r") as file:
        return yaml.safe_load(file)

config = load_config()

class TradingBot:
    def __init__(self, config):
        self.config = config
        self.symbol = config['trading']['symbol'].replace("/", "")  # Entfernt "/"

        # Lade API-Keys je nach Testnet oder Live
        if config['trading']['use_testnet']:
            self.api_key = os.getenv("BINANCE_TESTNET_API_KEY")
            self.secret_key = os.getenv("BINANCE_TESTNET_SECRET_KEY")
            print("🔧 Testnet API-Keys geladen.")
        else:
            self.api_key = os.getenv("BINANCE_API_KEY")
            self.secret_key = os.getenv("BINANCE_SECRET_KEY")
            print("🔧 Live API-Keys geladen.")

        # Fehlerprüfung
        if not self.api_key or not self.secret_key:
            raise ValueError("❌ API-Schlüssel nicht gefunden! Stelle sicher, dass `.env` korrekt konfiguriert ist.")

        # 🚨 Fehlerprüfung: Falls Keys fehlen, Programm abbrechen
        if not self.api_key or not self.secret_key:
            raise ValueError("❌ API-Schlüssel nicht gefunden! Stelle sicher, dass `.env` korrekt konfiguriert ist.")

        # ✅ Wähle den richtigen Binance-Connector (Live oder Testnet)
        self.use_testnet = config['trading']['use_testnet']
        self.connector = BinanceTestnetConnector() if self.use_testnet else BinanceConnector()
        print(f"🚀 {'Testnet' if self.use_testnet else 'Live'}-Connector aktiviert!")

        # Basis-URL für Binance Futures:
        self.base_url = self.connector.base_url

        # Handelsparameter:
        self.symbol = config['trading']['symbol']
        self.timeframe = config['trading']['timeframe']
        self.higher_timeframe = config['trading'].get('higher_timeframe', '1d')

        # Risikomanagement aus Config
        self.stop_loss_pct = config['risk_management'].get('stop_loss_pct', 0.05)
        self.take_profit_pct = config['risk_management'].get('take_profit_pct', 0.10)

        # ✅ Erstelle Strategie-Instanz
        self.strategy = CompositeStrategy(config)

    def fetch_data(self) -> pd.DataFrame:
        """Lädt OHLCV-Daten vom Binance Futures Testnet oder Live."""
        return self.connector.get_ohlcv(self.symbol, self.timeframe)  # FIXED ✅

    def fetch_daily_data(self) -> pd.DataFrame:
        """Lädt OHLCV-Daten für den höheren Timeframe (z. B. 1d)."""
        return self.connector.get_ohlcv(self.symbol, self.higher_timeframe)  # FIXED ✅

    def get_current_position(self) -> str:
        """Ruft den aktuellen Positionsstatus für das gehandelte Symbol ab (LONG, SHORT, NONE)."""
        endpoint = "/fapi/v2/positionRisk"
        timestamp = int(time.time() * 1000)
        params = {"timestamp": timestamp}
        query_string = urllib.parse.urlencode(params)
        signature = hmac.new(self.secret_key.encode(), query_string.encode(), hashlib.sha256).hexdigest()
        params["signature"] = signature
        headers = {"X-MBX-APIKEY": self.api_key}
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
        
    def get_current_price(self, symbol: str) -> float:
        """Holt den aktuellen Marktpreis für das gegebene Symbol."""
        endpoint = "/fapi/v1/ticker/price"
        params = {"symbol": symbol.replace("/", "")}
        
        try:
            response = self.connector.session.get(f"{self.base_url}{endpoint}", params=params)
            data = response.json()
            return float(data["price"])
        except Exception as e:
            logger.error(f"Fehler beim Abrufen des aktuellen Preises für {symbol}: {e}")
            return None

    def start(self):
        # Hole 1h-Daten:
        df = self.fetch_data()
        # Hole Daily-Daten:
        daily_df = self.fetch_daily_data()
        # Bestimme den aktuellen Positionsstatus (über REST-API)
        current_position = self.get_current_position()
        logger.info(f"Aktuelle Position: {current_position}")

        if not current_position:  # Falls None oder Fehler auftritt
            logger.error("❌ Fehler: Konnte aktuelle Position nicht abrufen!")
            current_position = "NONE"  # Standardwert setzen

        logger.info(f"Aktuelle Position: {current_position}")

        # Generiere das Signal basierend auf Strategie
        signal = self.strategy.generate_signal(df, daily_df, current_position=current_position)
        logger.info(f"Generiertes Signal: {signal}")

        # 🚨 Doppelte Orders verhindern 🚨
        if (current_position == "LONG" and signal == "BUY") or (current_position == "SHORT" and signal == "SELL"):
            logger.warning(f"⚠ Signal {signal} unterdrückt – bereits eine offene {current_position}-Position!")
            return  # Beendet die Funktion, damit keine Order platziert wird.

        if signal != "HOLD":
            # ✅ Berechnung von TP/SL
            entry_price = df['close'].iloc[-1]
            stop_loss_price = entry_price * (1 - self.stop_loss_pct) if signal == "BUY" else entry_price * (1 + self.stop_loss_pct)
            take_profit_price = entry_price * (1 + self.take_profit_pct) if signal == "BUY" else entry_price * (1 - self.take_profit_pct)

            # 🚀 Order ausführen
            try:
                execute_order(
                    self.connector,
                    self.symbol,  # ✅ Symbol ohne "/"
                    signal,
                    entry_price,
                    stop_loss_price,
                    take_profit_price
                )
            except Exception as e:
                logger.error(f"❌ Fehler bei Orderausführung: {e}")
