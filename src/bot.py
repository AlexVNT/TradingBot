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
        # Liste von Symbolen; Fallback: trade_pair oder "BTCUSDT"
        self.symbols = config['trading'].get("symbols", [config['trading'].get("trade_pair", "BTCUSDT")])

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

        # ✅ Wähle den richtigen Binance-Connector (Live oder Testnet)
        self.use_testnet = config['trading']['use_testnet']
        self.connector = BinanceTestnetConnector() if self.use_testnet else BinanceConnector()
        print(f"🚀 {'Testnet' if self.use_testnet else 'Live'}-Connector aktiviert!")

        # Basis-URL für Binance Futures:
        self.base_url = self.connector.base_url

        # Handelsparameter:
        self.timeframe = config['trading']['timeframe']
        self.higher_timeframe = config['trading'].get('higher_timeframe', '1d')

        # Risikomanagement aus Config
        self.stop_loss_pct = config['risk_management'].get('stop_loss_pct', 0.05)
        self.take_profit_pct = config['risk_management'].get('take_profit_pct', 0.10)

        # ✅ Erstelle Strategie-Instanz
        self.strategy = CompositeStrategy(config)

    def fetch_data(self, symbol: str) -> pd.DataFrame:
        """Lädt OHLCV-Daten für das angegebene Symbol vom Binance Futures Testnet oder Live."""
        return self.connector.get_ohlcv(symbol, self.timeframe)

    def fetch_daily_data(self, symbol: str) -> pd.DataFrame:
        """Lädt OHLCV-Daten für den höheren Timeframe (z. B. 1d) des angegebenen Symbols."""
        return self.connector.get_ohlcv(symbol, self.higher_timeframe)

    def get_current_position(self, symbol: str) -> str:
        """Ruft den aktuellen Positionsstatus für das angegebene Symbol ab (LONG, SHORT, NONE)."""
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
            # Vergleiche direkt mit dem Symbol, z. B. "BTCUSDT"
            for pos in data:
                if pos.get("symbol") == symbol:
                    pos_amt = float(pos.get("positionAmt", 0))
                    if pos_amt > 0:
                        return "LONG"
                    elif pos_amt < 0:
                        return "SHORT"
            return "NONE"
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der aktuellen Position für {symbol}: {e}")
            return "NONE"
        
    def get_current_price(self, symbol: str) -> float:
        """Holt den aktuellen Marktpreis für das gegebene Symbol."""
        endpoint = "/fapi/v1/ticker/price"
        params = {"symbol": symbol}
        
        try:
            response = self.connector.session.get(f"{self.base_url}{endpoint}", params=params)
            data = response.json()
            return float(data["price"])
        except Exception as e:
            logger.error(f"Fehler beim Abrufen des aktuellen Preises für {symbol}: {e}")
            return None

    def start_for_symbol(self, symbol: str):
        """Führt den Handelsprozess für ein einzelnes Symbol durch."""
        logger.info(f"--- Starte Handel für {symbol} ---")
        df = self.fetch_data(symbol)
        daily_df = self.fetch_daily_data(symbol)
        current_position = self.get_current_position(symbol)
        logger.info(f"Aktuelle Position für {symbol}: {current_position}")

        if not current_position:
            logger.error(f"❌ Fehler: Konnte aktuelle Position für {symbol} nicht abrufen!")
            current_position = "NONE"

        # Generiere das Signal basierend auf der Strategie
        signal = self.strategy.generate_signal(df, daily_df, current_position=current_position, symbol=symbol)
        logger.info(f"Generiertes Signal für {symbol}: {signal}")

        # 🚨 Doppelte Orders verhindern 🚨
        if (current_position == "LONG" and signal == "BUY") or (current_position == "SHORT" and signal == "SELL"):
            logger.warning(f"⚠ Signal {signal} für {symbol} unterdrückt – bereits eine offene {current_position}-Position!")
            return

        if signal != "HOLD":
            entry_price = df['close'].iloc[-1]
            stop_loss_price = entry_price * (1 - self.stop_loss_pct) if signal == "BUY" else entry_price * (1 + self.stop_loss_pct)
            take_profit_price = entry_price * (1 + self.take_profit_pct) if signal == "BUY" else entry_price * (1 - self.take_profit_pct)
            try:
                leverage = config['trading'].get("leverage", 10)
                execute_order(
                    self.connector,
                    symbol,  # Symbol wird direkt übergeben, z. B. "BTCUSDT"
                    signal,
                    entry_price,
                    stop_loss_price,
                    take_profit_price,
                    leverage
                )
            except Exception as e:
                logger.error(f"❌ Fehler bei Orderausführung für {symbol}: {e}")

    def start_all(self):
        """Iteriert über alle konfigurierten Symbole und führt den Handelsprozess aus."""
        for symbol in self.symbols:
            self.start_for_symbol(symbol)