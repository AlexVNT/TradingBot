# src/single_backtesting.py
from backtesting_improved import load_data, load_daily_data, run_backtest, calculate_performance, visualize_backtest
from strategy import CompositeStrategy
from utils import logger

def main():
    # Dateipfade anpassen – hier werden Hourly- und Daily-Daten aus CSV-Dateien geladen
    hourly_file = "data/historical/BTC_1h_2024.csv"
    daily_file = "data/historical/BTC_1d_2024.csv"
    
    df_hourly = load_data(hourly_file)
    df_daily = load_daily_data(daily_file)
    
    # Konfiguration – hier die "besten" Parameter aus deinem Backtesting-Ergebnis
    config = {
        'strategy': {
            'rsi_period': 10,
            'rsi_overbought': 65,
            'rsi_oversold': 35,
            'confirmation_bars': 1,
            'atr_period': 14,
            'ema_period': 50,
            'extended_debug': True,  # Setze auf True, um detaillierte Debug-Ausgaben zu erhalten
            'rsi_delta': 5,
            'short_delta': 10,
            'debug_frequency': 50
        },
        'risk_management': {
            'risk_pct': 0.01,
            'k_atr': 1.5,
            'm_atr': 3.0,
            'atr_period': 14,
            'cooldown_bars': 2
        },
        'trading': {
            'symbol': "BTC/USDT",
            'timeframe': "1h"
        },
        'binance': {
            'api_key': "${BINANCE_API_KEY}",
            'secret': "${BINANCE_SECRET_KEY}"
        }
    }
    
    # Erstelle die Strategie-Instanz
    strategy = CompositeStrategy(config)
    
    # Führe den Backtest aus (Hourly-Daten + Daily-Daten als Trendfilter)
    df_sim, trades = run_backtest(df_hourly, strategy, config, daily_df=df_daily, account_balance=100000)
    
    # Berechne und logge die Performance
    perf = calculate_performance(df_sim, trades)
    logger.info(f"Performance: {perf}")
    
    # Visualisiere den Backtest
    visualize_backtest(df_sim, trades, title="Single Backtest: Beste Parameter")

if __name__ == "__main__":
    main()
