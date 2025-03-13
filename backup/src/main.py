import os
import time
from dotenv import load_dotenv
import yaml
from bot import TradingBot
from utils import logger

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
    
    # Bot läuft 24 Stunden (oder passe run_duration an)
    start_time = time.time()
    run_duration = 24 * 60 * 60  # 24 Stunden in Sekunden
    end_time = start_time + run_duration
    
    while time.time() < end_time:
        try:
            bot.start()
        except Exception as e:
            logger.error(f"❌ Fehler beim Ausführen des Bots: {e}")
        # Warte 5 Minuten zwischen den Durchläufen
        time.sleep(300)

if __name__ == "__main__":
    main()
