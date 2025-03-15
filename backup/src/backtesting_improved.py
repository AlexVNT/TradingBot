# src/backtesting_improved.py
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import talib
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
    prev_position = "NONE"  # Für Debug-Logik
    entry_price = 0
    units = 0  # Anzahl der gehandelten Lots
    trades = []
    equity_curve = []
    debug_data = []  # Liste für Debug-Informationen
    
    # Risikomanagement-Parameter aus der config.yaml
    risk_pct = config["risk_management"].get("risk_pct", 0.01)  # 1 % Risiko pro Trade
    atr_sl_multiplier = 1.0  # Nur für GBPUSD relevant
    atr_tp_multiplier = config["strategy"].get("atr_tp_multiplier", 6.0)
    atr_period = config["risk_management"].get("atr_period", 14)
    leverage = config["trading"]["metatrader"].get("leverage", 1)
    fixed_sl_pips = 8 if symbol == "EURUSD" else 7 if symbol == "AUDUSD" else 12  # Letzte Feinjustierung für AUDUSD
    fixed_risk_per_trade = 160  # Feste Risiko pro Trade
    
    # Berechne ATR und füge es dem Datenframe hinzu
    df["atr"] = talib.ATR(df["high"], df["low"], df["close"], timeperiod=atr_period)
    # Füllen von NaN-Werten mit dem ersten gültigen ATR-Wert
    df["atr"] = df["atr"].fillna(method="bfill").fillna(df["atr"].mean())
    
    # Initialisiere den simulierten Datenframe
    df_sim = df.copy()
    df_sim["balance"] = initial_balance
    df_sim["equity"] = initial_balance
    df_sim["position"] = "NONE"
    
    for i in range(1, len(df_sim)):
        current_time = df_sim.index[i]
        current_close = df_sim["close"].iloc[i]
        atr = df_sim["atr"].iloc[i]
        
        # Aktualisiere Equity für offene Positionen
        if position != "NONE":
            pip_value = 10 if symbol.endswith("USD") and symbol != "USDJPY" else (1000 / current_close) if symbol == "USDJPY" else 10
            if position == "LONG":
                price_diff = (current_close - entry_price)
                pips = price_diff / 0.0001 if symbol != "USDJPY" else price_diff / 0.01
                equity = balance + (pips * units * pip_value * leverage)
            elif position == "SHORT":
                price_diff = (entry_price - current_close)
                pips = price_diff / 0.0001 if symbol != "USDJPY" else price_diff / 0.01
                equity = balance + (pips * units * pip_value * leverage)
        else:
            equity = balance
        
        df_sim.at[current_time, "balance"] = balance
        df_sim.at[current_time, "equity"] = equity
        
        # Speichere Debug-Daten vor der Änderung der Position
        if prev_position != position:
            debug_data.append({
                "time": current_time,
                "balance": balance,
                "equity": equity,
                "position": position,
                "entry_price": entry_price if position != "NONE" else 0,
                "exit_price": current_close if position == "NONE" and prev_position != "NONE" else 0,
                "units": units if position != "NONE" or prev_position != "NONE" else 0,
                "atr": atr,
                "pip_value": pip_value if position != "NONE" or prev_position != "NONE" else 0,
                "risk_per_unit_in_pips": risk_per_unit_in_pips if position != "NONE" else 0,
                "highest_win": max([trade["profit"] for trade in trades if trade["profit"] > 0] + [0]) if trades else 0,
                "highest_loss": min([trade["profit"] for trade in trades if trade["profit"] < 0] + [0]) if trades else 0,
                "profit": trades[-1]["profit"] if trades and position == "NONE" else 0
            })
        
        # Aktualisiere Position für den nächsten Vergleich
        prev_position = position
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
            # Fester Stop-Loss für alle Paare
            if symbol == "USDJPY":
                stop_loss = current_close - (fixed_sl_pips * 0.01)
                risk_per_unit = fixed_sl_pips * 0.01
                risk_per_unit_in_pips = fixed_sl_pips
            else:
                stop_loss = current_close - (fixed_sl_pips * 0.0001)
                risk_per_unit = fixed_sl_pips * 0.0001
                risk_per_unit_in_pips = fixed_sl_pips
            
            risk_per_trade = fixed_risk_per_trade  # Feste Risiko pro Trade
            pip_value = 10 if symbol.endswith("USD") and symbol != "USDJPY" else (1000 / current_close) if symbol == "USDJPY" else 10
            units = (risk_per_trade / (risk_per_unit_in_pips * pip_value)) if risk_per_unit > 0 and pip_value > 0 else 0
            units = min(max(units, 0.01), 100.0)
            
            position = "LONG"
            entry_price = current_close
            balance -= units * pip_value * 0.0001  # Transaktionskosten (0.01 %)
            df_sim.at[current_time, "position"] = position
            logger.info(f"{symbol}-Position eröffnet bei {entry_price} um {current_time}, Units: {units:.4f}, Pip Value: {pip_value:.4f}, Risk per Unit (Pips): {risk_per_unit_in_pips:.2f}, ATR: {atr:.6f}")
        
        elif signal == "SELL" and position == "NONE":
            # Fester Stop-Loss für alle Paare
            if symbol == "USDJPY":
                stop_loss = current_close + (fixed_sl_pips * 0.01)
                risk_per_unit = fixed_sl_pips * 0.01
                risk_per_unit_in_pips = fixed_sl_pips
            else:
                stop_loss = current_close + (fixed_sl_pips * 0.0001)
                risk_per_unit = fixed_sl_pips * 0.0001
                risk_per_unit_in_pips = fixed_sl_pips
            
            risk_per_trade = fixed_risk_per_trade  # Feste Risiko pro Trade
            pip_value = 10 if symbol.endswith("USD") and symbol != "USDJPY" else (1000 / current_close) if symbol == "USDJPY" else 10
            units = (risk_per_trade / (risk_per_unit_in_pips * pip_value)) if risk_per_unit > 0 and pip_value > 0 else 0
            units = min(max(units, 0.01), 100.0)
            
            position = "SHORT"
            entry_price = current_close
            balance -= units * pip_value * 0.0001  # Transaktionskosten
            df_sim.at[current_time, "position"] = position
            logger.info(f"{symbol}-Position eröffnet bei {entry_price} um {current_time}, Units: {units:.4f}, Pip Value: {pip_value:.4f}, Risk per Unit (Pips): {risk_per_unit_in_pips:.2f}, ATR: {atr:.6f}")
        
        elif (signal == "CLOSE_LONG" and position == "LONG") or (signal == "CLOSE_SHORT" and position == "SHORT"):
            if position == "LONG":
                pip_value = 10 if symbol.endswith("USD") and symbol != "USDJPY" else (1000 / current_close) if symbol == "USDJPY" else 10
                price_diff = (current_close - entry_price)
                pips = price_diff / 0.0001 if symbol != "USDJPY" else price_diff / 0.01
                profit = pips * units * pip_value * leverage
                balance += profit
                balance -= units * pip_value * 0.0001  # Transaktionskosten
                trades.append({
                    "entry_time": current_time,
                    "exit_time": current_time,
                    "entry_price": entry_price,
                    "exit_price": current_close,
                    "profit": profit,
                    "type": "LONG",
                    "units": units,
                    "pips": pips
                })
                logger.info(f"{symbol}-Position geschlossen bei {current_close} um {current_time}, Profit: {profit:.2f}, Pips: {pips:.2f}")
            elif position == "SHORT":
                pip_value = 10 if symbol.endswith("USD") and symbol != "USDJPY" else (1000 / current_close) if symbol == "USDJPY" else 10
                price_diff = (entry_price - current_close)
                pips = price_diff / 0.0001 if symbol != "USDJPY" else price_diff / 0.01
                profit = pips * units * pip_value * leverage
                balance += profit
                balance -= units * pip_value * 0.0001  # Transaktionskosten
                trades.append({
                    "entry_time": current_time,
                    "exit_time": current_time,
                    "entry_price": entry_price,
                    "exit_price": current_close,
                    "profit": profit,
                    "type": "SHORT",
                    "units": units,
                    "pips": pips
                })
                logger.info(f"{symbol}-Position geschlossen bei {current_close} um {current_time}, Profit: {profit:.2f}, Pips: {pips:.2f}")
            
            position = "NONE"
            entry_price = 0
            units = 0
            df_sim.at[current_time, "position"] = position
    
    # Speichere Debug-Daten in eine CSV-Datei
    os.makedirs("results", exist_ok=True)
    debug_df = pd.DataFrame(debug_data)
    debug_df.to_csv(f"results/debug_log_{symbol}.csv", index=False)
    logger.info(f"Debug-Daten für {symbol} gespeichert in results/debug_log_{symbol}.csv")
    
    # Speichere Trade-Details in eine CSV-Datei
    trade_df = pd.DataFrame(trades)
    trade_df["symbol"] = symbol
    trade_df = trade_df[["symbol", "type", "entry_time", "exit_time", "entry_price", "exit_price", "units", "pips", "profit"]]
    trade_df.to_csv(f"results/trades_{symbol}.csv", index=False)
    logger.info(f"Trade-Details für {symbol} gespeichert in results/trades_{symbol}.csv")
    
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