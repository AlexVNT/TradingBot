# tuning.py
import os
import yaml
import numpy as np
import pandas as pd
from math import sqrt
from bayes_opt import BayesianOptimization
from utils import logger
from backtesting_improved import load_data, load_daily_data, run_backtest, calculate_performance, visualize_backtest
from strategy import CompositeStrategy

DISCRETE_KEYS = ['rsi_period', 'rsi_overbought', 'rsi_oversold', 'confirmation_bars', 'cooldown_bars']

def convert_discrete_params(params: dict) -> dict:
    """Rundet alle Parameter aus DISCRETE_KEYS auf ganze Zahlen."""
    new_params = {}
    for k, v in params.items():
        if k in DISCRETE_KEYS:
            new_params[k] = int(round(v))
        else:
            new_params[k] = v
    return new_params

def objective_function(rsi_period, rsi_overbought, rsi_oversold, confirmation_bars,
                       risk_pct, k_atr, m_atr, cooldown_bars, short_tp_multiplier):
    # Runde diskrete Werte
    params = {
        'rsi_period': int(round(rsi_period)),
        'rsi_overbought': int(round(rsi_overbought)),
        'rsi_oversold': int(round(rsi_oversold)),
        'confirmation_bars': int(round(confirmation_bars)),
        'cooldown_bars': int(round(cooldown_bars)),
        'risk_pct': risk_pct,
        'k_atr': k_atr,
        'm_atr': m_atr,
        'short_tp_multiplier': short_tp_multiplier
    }
    # Sicherstellen, dass der Oversold-Wert kleiner als der Overbought-Wert ist
    if params['rsi_oversold'] >= params['rsi_overbought']:
        return -1000

    config = {
        'strategy': {
            'rsi_period': params['rsi_period'],
            'rsi_overbought': params['rsi_overbought'],
            'rsi_oversold': params['rsi_oversold'],
            'confirmation_bars': params['confirmation_bars'],
        },
        'risk_management': {
            'risk_pct': params['risk_pct'],
            'k_atr': params['k_atr'],
            'm_atr': params['m_atr'],
            'atr_period': 14,  # fester Wert
            'cooldown_bars': params['cooldown_bars'],
            'short_tp_multiplier': params['short_tp_multiplier']
        }
    }
    
    # Lade historische Daten (achte darauf, dass diese Pfade existieren)
    df_hourly = load_data("data/historical/BTC_1h_2024.csv")
    df_daily = load_daily_data("data/historical/BTC_1d_2024.csv")
    
    strategy = CompositeStrategy(config)
    df_sim, trades = run_backtest(df_hourly, strategy, config, daily_df=df_daily, account_balance=100000)
    metrics = calculate_performance(df_sim, trades)
    
    num_trades = metrics['num_trades']
    # Falls zu wenige Trades generiert wurden, bestrafe diese Konfiguration stark.
    MIN_TRADES = 200
    if num_trades < MIN_TRADES:
        logger.info(f"Zu wenige Trades ({num_trades} statt min. {MIN_TRADES}). Konfiguration wird bestraft.")
        return -1000.0

    total_profit = metrics['total_profit']
    win_rate = metrics['win_rate']
    
    # Berechne den Profit Factor
    gross_profit = sum(t[3] for t in [t for t in trades if "OPEN" not in t[1] and t[3] > 0])
    gross_loss = abs(sum(t[3] for t in [t for t in trades if "OPEN" not in t[1] and t[3] < 0]))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    sharpe = metrics['sharpe']
    max_drawdown = abs(metrics['max_drawdown'])
    
    # Gewichtungen – anpassbar
    scale_profit = 100000
    scale_sharpe = 5
    scale_drawdown = 10000
    desired_trades = 250

    w_profit = 0.4
    w_win_rate = 0.2
    w_profit_factor = 0.1
    w_sharpe = 0.2
    w_drawdown = 0.05
    w_trades = 0.05

    norm_profit = total_profit / scale_profit
    norm_sharpe = sharpe / scale_sharpe
    norm_drawdown = max_drawdown / scale_drawdown
    norm_trades = min(num_trades, desired_trades) / desired_trades
    # Normierter Profit Factor (bei Inf, setze auf festen Wert, z.B. 10)
    if np.isinf(profit_factor):
        norm_profit_factor = 10.0
    else:
        norm_profit_factor = np.log(profit_factor + 1)
    
    score = (w_profit * norm_profit +
             w_win_rate * win_rate +
             w_profit_factor * norm_profit_factor +
             w_sharpe * norm_sharpe -
             w_drawdown * norm_drawdown +
             w_trades * norm_trades)
    
    logger.info(f"Getestete Config: {config} => Metrics: {metrics} => Score: {score:.4f}")
    return score

