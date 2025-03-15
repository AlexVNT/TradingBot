import os
import yaml
import datetime
import pandas as pd
from src.backtesting_improved import run_backtest, calculate_performance, visualize_backtest
from src.strategy import CompositeStrategy
from src.utils import logger
from src.historical_data import download_historical_data
from src.metatrader_connector import MetaTraderConnector
import MetaTrader5 as mt5

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')

def load_config():
    with open(CONFIG_PATH, "r") as file:
        return yaml.safe_load(file)

config = load_config()

def load_config(config_path="config/config.yaml"):
    with open(config_path, "r") as file:
        return yaml.safe_load(file)

def load_best_params(params_path="results/tuning/best_params.yaml"):
    with open(params_path, "r") as file:
        return yaml.safe_load(file)

def save_backtest_summary(summaries, filename="results/backtest_summary.csv"):
    df_summary = pd.DataFrame(summaries)
    # Tuning-Parameter hinzufügen
    df_summary["atr_sl_multiplier"] = [config["trading"][s["platform"]]["symbols"][s["symbol"]]["atr_sl_multiplier"] for s in summaries]
    df_summary["atr_tp_multiplier"] = [config["trading"][s["platform"]]["symbols"][s["symbol"]]["atr_tp_multiplier"] for s in summaries]
    df_summary["rsi_period"] = config["strategy"]["rsi_period"]
    df_summary.to_csv(filename, index=False)
    logger.info(f"Backtest-Zusammenfassung in {filename} gespeichert.")
    
def save_simplified_log(summaries, filename="results/simplified_log.txt"):
    os.makedirs("results", exist_ok=True)
    with open(filename, "w") as f:
        for summary in summaries:
            f.write(f"{summary['platform']}/{summary['symbol']}:\n")
            f.write(f"Profit: {summary['total_profit']:.5f} | Profitfactor: {summary['profit_factor']:.2f} | "
                    f"Wins: {int(summary['win_rate'] * summary['num_trades'])} | Trades: {summary['num_trades']} | "
                    f"Drawdown: {summary['max_drawdown']:.5f} | Sharpe: {summary['sharpe']:.2f}\n\n")
    logger.info(f"Vereinfachtes Log in {filename} gespeichert.")

def generate_web_snippet(summaries, config):
    html = "<html><body><h1>Backtest Ergebnisse</h1>"
    html += "<h2>Statistiken</h2><table border='1'>"
    html += "<tr><th>Plattform/Symbol</th><th>Profit</th><th>Trades</th><th>Win Rate</th><th>Max Drawdown</th><th>Sharpe</th><th>SL Multiplier</th><th>TP Multiplier</th><th>RSI Period</th></tr>"
    for summary in summaries:
        platform_symbol = f"{summary['platform']}/{summary['symbol']}"
        profit = summary["total_profit"]
        num_trades = summary["num_trades"]
        win_rate = summary["win_rate"]
        max_drawdown = summary["max_drawdown"]
        sharpe = summary["sharpe"]
        sl_mult = config["trading"][summary["platform"]]["symbols"][summary["symbol"]]["atr_sl_multiplier"]
        tp_mult = config["trading"][summary["platform"]]["symbols"][summary["symbol"]]["atr_tp_multiplier"]
        rsi_period = config["strategy"]["rsi_period"]
        html += f"<tr><td>{platform_symbol}</td><td>{profit:.2f}</td><td>{num_trades}</td><td>{win_rate:.2%}</td><td>{max_drawdown:.2%}</td><td>{sharpe:.2f}</td><td>{sl_mult}</td><td>{tp_mult}</td><td>{rsi_period}</td></tr>"
    html += "</table>"

    # Tuning-Fortschritt
    html += "<h2>Tuning-Fortschritt</h2><table border='1'>"
    html += "<tr><th>Plattform/Symbol</th><th>Best Profit</th><th>SL Multiplier</th><th>TP Multiplier</th></tr>"
    best_params = load_config("results/tuning/best_params.yaml")  # Lade Tuning-Ergebnisse
    for platform in best_params:
        for symbol, params in best_params[platform].items():
            if params:  # Nur wenn Tuning-Daten vorhanden
                platform_symbol = f"{platform}/{symbol}"
                best_profit = next((s["total_profit"] for s in summaries if s["platform"] == platform and s["symbol"] == symbol), "N/A")
                sl_mult = params["atr_sl_multiplier"]
                tp_mult = params["atr_tp_multiplier"]
                html += f"<tr><td>{platform_symbol}</td><td>{best_profit}</td><td>{sl_mult}</td><td>{tp_mult}</td></tr>"
    html += "</table>"

    html += "</body></html>"
    with open("results/backtest_results.html", "w") as file:
        file.write(html)
    logger.info("HTML-Snippet in 'results/backtest_results.html' gespeichert.")
     
