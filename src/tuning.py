import os
import yaml
import pandas as pd
import numpy as np
from src.backtesting_improved import run_backtest, calculate_performance
from src.strategy import CompositeStrategy
from src.utils import logger
from src.multi_backtesting import load_data
import logging
from skopt import gp_minimize
from skopt.space import Real

def load_config(config_path="config/config.yaml"):
    with open(config_path, "r") as file:
        return yaml.safe_load(file)

def objective(params, config, platform, symbol, df_hourly, df_higher):
    atr_sl, atr_tp = params
    temp_config = config.copy()
    temp_config["strategy"]["atr_sl_multiplier"] = float(atr_sl)
    temp_config["strategy"]["atr_tp_multiplier"] = float(atr_tp)
    temp_config["trading"][platform]["symbols"][symbol]["atr_sl_multiplier"] = float(atr_sl)
    temp_config["trading"][platform]["symbols"][symbol]["atr_tp_multiplier"] = float(atr_tp)
    strategy = CompositeStrategy(temp_config, symbol=symbol)
    df_sim, trades = run_backtest(df_hourly, strategy, temp_config, df_higher=df_higher, symbol=symbol, platform=platform)
    perf = calculate_performance(df_sim, trades)
    profit = perf["total_profit"]
    logger.info(f"{platform}/{symbol}: Teste SL: {atr_sl:.2f}, TP: {atr_tp:.2f}, Profit: {profit:.2f}")
    return -profit  # Negativ, da gp_minimize minimiert

def bayesian_optimization(config, platform, symbol, atr_sl_range, atr_tp_range, df_hourly, df_higher):
    # Logging auf INFO setzen
    original_level = logger.getEffectiveLevel()
    logger.setLevel(logging.INFO)
    detailed_logger = logging.getLogger(f"detailed_{symbol}")
    detailed_original_level = detailed_logger.getEffectiveLevel()
    detailed_logger.setLevel(logging.INFO)
    
    # Suchraum definieren
    space = [
        Real(atr_sl_range[0], atr_sl_range[1], name="atr_sl_multiplier"),
        Real(atr_tp_range[0], atr_tp_range[1], name="atr_tp_multiplier")
    ]
    
    # Bayesian Optimization durchführen
    result = gp_minimize(
        lambda params: objective(params, config, platform, symbol, df_hourly, df_higher),
        space,
        n_calls=20,  # Anzahl der Iterationen
        random_state=42,
        verbose=False
    )
    
    # Beste Parameter und Ergebnis
    best_params = {"atr_sl_multiplier": float(result.x[0]), "atr_tp_multiplier": float(result.x[1])}
    temp_config = config.copy()
    temp_config["strategy"]["atr_sl_multiplier"] = best_params["atr_sl_multiplier"]
    temp_config["strategy"]["atr_tp_multiplier"] = best_params["atr_tp_multiplier"]
    temp_config["trading"][platform]["symbols"][symbol]["atr_sl_multiplier"] = best_params["atr_sl_multiplier"]
    temp_config["trading"][platform]["symbols"][symbol]["atr_tp_multiplier"] = best_params["atr_tp_multiplier"]
    strategy = CompositeStrategy(temp_config, symbol=symbol)
    df_sim, trades = run_backtest(df_hourly, strategy, temp_config, df_higher=df_higher, symbol=symbol, platform=platform)
    best_result = calculate_performance(df_sim, trades)
    
    # Logging-Level zurücksetzen
    logger.setLevel(original_level)
    detailed_logger.setLevel(detailed_original_level)
    
    return best_params, best_result

def tune_all_symbols(config):
    atr_sl_range = config["tuning"]["atr_sl_multiplier_range"]
    atr_tp_range = config["tuning"]["atr_tp_multiplier_range"]
    output_path = config["tuning"]["output_path"]
    
    best_params_dict = {"binance": {}, "metatrader": {}}
    platforms = []
    if config["platforms"]["binance"]:
        platforms.append("binance")
    if config["platforms"]["metatrader"]:
        platforms.append("metatrader")
    
    for platform in platforms:
        symbols = config["trading"][platform]["symbols"].keys()
        for symbol in symbols:
            logger.info(f"Optimiere {platform}/{symbol}...")
            df_hourly, df_higher = load_data(platform, symbol, config)
            if df_hourly is None or df_higher is None:
                logger.error(f"Daten für {platform}/{symbol} fehlen, überspringe.")
                continue
            best_params, result = bayesian_optimization(config, platform, symbol, atr_sl_range, atr_tp_range, df_hourly, df_higher)
            best_params_dict[platform][symbol] = best_params
            logger.info(f"{platform}/{symbol}: Beste Parameter: {best_params}, Profit: {result['total_profit']:.2f}")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as file:
        yaml.dump(best_params_dict, file, default_flow_style=False, sort_keys=False)
    logger.info(f"Ergebnisse gespeichert in {output_path}")

if __name__ == "__main__":
    config = load_config()
    tune_all_symbols(config)