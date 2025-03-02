import os
import time
from dotenv import load_dotenv
import yaml
from bot import TradingBot
from utils import logger
from binance_connector import BinanceConnector, BinanceTestnetConnector
from order_execution import execute_order

# Lade Umgebungsvariablen aus .env
load_dotenv()

print("🚀 Trading-Bot gestartet!")

# Konfiguration laden
def load_config(config_path="config/config.yaml"):
    if not os.path.exists(config_path):
        print(f"⚠ Warnung: Konfigurationsdatei {config_path} nicht gefunden! Es werden Standardwerte genutzt.")
        return {}
    try:
        with open(config_path, 'r') as file:
            return yaml.safe_load(file) or {}
    except yaml.YAMLError as e:
        print(f"❌ Fehler beim Laden der Konfigurationsdatei: {e}")
        return {}

config = load_config()
if not config:
    print("⚠ Kein gültiges Config-File gefunden. Bot wird nicht gestartet.")
    exit()

# Wähle den richtigen Binance Connector (Testnet oder Live)
use_testnet = config.get("trading", {}).get("use_testnet", True)
connector = BinanceTestnetConnector() if use_testnet else BinanceConnector()
logger.info(f"🌐 Verbunden mit Binance {'Testnet' if use_testnet else 'Live'}")

# Prüfe Guthaben (angepasst für Binance Futures)
try:
    account_info = connector.get_account_info()
    usdt_balance = next((a["walletBalance"] for a in account_info["assets"] if a["asset"] == "USDT"), "❌ Kein USDT-Guthaben gefunden!")
    print(f"💰 {'Testnet' if use_testnet else 'Live'}-Guthaben: {usdt_balance} USDT")
except Exception as e:
    print(f"❌ Fehler beim Abrufen des Guthabens: {e}")

def main():
    bot = TradingBot(config)
    logger.info("🚀 Starte TradingBot...")

    # Bot läuft 24 Stunden lang (oder passe run_duration nach Bedarf an)
    start_time = time.time()
    run_duration = 24 * 60 * 60  # 24 Stunden in Sekunden
    end_time = start_time + run_duration

    while time.time() < end_time:
        try:
            bot.start_all()


            # 📌 Hole Marktdaten & Position
            df = bot.fetch_data()
            df_daily = bot.fetch_daily_data()
            current_position = bot.get_current_position()

            # 📌 Generiere Trading-Signal
            trade_signal = bot.strategy.generate_signal(df, df_daily, current_position)

            # ❌ 🚨 Verhindere doppelte Orders 🚨 ❌
            if (current_position == "LONG" and trade_signal == "BUY") or (current_position == "SHORT" and trade_signal == "SELL"):
                logger.warning(f"⚠ Signal {trade_signal} unterdrückt – bereits eine offene {current_position}-Position!")
                continue  # Überspringe diesen Durchlauf

            if trade_signal and trade_signal != "HOLD":
                # 📌 Einstiegspreis ermitteln
                entry_price = df['close'].iloc[-1]  # Letzter Schlusskurs

                # 📌 Stop-Loss & Take-Profit berechnen
                stop_loss_price = entry_price * 0.99 if trade_signal == "BUY" else entry_price * 1.01
                take_profit_price = entry_price * 1.02 if trade_signal == "BUY" else entry_price * 0.98

                # ✅ Order ausführen
                execute_order(
                    bot.connector,  # 🔥 Hier wird der `bot.connector` genutzt
                    bot.symbol,  # 🔥 Symbol aus der Config
                    trade_signal,
                    entry_price,
                    stop_loss_price,
                    take_profit_price
                )

        except Exception as e:
            logger.error(f"❌ Fehler beim Ausführen des Bots: {e}")

        # Warte 300 Sekunden (5 Minuten) zwischen den Durchläufen
        time.sleep(300)

if __name__ == "__main__":
    main()
