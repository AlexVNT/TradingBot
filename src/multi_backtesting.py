# src/multi_backtesting.py
import os
import yaml
import datetime
import pandas as pd
from backtesting_improved import run_backtest, calculate_performance, visualize_backtest
from strategy import CompositeStrategy
from utils import logger

# Wir gehen davon aus, dass download_historical_data für Binance vorhanden ist
from historical_data import download_historical_data

# Für Metatrader importieren wir den Connector
from metatrader_connector import MetaTraderConnector
import MetaTrader5 as mt5

def save_backtest_summary(summaries, filename="results/backtest_summary.csv"):
    """
    Speichert die Backtest-Zusammenfassung als CSV-Datei.
    """
    os.makedirs("results", exist_ok=True)
    df_summary = pd.DataFrame(summaries)
    df_summary.to_csv(filename, index=False)
    logger.info(f"Backtest-Zusammenfassung in {filename} gespeichert.")

def main():
    with open("config/config.yaml", "r") as file:
        config = yaml.safe_load(file)
        
    # Bestimme die aktive Plattform
    if config["platforms"].get("metatrader") is True:
        platform = "metatrader"
    elif config["platforms"].get("binance") is True:
        platform = "binance"
    else:
        logger.error("Keine Plattform aktiviert!")
        return
    
    # Lese die Liste der Symbole
    if platform == "binance":
        symbols = config['trading']['binance'].get("symbols", [config['trading'].get("trade_pair", "BTCUSDT")])
    else:  # Metatrader – hier gehen wir von einem einzigen Symbol aus
        symbols = [config['trading']['metatrader']["symbol"]]
    
    start_date = "2024-01-01"  # Beispielstartdatum
    summaries = []
    
    for symbol in symbols:
        logger.info(f"Backtesting für {symbol} wird gestartet...")
        if platform == "binance":
            timeframe = config['trading']['binance']['timeframe']
            higher_tf = config['trading']['binance'].get("higher_timeframe", "1d")
            df_hourly = download_historical_data(symbol, timeframe, start_date)
            df_daily = download_historical_data(symbol, higher_tf, start_date)
        elif platform == "metatrader":
            trade_conf = config['trading']['metatrader']
            timeframe = trade_conf["timeframe"]
            higher_tf = trade_conf["higher_timeframe"]
            tf_mapping = {
                "M1": mt5.TIMEFRAME_M1,
                "M5": mt5.TIMEFRAME_M5,
                "M15": mt5.TIMEFRAME_M15,
                "M30": mt5.TIMEFRAME_M30,
                "H1": mt5.TIMEFRAME_H1,
                "H4": mt5.TIMEFRAME_H4,
                "D1": mt5.TIMEFRAME_D1,
                "W1": mt5.TIMEFRAME_W1,
                "MN1": mt5.TIMEFRAME_MN1
            }
            connector = MetaTraderConnector()
            mt_tf = tf_mapping.get(timeframe.upper(), mt5.TIMEFRAME_H1)
            mt_higher_tf = tf_mapping.get(higher_tf.upper(), mt5.TIMEFRAME_D1)
            df_hourly = connector.get_ohlcv(symbol, mt_tf, limit=1000)
            df_daily = connector.get_ohlcv(symbol, mt_higher_tf, limit=500)
            print("Spalten in df_daily:", df_daily.columns)

        
        strategy = CompositeStrategy(config)
        df_sim, trades = run_backtest(df_hourly, strategy, config, daily_df=df_daily, account_balance=100000, symbol=symbol)
        perf = calculate_performance(df_sim, trades)
        logger.info(f"Performance für {symbol}: {perf}")
        visualize_backtest(df_sim, trades, title=f"Backtest: {symbol}")
        
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
    
    save_backtest_summary(summaries)

if __name__ == "__main__":
    main()
