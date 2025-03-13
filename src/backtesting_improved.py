# src/backtesting_improved.py
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from utils import logger

def run_backtest(df, strategy, config, df_higher=None, symbol=None):
    """
    Führt einen Backtest für die gegebene Strategie und Daten durch.
    
    Args:
        df (pd.DataFrame): Stundendaten (H1) mit OHLCV-Daten
        strategy (CompositeStrategy): Die Handelsstrategie
        config (dict): Konfiguration aus config.yaml
        df_higher (pd.DataFrame): Daten im höheren Zeitrahmen (z. B. H4)
        symbol (str): Handelssymbol (z. B. EURUSD)
    
    Returns:
        df_sim (pd.DataFrame): Datenframe mit simulierten Ergebnissen
        trades (list): Liste der Trades
    """
    # Initialisiere das Startkapital aus der config.yaml
    initial_balance = config["risk_management"].get("initial_balance", 10000)  # Standard: 10.000 $
    balance = initial_balance
    equity = initial_balance
    position = "NONE"
    entry_price = 0
    trades = []
    equity_curve = []
    
    # Risikomanagement-Parameter aus der config.yaml
    risk_pct = config["risk_management"].get("risk_pct", 0.02)  # 2 % Risiko pro Trade
    atr_sl_multiplier = config["strategy"].get("atr_sl_multiplier", 2.0)
    leverage = config["trading"]["metatrader"].get("leverage", 1)
    
    # Initialisiere den simulierten Datenframe
    df_sim = df.copy()
    df_sim["balance"] = initial_balance
    df_sim["equity"] = initial_balance
    df_sim["position"] = "NONE"
    
    for i in range(1, len(df_sim)):
        # Aktuelle und vorherige Zeile
        current_time = df_sim.index[i]
        prev_time = df_sim.index[i-1]
        current_close = df_sim["close"].iloc[i]
        prev_close = df_sim["close"].iloc[i-1]
        
        # Aktualisiere Equity für offene Positionen
        if position != "NONE":
            if position == "LONG":
                equity = balance + (current_close - entry_price) * units * leverage
            elif position == "SHORT":
                equity = balance + (entry_price - current_close) * units * leverage
        else:
            equity = balance
        
        df_sim.at[current_time, "balance"] = balance
        df_sim.at[current_time, "equity"] = equity
        df_sim.at[current_time, "position"] = position
        equity_curve.append(equity)
        
        # Generiere Handelssignal
        signal = strategy.generate_signal(
            df_sim.iloc[:i+1],
            df_higher[df_higher.index <= current_time],
            position,
            symbol,
            entry_price
        )
        
        # Handle Signals
        if signal == "BUY" and position == "NONE":
            # Berechne Positionsgröße basierend auf Risiko
            atr = df_sim["atr"].iloc[i] if "atr" in df_sim.columns else 0.001
            stop_loss = current_close - atr * atr_sl_multiplier
            risk_per_unit = abs(current_close - stop_loss)
            risk_per_trade = balance * risk_pct
            units = risk_per_trade / risk_per_unit if risk_per_unit > 0 else 0
            units = units * leverage
            
            position = "LONG"
            entry_price = current_close
            balance -= units * current_close * 0.0001  # Transaktionskosten (angenommen 0.01 %)
            df_sim.at[current_time, "position"] = position
            logger.info(f"{symbol}-Position eröffnet bei {entry_price} um {current_time}")
        
        elif signal == "SELL" and position == "NONE":
            atr = df_sim["atr"].iloc[i] if "atr" in df_sim.columns else 0.001
            stop_loss = current_close + atr * atr_sl_multiplier
            risk_per_unit = abs(stop_loss - current_close)
            risk_per_trade = balance * risk_pct
            units = risk_per_trade / risk_per_unit if risk_per_unit > 0 else 0
            units = units * leverage
            
            position = "SHORT"
            entry_price = current_close
            balance -= units * current_close * 0.0001  # Transaktionskosten
            df_sim.at[current_time, "position"] = position
            logger.info(f"{symbol}-Position eröffnet bei {entry_price} um {current_time}")
        
        elif (signal == "CLOSE_LONG" and position == "LONG") or (signal == "CLOSE_SHORT" and position == "SHORT"):
            if position == "LONG":
                profit = (current_close - entry_price) * units * leverage
                balance += profit
                balance -= units * current_close * 0.0001  # Transaktionskosten
                trades.append({
                    "entry_time": prev_time,
                    "exit_time": current_time,
                    "entry_price": entry_price,
                    "exit_price": current_close,
                    "profit": profit,
                    "type": "LONG"
                })
                logger.info(f"{symbol}-Position geschlossen bei {current_close} um {current_time}, Profit: {profit}")
            elif position == "SHORT":
                profit = (entry_price - current_close) * units * leverage
                balance += profit
                balance -= units * current_close * 0.0001  # Transaktionskosten
                trades.append({
                    "entry_time": prev_time,
                    "exit_time": current_time,
                    "entry_price": entry_price,
                    "exit_price": current_close,
                    "profit": profit,
                    "type": "SHORT"
                })
                logger.info(f"{symbol}-Position geschlossen bei {current_close} um {current_time}, Profit: {profit}")
            
            position = "NONE"
            entry_price = 0
            units = 0
            df_sim.at[current_time, "position"] = position
    
    return df_sim, trades

