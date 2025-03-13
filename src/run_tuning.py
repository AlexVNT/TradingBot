# src/run_tuning.py
import yaml
import pandas as pd
import datetime
from multi_backtesting import load_data, save_backtest_summary
from strategy import CompositeStrategy
from backtesting_improved import run_backtest, calculate_performance, visualize_backtest
from utils import logger

def main():
    # Lade die Tuning-Parameter
    with open("config/tuning.yaml", "r") as file:
        tuning_configs = yaml.safe_load(file)

    # Lade die Haupt-Konfiguration
    with open("config/config.yaml", "r") as file:
        config = yaml.safe_load(file)

    platform = "metatrader" if config["platforms"].get("metatrader", False) else "binance"
    symbol = config['trading']['metatrader'].get("symbol", "EURUSD")

    summaries = []
    best_summary = None
    best_profit = float('-inf')
    best_df_sim = None
    best_trades = None
    best_tune_name = None
    
    # Lade die Daten einmalig
    df_hourly, df_higher = load_data(platform, symbol, config)
    if df_hourly is None or df_higher is None:
        logger.error(f"Backtest für {symbol} abgebrochen wegen fehlender Daten.")
        return

    # Führe den Backtest für jede Tuning-Konfiguration aus
    for tune in tuning_configs["tuning"]:
        tune_name = tune["name"]
        logger.info(f"Tuning-Konfiguration '{tune_name}' wird getestet...")

        # Aktualisiere die Konfiguration mit den Tuning-Parametern
        config["strategy"]["rsi_period"] = tune["rsi_period"]
        config["strategy"]["rsi_overbought"] = tune["rsi_overbought"]
        config["strategy"]["rsi_oversold"] = tune["rsi_oversold"]
        config["strategy"]["atr_tp_multiplier"] = tune["atr_tp_multiplier"]
        config["strategy"]["atr_sl_multiplier"] = tune["atr_sl_multiplier"]

        try:
            strategy = CompositeStrategy(config)
            df_sim, trades = run_backtest(df_hourly, strategy, config, df_higher=df_higher, symbol=symbol)
            if df_sim.empty or not trades:
                logger.warning(f"Kein Ergebnis für {symbol} unter '{tune_name}' – keine Trades generiert.")
                continue

            perf = calculate_performance(df_sim, trades)
            logger.info(f"Performance für {symbol} unter '{tune_name}': {perf}")
            
            summary = {
                "symbol": symbol,
                "tuning_name": tune_name,
                "total_profit": perf.get("total_profit", 0),
                "num_trades": perf.get("num_trades", 0),
                "win_rate": perf.get("win_rate", 0),
                "profit_factor": perf.get("profit_factor", 0),
                "max_drawdown": perf.get("max_drawdown", 0),
                "sharpe": perf.get("sharpe", 0),
                "timestamp": datetime.datetime.now().isoformat()
            }
            summaries.append(summary)

            # Prüfe, ob dies die beste Konfiguration ist
            if summary["total_profit"] > best_profit:
                best_profit = summary["total_profit"]
                best_summary = summary
                best_df_sim = df_sim
                best_trades = trades
                best_tune_name = tune_name

        except Exception as e:
            logger.error(f"Fehler beim Backtest für {symbol} unter '{tune_name}': {e}")
            continue
    
    # Speichere die Ergebnisse
    if summaries:
        save_backtest_summary(summaries, filename="results/tuning_summary.csv")
    else:
        logger.warning("Keine Backtest-Ergebnisse zum Speichern.")

    # Zeige die Visualisierung für die beste Konfiguration
    if best_summary:
        logger.info(f"Beste Konfiguration: '{best_tune_name}' mit Profit {best_profit}")
        visualize_backtest(best_df_sim, best_trades, title=f"Backtest: {symbol} (Beste Konfiguration: {best_tune_name})")
    else:
        logger.warning("Keine beste Konfiguration gefunden für Visualisierung.")

if __name__ == "__main__":
    main()