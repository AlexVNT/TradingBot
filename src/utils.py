# src/utils.py
import logging
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')

def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        filename=os.path.join(os.path.dirname(__file__), '..', 'data', 'logs', 'tradingbot.log')
    )
    return logging.getLogger('TradingBot')

logger = setup_logger()