def calculate_performance(df_sim, trades):
    """Berechnet die Performance-Metriken des Backtests."""
    if not trades:
        return {
            "total_profit": 0,
            "num_trades": 0,
            "win_rate": 0,
            "profit_factor": 0,
            "max_drawdown": 0,
            "sharpe": 0
        }
    
    total_profit = sum(trade["profit"] for trade in trades)
    num_trades = len(trades)
    winning_trades = sum(1 for trade in trades if trade["profit"] > 0)
    losing_trades = sum(1 for trade in trades if trade["profit"] < 0)
    win_rate = winning_trades / num_trades if num_trades > 0 else 0
    
    gross_profit = sum(trade["profit"] for trade in trades if trade["profit"] > 0)
    gross_loss = abs(sum(trade["profit"] for trade in trades if trade["profit"] < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    
    equity_curve = df_sim["equity"].values
    max_drawdown = 0
    peak = equity_curve[0]
    for equity in equity_curve:
        if equity > peak:
            peak = equity
        drawdown = (peak - equity) / peak if peak > 0 else 0
        max_drawdown = max(max_drawdown, drawdown)
    
    returns = df_sim["equity"].pct_change().dropna()
    sharpe = (returns.mean() / returns.std()) * np.sqrt(252 * 24) if returns.std() > 0 else 0  # Annualisiert (252 Handelstage, 24 Stunden)
    
    return {
        "total_profit": total_profit,
        "num_trades": num_trades,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "max_drawdown": -max_drawdown,
        "sharpe": sharpe
    }

def visualize_backtest(df_sim, trades, title="Backtest"):
    """Visualisiert die Ergebnisse des Backtests."""
    plt.figure(figsize=(14, 7))
    plt.plot(df_sim.index, df_sim["close"], label="Schlusskurs", color="blue")
    
    for trade in trades:
        entry_time = trade["entry_time"]
        exit_time = trade["exit_time"]
        entry_price = trade["entry_price"]
        exit_price = trade["exit_price"]
        trade_type = trade["type"]
        
        if trade_type == "LONG":
            plt.scatter(entry_time, entry_price, marker="^", color="green", label="LONG-OPEN" if "LONG-OPEN" not in plt.gca().get_legend_handles_labels()[1] else "", s=100)
            plt.scatter(exit_time, exit_price, marker="v", color="black", label="LONG-CLOSE" if "LONG-CLOSE" not in plt.gca().get_legend_handles_labels()[1] else "", s=100)
        elif trade_type == "SHORT":
            plt.scatter(entry_time, entry_price, marker="^", color="red", label="SHORT-OPEN" if "SHORT-OPEN" not in plt.gca().get_legend_handles_labels()[1] else "", s=100)
            plt.scatter(exit_time, exit_price, marker="v", color="darkred", label="SHORT-CLOSE" if "SHORT-CLOSE" not in plt.gca().get_legend_handles_labels()[1] else "", s=100)
    
    plt.title(title)
    plt.xlabel("Zeit")
    plt.ylabel("Preis")
    plt.legend()
    plt.grid()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(f"results/{title.replace(':', '_')}.png")
    plt.close()