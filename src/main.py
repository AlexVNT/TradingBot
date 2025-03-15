#src/main.py
import os
import time
from dotenv import load_dotenv
import yaml
from src.bot import TradingBot
from src.utils import logger

load_dotenv()
def load_config(config_path="config/config.yaml"):
    if not os.path.exists(config_path):
        print(f"⚠ Warnung: Konfigurationsdatei {config_path} nicht gefunden!")
        return {}
    try:
        with open(config_path, 'r') as file:
            return yaml.safe_load(file) or {}
    except Exception as e:
        print(f"❌ Fehler beim Laden der Konfiguration: {e}")
        return {}

config = load_config()
if not config:
    print("⚠ Kein gültiges Config-File gefunden. Bot wird nicht gestartet.")
    exit()

def main():
    bot = TradingBot(config)
    logger.info("🚀 Starte TradingBot...")
    while True:
        try:
            bot.start()
            time.sleep(300)  # 5 Minuten
        except Exception as e:
            logger.error(f"❌ Fehler beim Ausführen des Bots: {e}")
            time.sleep(60)  # Kurze Pause nach Fehler

if __name__ == "__main__":
    main()
