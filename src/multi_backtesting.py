import os
import yaml
import datetime
import pandas as pd
from historical_data import download_historical_data
from backtesting_improved import run_backtest, calculate_performance, visualize_backtest
from strategy import CompositeStrategy
from utils import logger

def save_backtest_summary(summaries, filename="results/backtest_summary.csv"):
    """
    Speichert die Backtest-Zusammenfassung als CSV-Datei.
    :param summaries: Liste von Dictionaries, in denen die wichtigsten Metriken enthalten sind.
    :param filename: Dateiname für die Zusammenfassung.
    """
    os.makedirs("results", exist_ok=True)
    df_summary = pd.DataFrame(summaries)
    df_summary.to_csv(filename, index=False)
    logger.info(f"Backtest-Zusammenfassung in {filename} gespeichert.")

def main():
    with open("config/config.yaml", "r") as file:
        config = yaml.safe_load(file)
        
    # Lese die Liste der Symbole (Fallback: trade_pair oder "BTCUSDT")
    symbols = config['trading'].get("symbols", [config['trading'].get("trade_pair", "BTCUSDT")])
    start_date = "2024-01-01"  # Starte mit historischen Daten ab 2024
    summaries = []
    
    for symbol in symbols:
        logger.info(f"Backtesting für {symbol} wird gestartet...")
        # Lade historische Daten direkt von Binance:
        df_hourly = download_historical_data(symbol, config['trading']['timeframe'], start_date)
        df_daily = download_historical_data(symbol, config['trading'].get("higher_timeframe", "1d"), start_date)
        
        strategy = CompositeStrategy(config)
        df_sim, trades = run_backtest(df_hourly, strategy, config, daily_df=df_daily, account_balance=100000)
        perf = calculate_performance(df_sim, trades)
        logger.info(f"Performance für {symbol}: {perf}")
        visualize_backtest(df_sim, trades, title=f"Backtest: {symbol}")
        
        # Erstelle eine Zusammenfassung mit den wichtigsten Metriken
        summary = {
            "symbol": symbol,
            "total_profit": perf.get("total_profit", 0),
            "num_trades": perf.get("num_trades", 0),
            "win_rate": perf.get("win_rate", 0),
            "profit_factor": perf.get("profit_factor", 0),
            "max_drawdown": perf.get("max_drawdown", 0),
            "sharpe": perf.get("sharpe", 0),
            "timestamp": datetime.datetime.now().isoformat()
        }
        summaries.append(summary)
    
    # Speichere alle Zusammenfassungen in einer CSV-Datei
    save_backtest_summary(summaries)

if __name__ == "__main__":
    main()
