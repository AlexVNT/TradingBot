import os
import yaml
import numpy as np
import pandas as pd
from math import sqrt
from bayes_opt import BayesianOptimization
from utils import logger
from backtesting_improved import run_backtest, calculate_performance, visualize_backtest
from strategy import CompositeStrategy

# Importiere die Connectoren
from binance_connector import BinanceConnector, BinanceTestnetConnector
from metatrader_connector import MetaTraderConnector

DISCRETE_KEYS = ['rsi_period', 'rsi_overbought', 'rsi_oversold', 'confirmation_bars', 'cooldown_bars']

def convert_discrete_params(params: dict) -> dict:
    new_params = {}
    for k, v in params.items():
        if k in DISCRETE_KEYS:
            new_params[k] = int(round(v))
        else:
            new_params[k] = v
    return new_params

def objective_function(rsi_period, rsi_overbought, rsi_oversold, confirmation_bars,
                       risk_pct, k_atr, m_atr, cooldown_bars, short_tp_multiplier):
    # Runde und setze Parameter
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
    if params['rsi_oversold'] >= params['rsi_overbought']:
        return -1000

    # Baue eine temporäre Config für Strategy und Risk Management
    tuning_config = {
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
            'atr_period': 14,  # Fester Wert
            'cooldown_bars': params['cooldown_bars'],
            'short_tp_multiplier': params['short_tp_multiplier']
        }
    }

    # Lade die allgemeine Konfiguration
    with open("config/config.yaml", "r") as f:
        full_config = yaml.safe_load(f)

    # Debug-Ausgabe, um zu sehen, was geladen wird:
    logger.info(f"Plattform-Konfiguration: {full_config.get('platforms')}")

    if full_config["platforms"].get("metatrader") is True:
        platform = "metatrader"
    elif full_config["platforms"].get("binance") is True:
        platform = "binance"
    else:
        logger.error("Keine Plattform in der Config aktiviert!")
        return -1000


    scores = []

    if platform == "binance":
        trade_conf = full_config["trading"]["binance"]
        symbols = trade_conf["symbols"]
        timeframe = trade_conf["timeframe"]
        higher_tf = trade_conf["higher_timeframe"]
        use_testnet = trade_conf.get("use_testnet", True)
        # Initialisiere den entsprechenden Connector
        connector = BinanceTestnetConnector() if use_testnet else BinanceConnector()
        for symbol in symbols:
            try:
                # Lade historische Daten direkt via API (hier Limit nach Bedarf anpassen)
                df_hourly = connector.get_ohlcv(symbol, timeframe, limit=1000)
                df_daily = connector.get_ohlcv(symbol, higher_tf, limit=500)
                # Erstelle die Strategie (tuning_config wird hier genutzt – ggf. in Kombination mit weiteren Konfigurationsabschnitten)
                strategy = CompositeStrategy(tuning_config)
                # Führe Backtest durch (Account-Balance hier als Beispiel 100000)
                df_sim, trades = run_backtest(df_hourly, strategy, tuning_config, daily_df=df_daily, account_balance=100000)
                metrics = calculate_performance(df_sim, trades)
                # Berechne einen Score, z. B. aus total_profit, win_rate etc.
                num_trades = metrics['num_trades']
                if num_trades < 50:
                    # Bestrafe Konfigurationen mit zu wenigen Trades
                    score = -1000.0
                else:
                    gross_profit = sum(t[3] for t in trades if "OPEN" not in t[1] and t[3] > 0)
                    gross_loss = abs(sum(t[3] for t in trades if "OPEN" not in t[1] and t[3] < 0))
                    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
                    sharpe = metrics['sharpe']
                    max_drawdown = abs(metrics['max_drawdown'])
                    # Gewichtungen (analog zu bisherigen Einstellungen)
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

                    norm_profit = metrics['total_profit'] / scale_profit
                    norm_sharpe = sharpe / scale_sharpe
                    norm_drawdown = max_drawdown / scale_drawdown
                    norm_trades = min(num_trades, desired_trades) / desired_trades
                    if np.isinf(profit_factor):
                        norm_profit_factor = 10.0
                    else:
                        norm_profit_factor = np.log(profit_factor + 1)

                    score = (w_profit * norm_profit +
                             w_win_rate * metrics['win_rate'] +
                             w_profit_factor * norm_profit_factor +
                             w_sharpe * norm_sharpe -
                             w_drawdown * norm_drawdown +
                             w_trades * norm_trades)
                scores.append(score)
            except Exception as e:
                logger.error(f"Fehler bei {symbol}: {e}")
                scores.append(-1000)
        # Gesamtscore als Durchschnitt über alle Symbole
        overall_score = np.mean(scores)
        logger.info(f"Durchschnittlicher Score für Binance: {overall_score:.4f}")
        return overall_score

    elif platform == "metatrader":
        trade_conf = full_config["trading"]["metatrader"]
        symbol = trade_conf["symbol"]
        timeframe = trade_conf["timeframe"]
        higher_tf = trade_conf["higher_timeframe"]
        connector = MetaTraderConnector()
        # Mapping für MetaTrader-Zeitrahmen
        import MetaTrader5 as mt5
        tf_mapping = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
            "W1": mt5.TIMEFRAME_W1,
            "MN1": mt5.TIMEFRAME_MN1
        }
        mt_tf = tf_mapping.get(timeframe.upper(), mt5.TIMEFRAME_H1)
        mt_higher_tf = tf_mapping.get(higher_tf.upper(), mt5.TIMEFRAME_D1)
        try:
            df_hourly = connector.get_ohlcv(symbol, mt_tf, limit=1000)
            df_daily = connector.get_ohlcv(symbol, mt_higher_tf, limit=500)
            strategy = CompositeStrategy(tuning_config)
            df_sim, trades = run_backtest(df_hourly, strategy, tuning_config, daily_df=df_daily, account_balance=100000)
            metrics = calculate_performance(df_sim, trades)
            num_trades = metrics['num_trades']
            if num_trades < 50:
                overall_score = -1000.0
            else:
                gross_profit = sum(t[3] for t in trades if "OPEN" not in t[1] and t[3] > 0)
                gross_loss = abs(sum(t[3] for t in trades if "OPEN" not in t[1] and t[3] < 0))
                profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
                sharpe = metrics['sharpe']
                max_drawdown = abs(metrics['max_drawdown'])
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

                norm_profit = metrics['total_profit'] / scale_profit
                norm_sharpe = sharpe / scale_sharpe
                norm_drawdown = max_drawdown / scale_drawdown
                norm_trades = min(num_trades, desired_trades) / desired_trades
                if np.isinf(profit_factor):
                    norm_profit_factor = 10.0
                else:
                    norm_profit_factor = np.log(profit_factor + 1)

                overall_score = (w_profit * norm_profit +
                                 w_win_rate * metrics['win_rate'] +
                                 w_profit_factor * norm_profit_factor +
                                 w_sharpe * norm_sharpe -
                                 w_drawdown * norm_drawdown +
                                 w_trades * norm_trades)
            logger.info(f"Score für MetaTrader: {overall_score:.4f}")
            return overall_score
        except Exception as e:
            logger.error(f"Fehler bei MetaTrader: {e}")
            return -1000.0

# Parameter-Grenzen bleiben unverändert:
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
                          platform="binance"):
    # Für Visualisierungen nutzen wir weiterhin CSVs als Beispiel – 
    # hier kannst du später auch direkt API-Daten einbinden, falls gewünscht.
    from backtesting_improved import load_data, load_daily_data
    params = best_params["params"]
    config_for_vis = {
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
    # Beispiel: Für Binance nutzen wir CSVs (du kannst das später anpassen)
    if platform == "binance":
        df_hourly = load_data("data/historical/BTC_1h_2024.csv")
        df_daily = load_daily_data("data/historical/BTC_1d_2024.csv")
    else:
        df_hourly = load_data("data/historical/EURUSD_H1.csv")
        df_daily = load_daily_data("data/historical/EURUSD_D1.csv")
    strategy = CompositeStrategy(config_for_vis)
    df_sim, trades = run_backtest(df_hourly, strategy, config_for_vis, daily_df=df_daily, account_balance=100000)
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
            # Hier kannst du ggf. die Plattform als Parameter übergeben
            visualize_best_result(best_params, platform="binance")
        else:
            logger.error("Kein Ergebnis gefunden, bitte prüfe deine Strategie und Daten.")

if __name__ == "__main__":
    main()
