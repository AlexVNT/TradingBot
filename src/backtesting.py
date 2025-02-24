# src/backtesting.py
import pandas as pd
from src.strategy import CompositeStrategy
from src.utils import logger

def run_backtest(data_file, config):
    # Lese historische Daten ein (z. B. als CSV)
    df = pd.read_csv(data_file, parse_dates=['timestamp'], index_col='timestamp')
    strategy = CompositeStrategy(config)
    df['signal'] = df.apply(lambda row: strategy.generate_signal(df), axis=1)
    logger.info("Backtest abgeschlossen.")
    return df

if __name__ == "__main__":
    # Beispiel: Führe den Backtest für ein bestimmtes Symbol und Timeframe durch
    config = {
        'strategy': {
            'rsi_period': 14,
            'rsi_overbought': 70,
            'rsi_oversold': 30
        }
    }
    backtest_df = run_backtest("data/historical/BTC_USDT_1h.csv", config)
    print(backtest_df.tail())
