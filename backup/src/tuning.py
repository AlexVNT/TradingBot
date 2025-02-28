# src/tuning.py
import os
import pandas as pd
import yaml
from strategy import CompositeStrategy
from backtesting_improved import load_data, run_backtest, calculate_performance
from utils import logger

def grid_search_parameters(df: pd.DataFrame, param_grid: list) -> list:
    """
    Führt einen Grid Search über die RSI-Parameter und confirmation_bars der Strategie durch.
    param_grid: Eine Liste von Dictionaries, z.B.
       {'rsi_period': 14, 'rsi_oversold': 30, 'rsi_overbought': 70, 'confirmation_bars': 2}
    Die ATR-Parameter werden fest vorgegeben.
    Liefert eine Liste von Ergebnissen, die für jede Parameterkombination die Performance-Kennzahlen enthalten.
    """
    results = []
    for params in param_grid:
        config = {
            'strategy': {
                'rsi_period': params['rsi_period'],
                'rsi_oversold': params['rsi_oversold'],
                'rsi_overbought': params['rsi_overbought'],
                'confirmation_bars': params['confirmation_bars'],
                'atr_period': 14  # fest
            },
            'risk_management': {
                'risk_pct': 0.01,
                'k_atr': 1.5,        # fest
                'm_atr': 3.0,        # fest
                'atr_period': 14,     # fest
                'cooldown_bars': 2    # fest
            }
        }
        try:
            strategy = CompositeStrategy(config)
            df_copy = df.copy()
            df_sim, trades = run_backtest(df_copy, strategy, config)
            metrics = calculate_performance(df_sim, trades)
            result = {**params, **metrics}
            results.append(result)
            logger.info(f"Tested params: {params} => Metrics: {metrics}")
        except Exception as e:
            logger.error(f"Fehler bei Parametern {params}: {e}")
    if not results:
        logger.error("Keine Ergebnisse im Grid Search gefunden.")
    return results

def main():
    data_file = "data/historical/BTC_1h_2024.csv"
    df = load_data(data_file)
    
    # Parameter-Grid: Nur RSI-Parameter und confirmation_bars variieren
    param_grid = []
    for rsi_period in [10, 14, 20]:
        for rsi_oversold in [25, 30, 35]:
            for rsi_overbought in [65, 70, 75]:
                for confirmation_bars in [1, 2, 3]:
                    param_grid.append({
                        "rsi_period": rsi_period,
                        "rsi_oversold": rsi_oversold,
                        "rsi_overbought": rsi_overbought,
                        "confirmation_bars": confirmation_bars
                    })
    
    results = grid_search_parameters(df, param_grid)
    if results:
        best = max(results, key=lambda x: x["total_profit"])
        logger.info(f"Beste Parameter gefunden: {best}")
    else:
        logger.error("Grid Search lieferte keine Ergebnisse – bitte überprüfe deine Strategie und Daten.")
        return

if __name__ == "__main__":
    main()
