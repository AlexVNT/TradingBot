import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import talib
from src.utils import logger
from src.strategy import CompositeStrategy
import logging

logger.info("=== NEW VERSION LOADED: backtesting_improved.py with enforced unit limits v12 (2025-03-15) ===")

def setup_detailed_logger(symbol):
    detailed_logger = logging.getLogger(f"detailed_{symbol}")
    detailed_logger.setLevel(logging.DEBUG)
    os.makedirs("results", exist_ok=True)
    handler = logging.FileHandler(f"results/debug_detailed_{symbol}.log", mode='w')
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    detailed_logger.addHandler(handler)
    return detailed_logger

def run_backtest(df, strategy, config, df_higher=None, symbol=None, platform=None):
    initial_balance = config["risk_management"].get("initial_balance", 16000)
    balance = initial_balance
    equity = initial_balance
    position = "NONE"
    prev_position = "NONE"
    entry_price = 0
    units = 0
    trades = []
    equity_curve = []
    debug_data = []
    
    if platform not in ["binance", "metatrader"]:
        raise ValueError(f"Ungültige Plattform: {platform}. Erwartet: 'binance' oder 'metatrader'")
    leverage = config["trading"][platform].get("leverage", 1)
    atr_period = config["risk_management"].get("atr_period", 14)
    
    detailed_logger = setup_detailed_logger(symbol)
    logger.info(f"Starting backtest for {platform}/{symbol} with leverage {leverage}")
    detailed_logger.debug(f"Platform: {platform}, Symbol: {symbol}, Leverage: {leverage}")
    
    # ATR für SL/TP verwenden, kein fixed_sl_pips mehr
    df["atr"] = talib.ATR(df["high"], df["low"], df["close"], timeperiod=atr_period)
    df["atr"] = df["atr"].fillna(method="bfill").fillna(df["atr"].mean())
    
    df_sim = df.copy()
    df_sim["balance"] = pd.Series(initial_balance, dtype=float)
    df_sim["equity"] = pd.Series(initial_balance, dtype=float)
    df_sim["position"] = "NONE"
    detailed_logger.debug(f"Dataframe initialized: {len(df_sim)} rows")
    
    for i in range(1, len(df_sim)):
        current_time = df_sim.index[i]
        current_close = df_sim["close"].iloc[i]
        atr = df_sim["atr"].iloc[i]
        
        detailed_logger.debug(f"Processing timestamp: {current_time}, Close: {current_close}, ATR: {atr}")
        
        if balance <= 0:
            logger.error(f"{symbol}: Balance negativ ({balance}), Backtest abgebrochen.")
            detailed_logger.error(f"Balance negativ: {balance}, stopping backtest")
            break
        
        # Pip-Werte definieren
        pip_size = current_close * 0.0001 if platform == "binance" else (0.0001 if symbol != "USDJPY" else 0.01)
        pip_value = 0.1 if platform == "binance" else (10 if symbol.endswith("USD") and symbol != "USDJPY" else (1000 / current_close))
        
        if position != "NONE":
            detailed_logger.debug(f"Position active - Pip Value: {pip_value}, Pip Size: {pip_size}, Units: {units}")
            if position == "LONG":
                price_diff = (current_close - entry_price)
                pips = price_diff / pip_size
                equity = balance + (pips * units * pip_value * leverage)
                detailed_logger.debug(f"LONG - Price Diff: {price_diff}, Pips: {pips}, Equity: {equity}")
            elif position == "SHORT":
                price_diff = (entry_price - current_close)
                pips = price_diff / pip_size
                equity = balance + (pips * units * pip_value * leverage)
                detailed_logger.debug(f"SHORT - Price Diff: {price_diff}, Pips: {pips}, Equity: {equity}")
        else:
            equity = balance
            detailed_logger.debug(f"No position - Equity set to Balance: {equity}")
        
        df_sim.at[current_time, "balance"] = balance
        df_sim.at[current_time, "equity"] = equity
        
        if prev_position != position:
            debug_entry = {
                "time": current_time,
                "balance": balance,
                "equity": equity,
                "position": position,
                "entry_price": entry_price if position != "NONE" else 0,
                "exit_price": current_close if position == "NONE" and prev_position != "NONE" else 0,
                "units": units,
                "atr": atr,
                "pip_value": pip_value if position != "NONE" or prev_position != "NONE" else 0,
                "risk_per_trade": strategy.calculate_risk(),
                "profit": trades[-1]["profit"] if trades and position == "NONE" else 0
            }
            debug_data.append(debug_entry)
            detailed_logger.debug(f"Debug entry saved: {debug_entry}")
        
        prev_position = position
        df_sim.at[current_time, "position"] = position
        equity_curve.append(equity)
        
        strategy.balance = max(balance, 0)
        detailed_logger.debug(f"Before signal - Balance: {balance}, Position: {position}")
        signal = strategy.generate_signal(
            df_sim.iloc[:i+1],
            df_higher[df_higher.index <= current_time],
            position,
            symbol,
            entry_price
        )
        detailed_logger.debug(f"Signal generated: {signal}")
        
        if signal in ["BUY", "SELL"] and position == "NONE":
            # ATR-basierte SL-Berechnung
            sl_pips = strategy.atr_sl_multiplier * atr / pip_size
            risk_per_trade = strategy.calculate_risk()
            calculated_units = risk_per_trade / (sl_pips * pip_value)
            detailed_logger.debug(f"{'BUY' if signal == 'BUY' else 'SELL'} - Pre-calc: risk_per_trade={risk_per_trade}, sl_pips={sl_pips}, pip_value={pip_value}, calculated_units={calculated_units}")
            
            if platform == "binance":
                units = min(max(calculated_units, 0.0001), 5.0)  # Erhöhtes Maximum auf 5.0
                if calculated_units > 5.0:
                    logger.warning(f"{symbol} {'BUY' if signal == 'BUY' else 'SELL'}: Calculated units {calculated_units} exceeded 5.0, capped at {units}")
                    detailed_logger.warning(f"{'BUY' if signal == 'BUY' else 'SELL'} - Calculated units {calculated_units} exceeded 5.0, capped at {units}")
            else:  # MetaTrader
                units = min(max(calculated_units, 0.01), 5.0)  # Maximum 5.0 statt 100.0 für realistische Tests
                if calculated_units > 5.0:
                    logger.warning(f"{symbol} {'BUY' if signal == 'BUY' else 'SELL'}: Calculated units {calculated_units} exceeded 5.0, capped at {units}")
                    detailed_logger.warning(f"{'BUY' if signal == 'BUY' else 'SELL'} - Calculated units {calculated_units} exceeded 5.0, capped at {units}")
            
            detailed_logger.debug(f"{'BUY' if signal == 'BUY' else 'SELL'} - Post-calc: final_units={units}")
            
            position = "LONG" if signal == "BUY" else "SHORT"
            entry_price = current_close
            # Kein Balance-Abzug beim Öffnen
            df_sim.at[current_time, "position"] = position
            logger.info(f"{symbol}-{'LONG' if signal == 'BUY' else 'SHORT'} eröffnet bei {entry_price}, Units: {units:.4f}, Risk: {risk_per_trade:.2f}")
            detailed_logger.info(f"{'LONG' if signal == 'BUY' else 'SHORT'} opened - Entry Price: {entry_price}, Units: {units}, Balance after: {balance}")
        
        elif (signal == "CLOSE_LONG" and position == "LONG") or (signal == "CLOSE_SHORT" and position == "SHORT"):
            if position == "LONG":
                price_diff = (current_close - entry_price)
                pips = price_diff / pip_size
                profit = pips * units * pip_value * leverage
                balance += profit  # Balance nur hier aktualisieren
                trades.append({
                    "entry_time": trades[-1]["entry_time"] if trades else current_time,
                    "exit_time": current_time,
                    "entry_price": entry_price,
                    "exit_price": current_close,
                    "profit": profit,
                    "type": "LONG",
                    "units": units,
                    "pips": pips
                })
                logger.info(f"{symbol}-LONG geschlossen bei {current_close}, Profit: {profit:.2f}")
                detailed_logger.info(f"LONG closed - Exit Price: {current_close}, Profit: {profit}, Units: {units}, Balance after: {balance}")
            elif position == "SHORT":
                price_diff = (entry_price - current_close)
                pips = price_diff / pip_size
                profit = pips * units * pip_value * leverage
                balance += profit  # Balance nur hier aktualisieren
                trades.append({
                    "entry_time": trades[-1]["entry_time"] if trades else current_time,
                    "exit_time": current_time,
                    "entry_price": entry_price,
                    "exit_price": current_close,
                    "profit": profit,
                    "type": "SHORT",
                    "units": units,
                    "pips": pips
                })
                logger.info(f"{symbol}-SHORT geschlossen bei {current_close}, Profit: {profit:.2f}")
                detailed_logger.info(f"SHORT closed - Exit Price: {current_close}, Profit: {profit}, Units: {units}, Balance after: {balance}")
            
            position = "NONE"
            entry_price = 0
            units = 0
            df_sim.at[current_time, "position"] = position
    
    os.makedirs("results", exist_ok=True)
    debug_df = pd.DataFrame(debug_data)
    debug_df.to_csv(f"results/debug_log_{symbol}.csv", index=False)
    logger.info(f"Debug-Daten für {symbol} gespeichert in results/debug_log_{symbol}.csv")
    
    trade_df = pd.DataFrame(trades)
    trade_df["symbol"] = symbol
    trade_df = trade_df[["symbol", "type", "entry_time", "exit_time", "entry_price", "exit_price", "units", "pips", "profit"]]
    trade_df.to_csv(f"results/trades_{symbol}.csv", index=False)
    logger.info(f"Trade-Details für {symbol} gespeichert in results/trades_{symbol}.csv")
    
    return df_sim, trades

# Rest des Codes (calculate_performance, visualize_backtest) bleibt unverändert

def calculate_performance(df_sim, trades):
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
    sharpe = (returns.mean() / returns.std()) * np.sqrt(252 * 24) if returns.std() > 0 else 0
    
    return {
        "total_profit": total_profit,
        "num_trades": num_trades,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "max_drawdown": -max_drawdown,
        "sharpe": sharpe
    }

def visualize_backtest(df_sim, trades, title="Backtest"):
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
    
    os.makedirs("results", exist_ok=True)
    safe_title = title.replace(':', '_').replace('/', '_')
    plt.savefig(f"results/{safe_title}.png")
    plt.close()