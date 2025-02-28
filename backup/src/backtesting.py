# src/backtesting.py
import os
import pandas as pd
import matplotlib.pyplot as plt
from math import sqrt
from strategy import CompositeStrategy  # oder SimpleRSIStrategy
from utils import logger

def load_data(data_file: str) -> pd.DataFrame:
    """
    Lädt historische Daten aus CSV oder Parquet.
    """
    _, ext = os.path.splitext(data_file.lower())
    if ext == '.parquet':
        df = pd.read_parquet(data_file)
    else:
        df = pd.read_csv(data_file, parse_dates=['timestamp'], index_col='timestamp')
    return df

def run_backtest(data_file: str, config: dict) -> pd.DataFrame:
    # 1) Daten laden
    df = load_data(data_file)
    
    # 2) Strategie-Instanz
    strategy = CompositeStrategy(config)
    
    # 3) Signale generieren
    # Wir nehmen an, dass wir für jeden Index das Signal mit allen bisherigen Daten berechnen.
    # Achtung: Bei sehr großen Datensätzen kann das langsam sein.
    df['signal'] = df.apply(lambda row: strategy.generate_signal(df.loc[:row.name]), axis=1)
    
    # 4) Trades simulieren (einfache Long-Only-Variante)
    position = 0
    entry_price = 0
    df['trade'] = 0   # +1 = Kauf, -1 = Verkauf
    df['profit'] = 0.0

    for i in range(len(df)):
        signal = df['signal'].iloc[i]
        price = df['close'].iloc[i]
        
        if position == 0 and signal == "BUY":
            position = 1
            entry_price = price
            df.iloc[i, df.columns.get_loc('trade')] = 1
        elif position == 1 and signal == "SELL":
            profit = price - entry_price
            df.iloc[i, df.columns.get_loc('profit')] = profit
            position = 0
            df.iloc[i, df.columns.get_loc('trade')] = -1

    # 5) Performance-Kennzahlen berechnen

    # 5.1 Gesamtprofit
    total_profit = df['profit'].sum()

    # 5.2 Trefferquote (Win Rate)
    # Wir zählen, wie viele Trades einen positiven Profit hatten.
    trade_mask = (df['trade'] == -1)  # -1 signalisiert hier den Abschluss eines Trades
    closed_trades = df[trade_mask]
    total_closed_trades = len(closed_trades)
    profitable_trades = len(closed_trades[closed_trades['profit'] > 0])
    if total_closed_trades > 0:
        win_rate = profitable_trades / total_closed_trades
    else:
        win_rate = 0

    # 5.3 Profit Factor (Verhältnis aus Summe aller Gewinne / Summe aller Verluste)
    gross_profit = closed_trades[closed_trades['profit'] > 0]['profit'].sum()
    gross_loss = closed_trades[closed_trades['profit'] < 0]['profit'].sum()  # ist negativ
    gross_loss_abs = abs(gross_loss)
    if gross_loss_abs > 0:
        profit_factor = gross_profit / gross_loss_abs
    else:
        profit_factor = float('inf') if gross_profit > 0 else 0

    # 5.4 Maximaler Drawdown
    # Dafür erstellen wir eine kumulative PnL-Kurve (Equity-Kurve).
    df['cumulative_profit'] = df['profit'].cumsum()
    running_max = df['cumulative_profit'].cummax()
    drawdown = df['cumulative_profit'] - running_max
    max_drawdown = drawdown.min()

    # 5.5 (Optionale) Sharpe Ratio (stark vereinfacht, bar-basiert)
    # Wir nehmen an, jeder Eintrag in df entspricht einer "Zeiteinheit" (z. B. 1h).
    # Realistisch wäre, daily returns zu betrachten.
    if df['profit'].std() != 0:
        sharpe = (df['profit'].mean() / df['profit'].std()) * sqrt(len(df))
    else:
        sharpe = 0

    # Logging der Ergebnisse
    logger.info(f"Backtest abgeschlossen. Ergebnisse:")
    logger.info(f"  Gesamtprofit        : {total_profit:.2f}")
    logger.info(f"  Anzahl abgeschl. Trades: {total_closed_trades}")
    logger.info(f"  Trefferquote (Win Rate) : {win_rate*100:.2f}%")
    logger.info(f"  Profit Factor       : {profit_factor:.2f}")
    logger.info(f"  Max Drawdown        : {max_drawdown:.2f}")
    logger.info(f"  (Einfache) Sharpe   : {sharpe:.2f}")

    # 6) Visualisierung: Kurs + Kauf-/Verkaufspunkte
    plt.figure(figsize=(12, 6))
    plt.plot(df.index, df['close'], label="Schlusskurs")
    buy_signals = df[df['trade'] == 1]
    sell_signals = df[df['trade'] == -1]
    plt.scatter(buy_signals.index, buy_signals['close'], marker='^', color='g', label="BUY")
    plt.scatter(sell_signals.index, sell_signals['close'], marker='v', color='r', label="SELL")
    plt.title("Backtesting: Handelssignale")
    plt.xlabel("Datum")
    plt.ylabel("Preis")
    plt.legend()
    plt.show()

    return df

if __name__ == "__main__":
    # Beispielhafte Konfiguration
    config = {
        'strategy': {
            'rsi_period': 14,
            'rsi_overbought': 70,
            'rsi_oversold': 30
        }
    }
    backtest_df = run_backtest("data/historical/BTC_1h_2024.parquet", config)