# Parameter-Grenzen (diskrete Parameter werden durch Rundung als Ganzzahlen verwendet)
pbounds = {
    'rsi_period': (5, 20),
    'rsi_overbought': (60, 90),
    'rsi_oversold': (10, 40),
    'confirmation_bars': (1, 5),
    'risk_pct': (0.005, 0.02),
    'k_atr': (1.0, 2.5),
    'm_atr': (2.0, 5.0),
    'cooldown_bars': (1, 5),
    'short_tp_multiplier': (1.0, 2.0)
}

def save_best_params(best_params, filename="results/best_params.yaml"):
    os.makedirs("results", exist_ok=True)
    
    def convert(item):
        if isinstance(item, np.generic):
            return item.item()
        elif isinstance(item, dict):
            return {k: convert(v) for k, v in item.items()}
        elif isinstance(item, list):
            return [convert(x) for x in item]
        else:
            return item

    best_params['params'] = convert_discrete_params(best_params['params'])
    best_params_converted = convert(best_params)
    
    with open(filename, "w") as f:
        yaml.safe_dump(best_params_converted, f, default_flow_style=False)
    logger.info(f"Beste Parameter wurden unter {filename} gespeichert.")

def visualize_best_result(best_params,
                          hourly_file="data/historical/BTC_1h_2024.csv",
                          daily_file="data/historical/BTC_1d_2024.csv"):
    params = best_params["params"]
    config = {
        'strategy': {
            'rsi_period': int(params['rsi_period']),
            'rsi_overbought': int(params['rsi_overbought']),
            'rsi_oversold': int(params['rsi_oversold']),
            'confirmation_bars': int(params['confirmation_bars'])
        },
        'risk_management': {
            'risk_pct': params['risk_pct'],
            'k_atr': params['k_atr'],
            'm_atr': params['m_atr'],
            'atr_period': 14,
            'cooldown_bars': int(params['cooldown_bars']),
            'short_tp_multiplier': params['short_tp_multiplier']
        }
    }
    df_hourly = load_data(hourly_file)
    df_daily = load_daily_data(daily_file)
    strategy = CompositeStrategy(config)
    df_sim, trades = run_backtest(df_hourly, strategy, config, daily_df=df_daily, account_balance=100000)
    metrics = calculate_performance(df_sim, trades)
    logger.info(f"Performance mit besten Parametern: {metrics}")
    visualize_backtest(df_sim, trades, title="Backtest: Best Parameters")

def auto_tune(init_points=5, n_iter=15):
    optimizer = BayesianOptimization(
        f=objective_function,
        pbounds=pbounds,
        random_state=42,
    )
    optimizer.maximize(init_points=init_points, n_iter=n_iter)
    return optimizer.max

def main():
    best_params = None
    try:
        best_params = auto_tune(init_points=5, n_iter=15)
    except KeyboardInterrupt:
        logger.info("Tuning wurde manuell abgebrochen.")
    finally:
        if best_params:
            logger.info(f"Beste Parameter gefunden: {best_params}")
            save_best_params(best_params)
            visualize_best_result(best_params)
        else:
            logger.error("Kein Ergebnis gefunden, bitte prüfe deine Strategie und Daten.")

if __name__ == "__main__":
    main()
