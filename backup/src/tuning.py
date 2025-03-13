# src/tuning.py
import os
import yaml
import pandas as pd
import datetime
from backtesting_improved import run_backtest, calculate_performance, visualize_backtest
from strategy import CompositeStrategy
from utils import logger
from multi_backtesting import load_data
from bayes_opt import BayesianOptimization

def load_config():
    with open("config/config.yaml", "r") as file:
        return yaml.safe_load(file)

def evaluate_strategy(rsi_period, rsi_overbought, rsi_oversold, atr_tp, atr_sl, lookback, **kwargs):
    symbol = kwargs.get('symbol', "EURUSD")
    platform = kwargs.get('platform', "metatrader")
    config = kwargs.get('config', load_config())
    df_hourly, df_higher = kwargs.get('data', load_data(platform, symbol, config))

    if df_hourly is None or df_higher is None:
        return -float('inf')

    # Rundung der Parameter auf ganzzahlige oder sinnvolle Werte
    rsi_period = int(round(rsi_period))
    rsi_overbought = int(round(rsi_overbought))
    rsi_oversold = int(round(rsi_oversold))
    atr_tp = round(atr_tp, 1)
    atr_sl = round(atr_sl, 1)
    lookback = int(round(lookback))

    # Sicherstellen, dass die Werte im gültigen Bereich liegen
    rsi_period = max(2, min(15, rsi_period))
    rsi_overbought = max(50, min(90, rsi_overbought))
    rsi_oversold = max(10, min(40, rsi_oversold))
    atr_tp = max(2.0, min(8.0, atr_tp))
    atr_sl = max(0.5, min(3.5, atr_sl))
    lookback = max(3, min(10, lookback))

    # Temporäre Config anpassen
    temp_config = config.copy()
    temp_config["strategy"] = temp_config.get("strategy", {})
    temp_config["strategy"]["rsi_period"] = rsi_period
    temp_config["strategy"]["rsi_overbought"] = rsi_overbought
    temp_config["strategy"]["rsi_oversold"] = rsi_oversold
    temp_config["strategy"]["atr_tp_multiplier"] = atr_tp
    temp_config["strategy"]["atr_sl_multiplier"] = atr_sl
    temp_config["strategy"]["lookback"] = lookback

    strategy = CompositeStrategy(temp_config)
    df_sim, trades = run_backtest(df_hourly, strategy, temp_config, df_higher=df_higher, symbol=symbol)
    perf = calculate_performance(df_sim, trades)

    # Zielmetrik: Kombination aus Profit, Win Rate und Anzahl der Trades
    min_trades = 30
    trade_penalty = min(0, (len(trades) - min_trades) * 0.02)
    win_rate_bonus = perf["win_rate"] * 0.2
    score = perf["total_profit"] + trade_penalty + win_rate_bonus

    logger.info(f"Getestet: RSI {rsi_period}/{rsi_overbought}/{rsi_oversold}, TP {atr_tp}x, SL {atr_sl}x, Lookback {lookback} – Profit: {perf['total_profit']:.5f}, Trades: {len(trades)}, Win Rate: {perf['win_rate']:.2f}, Score: {score:.5f}")
    return score if perf["total_profit"] is not None else -float('inf')

def tune_strategy():
    config = load_config()
    platform = "metatrader" if config["platforms"].get("metatrader", False) else "binance"
    symbol = config['trading']['metatrader'].get("symbol", "EURUSD") if platform == "metatrader" else config['trading'].get("trade_pair", "BTCUSDT")

    df_hourly, df_higher = load_data(platform, symbol, config)
    if df_hourly is None or df_higher is None:
        logger.error(f"Datenabruf für {symbol} fehlgeschlagen.")
        return None, None

    pbounds = {
        'rsi_period': (2, 15),
        'rsi_overbought': (50, 90),
        'rsi_oversold': (10, 40),
        'atr_tp': (2.0, 8.0),
        'atr_sl': (0.5, 3.5),
        'lookback': (3, 10)
    }

    optimizer = BayesianOptimization(
        f=lambda rsi_period, rsi_overbought, rsi_oversold, atr_tp, atr_sl, lookback: evaluate_strategy(
            rsi_period, rsi_overbought, rsi_oversold, atr_tp, atr_sl, lookback,
            config=config, symbol=symbol, platform=platform, data=(df_hourly, df_higher)
        ),
        pbounds=pbounds,
        random_state=42,
        allow_duplicate_points=True
    )

    logger.info("Starte Bayesian Optimization für die Parameter...")
    optimizer.maximize(
        init_points=5,
        n_iter=40
    )

    best_params = optimizer.max['params']
    best_params['rsi_period'] = int(round(best_params['rsi_period']))
    best_params['rsi_overbought'] = int(round(best_params['rsi_overbought']))
    best_params['rsi_oversold'] = int(round(best_params['rsi_oversold']))
    best_params['lookback'] = int(round(best_params['lookback']))
    best_value = optimizer.max['target']
    logger.info(f"Beste Parameter: {best_params} mit Score: {best_value:.5f}")

    # Speichere die besten Parameter in einer separaten Datei
    os.makedirs("results", exist_ok=True)
    with open("results/best_parameters.yaml", "w") as f:
        yaml.dump(best_params, f)
    logger.info("Beste Parameter gespeichert in 'results/best_parameters.yaml'")

    results = pd.DataFrame(optimizer.res)
    os.makedirs("results", exist_ok=True)
    results.to_csv("results/bayesian_tuning_results.csv", index=False)

    # Führe den Backtest mit den besten Parametern aus und zeige Visualisierung
    best_config = config.copy()
    best_config["strategy"]["rsi_period"] = best_params['rsi_period']
    best_config["strategy"]["rsi_overbought"] = best_params['rsi_overbought']
    best_config["strategy"]["rsi_oversold"] = best_params['rsi_oversold']
    best_config["strategy"]["atr_tp_multiplier"] = best_params['atr_tp']
    best_config["strategy"]["atr_sl_multiplier"] = best_params['atr_sl']
    best_config["strategy"]["lookback"] = best_params['lookback']

    best_strategy = CompositeStrategy(best_config)
    best_df_sim, best_trades = run_backtest(df_hourly, best_strategy, best_config, df_higher=df_higher, symbol=symbol)
    best_perf = calculate_performance(best_df_sim, best_trades)
    logger.info(f"Endgültige Performance mit besten Parametern: {best_perf}")
    visualize_backtest(best_df_sim, best_trades, title=f"Backtest: {symbol} (Beste Parameter)")

    return best_params, best_value

if __name__ == "__main__":
    best_params, best_value = tune_strategy()