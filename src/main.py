# src/main.py

import os
import time
from dotenv import load_dotenv
import yaml
from bot import TradingBot
from utils import logger
from binance_client import get_balance

# Lade Umgebungsvariablen
load_dotenv()

print("🚀 Trading-Bot gestartet!")

# Prüfe Guthaben im Binance Futures Testnet
try:
    balance = get_balance()
    print("💰 Testnet Guthaben:", balance)
except Exception as e:
    print("❌ Fehler beim Abrufen des Guthabens:", str(e))

def load_config(config_path="config/config.yaml"):
    """Lädt die Konfigurationsdatei sicher"""
    if not os.path.exists(config_path):
        print(f"⚠ Warnung: Konfigurationsdatei {config_path} nicht gefunden! Es werden Standardwerte genutzt.")
        return {}
    try:
        with open(config_path, 'r') as file:
            return yaml.safe_load(file) or {}
    except yaml.YAMLError as e:
        print(f"❌ Fehler beim Laden der Konfigurationsdatei: {e}")
        return {}

def main():
    config = load_config()
    if not config:
        print("⚠ Kein gültiges Config-File gefunden. Bot wird nicht gestartet.")
        return

    bot = TradingBot(config)
    logger.info("🚀 Starte TradingBot...")

    # Bot soll 24 Stunden lang laufen
    start_time = time.time()
    run_duration = 24 * 60 * 60  # 24 Stunden in Sekunden
    end_time = start_time + run_duration

    while time.time() < end_time:
        try:
            bot.start()
        except Exception as e:
            logger.error(f"Fehler beim Ausführen des Bots: {e}")
        # Warte 60 Sekunden zwischen den Durchläufen; passe diesen Wert nach Bedarf an.
        time.sleep(60)

if __name__ == "__main__":
    main()
