# src/single_backtesting.py
from backtesting_improved import (
    load_data,
    load_daily_data,
    run_backtest,
    calculate_performance,
    visualize_backtest
)
from strategy import CompositeStrategy
from utils import logger

def main():
    # Hourly-Daten (1h)
    hourly_file = "data/historical/BTC_1h_2024.csv"
    df_hourly = load_data(hourly_file)

    # Daily-Daten (separat)
    daily_file = "data/historical/BTC_1d_2024.csv"
    df_daily = load_daily_data(daily_file)

    # Beste Parameter laut Grid Search
    best_config = {
        'strategy': {
            'rsi_period': 10,
            'rsi_oversold': 35,
            'rsi_overbought': 65,
            'confirmation_bars': 1,
            'atr_period': 14,
            # optional: 'extended_debug': True
        },
        'risk_management': {
            'risk_pct': 0.01,
            'k_atr': 1.5,
            'm_atr': 3.0,
            'atr_period': 14,
            'cooldown_bars': 2
        }
    }
    strategy = CompositeStrategy(best_config)

    df_sim, trades = run_backtest(df_hourly, strategy, best_config, df_daily)
    metrics = calculate_performance(df_sim, trades)
    logger.info(f"Performance: {metrics}")
    visualize_backtest(df_sim, trades, title="Single Backtest: Beste Parameter")

if __name__ == "__main__":
    main()
