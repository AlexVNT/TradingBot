# src/multi_backtesting.py
import os
import yaml
import datetime
import pandas as pd
from backtesting_improved import run_backtest, calculate_performance, visualize_backtest
from strategy import CompositeStrategy
from utils import logger
from historical_data import download_historical_data
from metatrader_connector import MetaTraderConnector
import MetaTrader5 as mt5

def save_backtest_summary(summaries, filename="results/backtest_summary.csv"):
    """Speichert die Backtest-Zusammenfassung in einer CSV-Datei."""
    try:
        os.makedirs("results", exist_ok=True)
        df_summary = pd.DataFrame(summaries)
        df_summary.to_csv(filename, index=False)
        logger.info(f"Backtest-Zusammenfassung in {filename} gespeichert.")
    except Exception as e:
        logger.error(f"Fehler beim Speichern der Zusammenfassung: {e}")

def save_simplified_log(summaries, filename="results/simplified_log.txt"):
    """Speichert die Backtest-Ergebnisse in einem vereinfachten Log-Format."""
    try:
        os.makedirs("results", exist_ok=True)
        with open(filename, "w") as f:
            for summary in summaries:
                symbol = summary["symbol"]
                total_profit = summary["total_profit"]
                profit_factor = summary["profit_factor"]
                num_trades = summary["num_trades"]
                win_rate = summary["win_rate"]
                wins = int(win_rate * num_trades)
                max_drawdown = summary["max_drawdown"]
                sharpe = summary["sharpe"]
                # Schreibe das vereinfachte Format
                f.write(f"{symbol}:\n")
                f.write(f"Profit: {total_profit:.5f} | Profitfactor: {profit_factor:.2f} | Wins: {wins} | Trades: {num_trades} | Drawdown: {max_drawdown:.5f} | Sharp: {sharpe:.2f}\n\n")
        logger.info(f"Vereinfachtes Log in {filename} gespeichert.")
    except Exception as e:
        logger.error(f"Fehler beim Speichern des vereinfachten Logs: {e}")

def load_data(platform, symbol, config):
    """Lädt historische Daten für die gegebene Plattform und Symbol."""
    if platform == "binance":
        timeframe = config['trading']['binance']['timeframe']
        higher_tf = config['trading']['binance'].get("higher_timeframe", "1d")
        start_date = "2024-01-01"
        df_hourly = download_historical_data(symbol, timeframe, start_date)
        df_higher = download_historical_data(symbol, higher_tf, start_date)
        if df_hourly is None or df_higher is None:
            logger.error(f"Datenabruf für {symbol} (Binance) fehlgeschlagen.")
            return None, None
    elif platform == "metatrader":
        trade_conf = config['trading']['metatrader']
        timeframe = trade_conf["timeframe"]
        higher_tf = trade_conf["higher_timeframe"]
        tf_mapping = {
            "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1, "MN1": mt5.TIMEFRAME_MN1
        }
        connector = MetaTraderConnector()
        mt_tf = tf_mapping.get(timeframe.upper(), mt5.TIMEFRAME_H1)
        mt_higher_tf = tf_mapping.get(higher_tf.upper(), mt5.TIMEFRAME_H4)
        df_hourly = connector.get_ohlcv(symbol, mt_tf, limit=1000)
        df_higher = connector.get_ohlcv(symbol, mt_higher_tf, limit=2000)

        if df_hourly is None or df_higher is None or df_hourly.empty or df_higher.empty:
            logger.error(f"Datenabruf für {symbol} (MetaTrader) fehlgeschlagen.")
            return None, None
        
        # Zusätzliche Validierung der H4-Daten
        if len(df_higher) < 50 or df_higher['close'].isnull().any():
            logger.warning(f"Unzureichende oder ungültige H4-Daten für {symbol}: {len(df_higher)} Bars, NaN-Werte: {df_higher['close'].isnull().sum()}")
            return None, None
        logger.debug(f"H4-Daten: {df_higher.head()}")

        df_hourly = df_hourly.rename(columns={"tick_volume": "volume"})
        df_higher = df_higher.rename(columns={"tick_volume": "volume"})
        logger.info(f"MetaTrader-Daten geladen: {len(df_hourly)} Stunden, {len(df_higher)} {higher_tf}-Bars")
        logger.info(f"Hourly Daten Zeitraum: {df_hourly.index[0]} bis {df_hourly.index[-1]}")
        logger.info(f"{higher_tf} Daten Zeitraum: {df_higher.index[0]} bis {df_higher.index[-1]}")

    return df_hourly, df_higher

def main():
    """Hauptfunktion zum Ausführen des Multi-Backtests."""
    try:
        with open("config/config.yaml", "r") as file:
            config = yaml.safe_load(file)
    except Exception as e:
        logger.error(f"Fehler beim Laden von config.yaml: {e}")
        return

    if config["platforms"].get("metatrader", False):
        platform = "metatrader"
    elif config["platforms"].get("binance", False):
        platform = "binance"
    else:
        logger.error("Keine Plattform aktiviert in config.yaml!")
        return
    
    # Erweiterte Liste von Symbolen für MetaTrader
    if platform == "metatrader":
        symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
    else:
        symbols = config['trading']['binance'].get("symbols", [config['trading'].get("trade_pair", "BTCUSDT")])

    summaries = []
    
    for symbol in symbols:
        logger.info(f"Backtesting für {symbol} wird gestartet...")
        
        df_hourly, df_higher = load_data(platform, symbol, config)
        if df_hourly is None or df_higher is None:
            logger.error(f"Backtest für {symbol} abgebrochen wegen fehlender Daten.")
            continue

        try:
            strategy = CompositeStrategy(config)
            df_sim, trades = run_backtest(df_hourly, strategy, config, df_higher=df_higher, symbol=symbol)
            if df_sim.empty or not trades:
                logger.warning(f"Kein Ergebnis für {symbol} – keine Trades generiert.")
                continue

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

        except Exception as e:
            logger.error(f"Fehler beim Backtest für {symbol}: {e}")
            continue
    
    if summaries:
        save_backtest_summary(summaries)
        save_simplified_log(summaries)  # Vereinfachtes Log speichern
    else:
        logger.warning("Keine Backtest-Ergebnisse zum Speichern.")

if __name__ == "__main__":
    main()