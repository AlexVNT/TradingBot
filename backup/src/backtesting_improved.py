# src/backtesting_improved.py
import pandas as pd
import numpy as np
from utils import logger
import matplotlib.pyplot as plt
from strategy import CompositeStrategy

def run_backtest(df: pd.DataFrame, strategy: CompositeStrategy, config: dict, df_higher: pd.DataFrame = None, symbol: str = "EURUSD") -> tuple:
    """Führt den Backtest für die gegebene Strategie und Daten aus."""
    df_sim = df.copy()
    trades = []
    current_position = "NONE"
    entry_price = None
    entry_time = None

    for index, row in df_sim.iterrows():
        # Signal generieren, indem nur Daten bis zum aktuellen Zeitpunkt verwendet werden
        signal = strategy.generate_signal(
            df_sim[df_sim.index <= index],
            df_higher[df_higher.index <= index],
            current_position,
            symbol,
            entry_price
        )
        current_price = row['close']

        if signal == "BUY" and current_position == "NONE":
            current_position = "LONG"
            entry_price = current_price
            entry_time = index
            logger.info(f"{symbol}-Position eröffnet bei {entry_price:.5f} um {entry_time}")
        elif signal == "SELL" and current_position == "NONE":
            current_position = "SHORT"
            entry_price = current_price
            entry_time = index
            logger.info(f"{symbol}-Position eröffnet bei {entry_price:.5f} um {entry_time}")
        elif (signal == "CLOSE_LONG" or signal == "CLOSE_SHORT") and current_position != "NONE" and index >= entry_time:
            exit_price = current_price
            exit_time = index
            profit = exit_price - entry_price if current_position == "LONG" else entry_price - exit_price
            trades.append({
                "type": current_position,
                "entry_time": entry_time,
                "entry_price": entry_price,
                "exit_time": exit_time,
                "exit_price": exit_price,
                "profit": profit
            })
            logger.info(f"{symbol}-Position geschlossen bei {exit_price:.5f} um {exit_time}")
            current_position = "NONE"
            entry_price = None
            entry_time = None

    return df_sim, trades

def calculate_performance(df_sim: pd.DataFrame, trades: list) -> dict:
    """Berechnet die Performance-Metriken basierend auf den Trades."""
    if not trades:
        return {
            "total_profit": 0.0,
            "num_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "max_drawdown": 0.0,
            "sharpe": 0.0
        }

    total_profit = sum(trade['profit'] for trade in trades)
    num_trades = len(trades)
    wins = sum(1 for trade in trades if trade['profit'] > 0)
    win_rate = wins / num_trades if num_trades > 0 else 0.0

    gross_profit = sum(trade['profit'] for trade in trades if trade['profit'] > 0)
    gross_loss = abs(sum(trade['profit'] for trade in trades if trade['profit'] < 0))
    profit_factor = gross_profit / gross_loss if gross_loss != 0 else float('inf')

    equity = [0]
    for trade in trades:
        equity.append(equity[-1] + trade['profit'])
    max_drawdown = max(np.maximum.accumulate(equity) - equity) if equity else 0.0

    returns = np.diff(equity)
    sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) != 0 else 0.0

    return {
        "total_profit": total_profit,
        "num_trades": num_trades,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "max_drawdown": -max_drawdown,
        "sharpe": sharpe
    }

def visualize_backtest(df_sim: pd.DataFrame, trades: list, title: str = "Backtest"):
    """Visualisiert den Backtest mit Kursverlauf und Trades."""
    plt.figure(figsize=(12, 6))
    plt.plot(df_sim.index, df_sim['close'], label="Schlusskurs", color="blue")

    long_open_labeled = False
    long_close_labeled = False
    short_open_labeled = False
    short_close_labeled = False

    for trade in trades:
        if trade.get("entry_time"):
            if trade["type"] == "LONG":
                label = "LONG-OPEN" if not long_open_labeled else None
                plt.arrow(trade["entry_time"].to_pydatetime(), trade["entry_price"], 0, 0.0015, head_width=0.3, head_length=0.0007, fc='#90EE90', ec='#90EE90', label=label)
                long_open_labeled = True
            elif trade["type"] == "SHORT":
                label = "SHORT-OPEN" if not short_open_labeled else None
                plt.arrow(trade["entry_time"].to_pydatetime(), trade["entry_price"], 0, -0.0015, head_width=0.3, head_length=0.0007, fc='#FF6347', ec='#FF6347', label=label)
                short_open_labeled = True
        if trade.get("exit_time"):
            if trade["type"] == "LONG":
                label = "LONG-CLOSE" if not long_close_labeled else None
                plt.arrow(trade["exit_time"].to_pydatetime(), trade["exit_price"], 0, -0.0015, head_width=0.3, head_length=0.0007, fc='#006400', ec='#006400', label=label)
                long_close_labeled = True
            elif trade["type"] == "SHORT":
                label = "SHORT-CLOSE" if not short_close_labeled else None
                plt.arrow(trade["exit_time"].to_pydatetime(), trade["exit_price"], 0, 0.0015, head_width=0.3, head_length=0.0007, fc='#8B0000', ec='#8B0000', label=label)
                short_close_labeled = True

    plt.title(title)
    plt.legend(loc="best")
    plt.grid(True)
    plt.show()