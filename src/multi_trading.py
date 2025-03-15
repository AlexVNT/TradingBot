# src/multi_trading.py
import time
import yaml
from src.bot import TradingBot
from src.utils import logger

def main():
    with open("config/config.yaml", "r") as file:
        config = yaml.safe_load(file)
    bot = TradingBot(config)
    
    # Endlosschleife (oder eine andere Laufzeitsteuerung) – z.B. alle 5 Minuten:
    while True:
        logger.info("Starte Handelsrunde für alle Symbole...")
        bot.start_all()
        logger.info("Handelsrunde abgeschlossen. Warte 5 Minuten bis zur nächsten Runde...")
        time.sleep(300)

if __name__ == "__main__":
    main()
