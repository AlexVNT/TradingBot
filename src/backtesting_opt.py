# src/backtesting_opt.py
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from math import sqrt
import yaml
from utils import logger
from strategy import CompositeStrategy

def load_data(data_file: str) -> pd.DataFrame:
    """
    Lädt historische Daten aus einer CSV- oder Parquet-Datei.
    """
    _, ext = os.path.splitext(data_file.lower())
    if ext == '.parquet':
        df = pd.read_parquet(data_file)
    else:
        df = pd.read_csv(data_file, parse_dates=['timestamp'], index_col='timestamp')
    return df

def backtest_strategy(df: pd.DataFrame, strategy: CompositeStrategy) -> dict:
    """
    Simuliert Trades mithilfe der gegebenen Strategie über den DataFrame.
    Berechnet anschließend Performance-Kennzahlen:
      - Gesamtprofit
      - Anzahl abgeschlossener Trades
      - Trefferquote (Win Rate)
      - Profit Factor
      - Max Drawdown
      - (Einfache) Sharpe Ratio
    """
    # Generiere Signale: Hier wird angenommen, dass die Strategie bei jedem Zeitpunkts die
    # Daten bis zu diesem Zeitpunkt auswertet.
    df = df.copy()  # Vermeidet Seiteneffekte
    df['signal'] = df.apply(lambda row: strategy.generate_signal(df.loc[:row.name]), axis=1)
    
    # Trade-Simulation: Long-Only-Ansatz.
    position = 0
    entry_price = 0
    trades = []  # Liste von (index, trade_type, price, profit)
    
    for i in range(len(df)):
        signal = df['signal'].iloc[i]
        price = df['close'].iloc[i]
        # Eröffne eine Long-Position bei BUY, wenn keine Position offen ist.
        if position == 0 and signal == "BUY":
            position = 1
            entry_price = price
            trades.append((df.index[i], "BUY", price, 0))
        # Schließe die Long-Position bei SELL
        elif position == 1 and signal == "SELL":
            profit = price - entry_price
            trades.append((df.index[i], "SELL", price, profit))
            position = 0

    # Gesamtprofit berechnen (nur bei SELL-Events, wo Profit realisiert wird)
    total_profit = sum(trade[3] for trade in trades if trade[1] == "SELL")
    
    # Anzahl abgeschlossener Trades und Trefferquote:
    closed_trades = [trade for trade in trades if trade[1] == "SELL"]
    num_trades = len(closed_trades)
    win_trades = len([trade for trade in closed_trades if trade[3] > 0])
    win_rate = win_trades / num_trades if num_trades > 0 else 0

    # Profit Factor:
    gross_profit = sum(trade[3] for trade in closed_trades if trade[3] > 0)
    gross_loss = abs(sum(trade[3] for trade in closed_trades if trade[3] < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    # Berechne die Equity-Kurve
    df['profit'] = 0.0
    for trade in closed_trades:
        idx = trade[0]
        df.loc[idx, 'profit'] = trade[3]
    df['cumulative_profit'] = df['profit'].cumsum()
    running_max = df['cumulative_profit'].cummax()
    drawdown = df['cumulative_profit'] - running_max
    max_drawdown = drawdown.min()

    # (Einfache) Sharpe Ratio (Annahme: jede Zeiteinheit ist gleichwertig, z. B. 1h)
    profit_std = df['profit'].std()
    if profit_std != 0:
        sharpe = (df['profit'].mean() / profit_std) * sqrt(len(df))
    else:
        sharpe = 0

    metrics = {
        "total_profit": total_profit,
        "num_trades": num_trades,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
    }
    return metrics

def grid_search_parameters(df: pd.DataFrame, param_grid: list) -> list:
    """
    Führt einen Grid Search über die Parameter der Strategie durch.
    param_grid ist eine Liste von Dictionaries mit den Parametern (z. B. RSI-Period, Overbought, Oversold).
    Gibt eine Liste von Ergebnissen zurück, die jeweils die Parameter und die zugehörigen Performance-Kennzahlen enthalten.
    """
    results = []
    for params in param_grid:
        # Erstelle eine Konfiguration für die Strategie
        config = {
            'strategy': {
                'rsi_period': params['rsi_period'],
                'rsi_overbought': params['rsi_overbought'],
                'rsi_oversold': params['rsi_oversold']
            }
        }
        strategy = CompositeStrategy(config)
        metrics = backtest_strategy(df.copy(), strategy)
        # Speichere Parameter und Kennzahlen
        result = {**params, **metrics}
        results.append(result)
        logger.info(f"Tested params: {params} => Metrics: {metrics}")
    return results

def main():
    # Pfad zu deiner Parquet-Datei (Passe den Pfad an)
    data_file = "data/historical/BTC_1h_2024.parquet"
    df = load_data(data_file)
    
    # Beispiel-Parametergrid (du kannst hier die Werte anpassen)
    param_grid = []
    for rsi_period in [10, 14, 20]:
        for rsi_oversold in [25, 30, 35]:
            for rsi_overbought in [65, 70, 75]:
                param_grid.append({
                    "rsi_period": rsi_period,
                    "rsi_oversold": rsi_oversold,
                    "rsi_overbought": rsi_overbought
                })
                
    # Führe Grid Search durch
    results = grid_search_parameters(df, param_grid)
    
    # Finde den besten Parameter-Satz basierend auf Gesamtprofit (oder einem anderen Metrik-Kriterium)
    best = max(results, key=lambda x: x["total_profit"])
    logger.info(f"Beste Parameter gefunden: {best}")
    
    # Optional: Visualisierung der Equity-Kurve für den besten Parameter-Satz
    best_config = {
        'strategy': {
            'rsi_period': best['rsi_period'],
            'rsi_overbought': best['rsi_overbought'],
            'rsi_oversold': best['rsi_oversold']
        }
    }
    strategy = CompositeStrategy(best_config)
    metrics = backtest_strategy(df.copy(), strategy)
    logger.info(f"Performance mit besten Parametern: {metrics}")
    
    # Hier kannst du zusätzlich noch die Equity-Kurve plotten, falls gewünscht.
    df['signal'] = df.apply(lambda row: strategy.generate_signal(df.loc[:row.name]), axis=1)
    plt.figure(figsize=(12, 6))
    plt.plot(df.index, df['close'], label="Schlusskurs")
    plt.title("Backtesting Equity-Kurve mit besten Parametern")
    plt.xlabel("Datum")
    plt.ylabel("Preis")
    plt.legend()
    plt.show()

if __name__ == "__main__":
    main()