# Nur der relevante Teil von multi_backtesting.py
def load_data(platform, symbol, config):
    if platform == "binance":
        timeframe = config['trading']['binance']['timeframe']
        higher_tf = config['trading']['binance'].get("higher_timeframe", "1d")
        start_date = "2024-07-01"  # Zurück auf aktuelleren Zeitraum für Konsistenz
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
        df_hourly = connector.get_ohlcv(symbol, mt_tf, limit=1000)  # Kein Shift für aktuelle Daten
        df_higher = connector.get_ohlcv(symbol, mt_higher_tf, limit=1000)
        if df_hourly is None or df_higher is None or df_hourly.empty or df_higher.empty:
            logger.error(f"Datenabruf für {symbol} (MetaTrader) fehlgeschlagen.")
            return None, None
        df_hourly = df_hourly.rename(columns={"tick_volume": "volume"})
        df_higher = df_higher.rename(columns={"tick_volume": "volume"})
        logger.info(f"MetaTrader-Daten geladen: {len(df_hourly)} Stunden, {len(df_higher)} {higher_tf}-Bars")
    
    return df_hourly, df_higher

def main():
    config = load_config()
    best_params = load_best_params()
    
    platforms = []
    if config["platforms"]["binance"]:
        platforms.append("binance")
    if config["platforms"]["metatrader"]:
        platforms.append("metatrader")
    
    summaries = []
    for platform in platforms:
        symbols = config["trading"][platform]["symbols"].keys()
        for symbol in symbols:
            logger.info(f"Backtesting für {platform}/{symbol} wird gestartet...")
            df_hourly, df_higher = load_data(platform, symbol, config)
            if df_hourly is None or df_higher is None:
                logger.error(f"Backtest für {platform}/{symbol} abgebrochen wegen fehlender Daten.")
                continue
            
            # Beste Parameter anwenden, falls verfügbar
            temp_config = config.copy()
            if platform in best_params and symbol in best_params[platform]:
                temp_config["strategy"]["atr_sl_multiplier"] = best_params[platform][symbol]["atr_sl_multiplier"]
                temp_config["strategy"]["atr_tp_multiplier"] = best_params[platform][symbol]["atr_tp_multiplier"]
                logger.info(f"{platform}/{symbol}: Verwende optimierte Parameter - SL: {best_params[platform][symbol]['atr_sl_multiplier']}, TP: {best_params[platform][symbol]['atr_tp_multiplier']}")
            
            strategy = CompositeStrategy(temp_config, symbol=symbol)
            df_sim, trades = run_backtest(df_hourly, strategy, temp_config, df_higher=df_higher, symbol=symbol, platform=platform)
            if df_sim.empty or not trades:
                logger.warning(f"Kein Ergebnis für {platform}/{symbol} – keine Trades generiert.")
                continue
            
            perf = calculate_performance(df_sim, trades)
            logger.info(f"Performance für {platform}/{symbol}: {perf}")
            visualize_backtest(df_sim, trades, title=f"Backtest: {platform}/{symbol}")
            
            summary = {
                "platform": platform,
                "symbol": symbol,
                "total_profit": perf["total_profit"],
                "num_trades": perf["num_trades"],
                "win_rate": perf["win_rate"],
                "profit_factor": perf["profit_factor"],
                "max_drawdown": perf["max_drawdown"],
                "sharpe": perf["sharpe"],
                "timestamp": datetime.datetime.now().isoformat()
            }
            summaries.append(summary)
    
    if summaries:
        save_backtest_summary(summaries)
        save_simplified_log(summaries)
        generate_web_snippet(summaries, config)

if __name__ == "__main__":
    main()