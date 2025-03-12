# src/backtesting_improved.py
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from math import sqrt
import talib
from strategy import CompositeStrategy, get_daily_trend_with_ema
from utils import logger
from risk_management import calculate_position_size

def load_data(data_file: str) -> pd.DataFrame:
    """
    Lädt Hourly-Daten aus einer CSV- oder Parquet-Datei.
    Setzt den Timestamp als Index und vereinheitlicht die Spaltennamen.
    """
    _, ext = os.path.splitext(data_file.lower())
    if ext == '.parquet':
        df = pd.read_parquet(data_file)
    else:
        df = pd.read_csv(data_file, parse_dates=['timestamp'], index_col='timestamp')
    df.columns = [col.strip().lower().replace(' ', '_') for col in df.columns]
    return df

def load_daily_data(daily_file: str) -> pd.DataFrame:
    """
    Lädt Daily-Daten aus einer CSV-Datei.
    Erwartet Spalten wie: timestamp, open, high, low, close, volume_btc, volume_usdt, etc.
    """
    df = pd.read_csv(daily_file, parse_dates=['timestamp'], index_col='timestamp')
    df.columns = [col.strip().lower().replace(' ', '_') for col in df.columns]
    return df

def run_backtest(df: pd.DataFrame, strategy, config: dict, daily_df: pd.DataFrame, account_balance: float = 100000, symbol: str = None) -> (pd.DataFrame, list):
    """
    Simuliert den Backtest anhand der Hourly-Daten und nutzt den Daily-DataFrame
    als übergeordneten Trendfilter. Falls ein Symbol übergeben wird, wird dieses in
    einer zusätzlichen Spalte abgelegt.
    """
    risk_pct = config['risk_management'].get('risk_pct', 0.01)
    k_atr = config['risk_management'].get('k_atr', 1.5)
    m_atr = config['risk_management'].get('m_atr', 3.0)
    atr_period = config['risk_management'].get('atr_period', 14)
    cooldown_bars = config['risk_management'].get('cooldown_bars', 2)

    df = df.copy()
    # Falls ein Symbol übergeben wurde, füge eine Spalte hinzu:
    if symbol is not None:
        df['symbol'] = symbol

    if 'atr' not in df.columns:
        df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=atr_period)
    
    trades = []
    df['trade'] = 0
    df['profit'] = 0.0

    position = 0    # 0 = keine Position, 1 = Long, -1 = Short
    entry_price = None
    pos_size = 0
    trailing_stop = None
    short_stop_loss = None
    short_take_profit = None
    cooldown = 0

    # Erstelle Signale – übergebe hier die Datenframes an die Strategie
    df['signal'] = df.apply(lambda row: strategy.generate_signal(df.loc[:row.name], daily_df.loc[:row.name.floor('D')]), axis=1)

    for i in range(len(df)):
        current_time = df.index[i]
        signal = df['signal'].iloc[i]
        price = df['close'].iloc[i]
        current_atr = df['atr'].iloc[i]

        if cooldown > 0:
            cooldown -= 1
            continue

        # Positionsmanagement für Long-Positionen
        if position == 1:
            new_trailing_stop = price - k_atr * current_atr
            trailing_stop = new_trailing_stop if trailing_stop is None else max(trailing_stop, new_trailing_stop)
            if price < trailing_stop:
                profit = price - entry_price
                trades.append((current_time, "TRAILING-STOP-LONG", price, profit, pos_size, trailing_stop))
                df.iloc[i, df.columns.get_loc('profit')] = profit
                position = 0
                cooldown = cooldown_bars

        # Positionsmanagement für Short-Positionen
        elif position == -1:
            if price >= short_stop_loss or price <= short_take_profit:
                profit = entry_price - price
                action = "STOP-LOSS-SHORT" if price >= short_stop_loss else "TAKE-PROFIT-SHORT"
                trades.append((current_time, action, price, profit, pos_size, short_stop_loss))
                df.iloc[i, df.columns.get_loc('profit')] = profit
                position = 0
                cooldown = cooldown_bars

        # Neue Positionen eröffnen, wenn keine Position offen ist
        if position == 0:
            if signal == "BUY":
                entry_price = price
                trailing_stop = entry_price - k_atr * current_atr
                pos_size = calculate_position_size(account_balance, risk_pct, entry_price, trailing_stop)
                position = 1
                trades.append((current_time, "LONG-OPEN", price, 0, pos_size, trailing_stop))
                df.iloc[i, df.columns.get_loc('trade')] = 1
            elif signal == "SELL":
                entry_price = price
                short_stop_loss = entry_price + k_atr * current_atr
                short_take_profit = entry_price - m_atr * current_atr
                pos_size = calculate_position_size(account_balance, risk_pct, entry_price, short_stop_loss)
                position = -1
                trades.append((current_time, "SHORT-OPEN", price, 0, pos_size, short_stop_loss))
                df.iloc[i, df.columns.get_loc('trade')] = -1
        else:
            # Positionswechsel: Falls bereits eine Position offen ist und ein entgegengesetztes Signal kommt.
            if position == 1 and signal == "SELL":
                profit = price - entry_price
                trades.append((current_time, "LONG-CLOSE", price, profit, pos_size, trailing_stop))
                df.iloc[i, df.columns.get_loc('profit')] = profit
                entry_price = price
                short_stop_loss = entry_price + k_atr * current_atr
                short_take_profit = entry_price - m_atr * current_atr
                pos_size = calculate_position_size(account_balance, risk_pct, entry_price, short_stop_loss)
                trades.append((current_time, "SHORT-OPEN", price, 0, pos_size, short_stop_loss))
                df.iloc[i, df.columns.get_loc('trade')] = -1
                position = -1
                cooldown = cooldown_bars
            elif position == -1 and signal == "BUY":
                profit = entry_price - price
                trades.append((current_time, "SHORT-CLOSE", price, profit, pos_size, short_stop_loss))
                df.iloc[i, df.columns.get_loc('profit')] = profit
                entry_price = price
                trailing_stop = entry_price - k_atr * current_atr
                pos_size = calculate_position_size(account_balance, risk_pct, entry_price, trailing_stop)
                trades.append((current_time, "LONG-OPEN", price, 0, pos_size, trailing_stop))
                df.iloc[i, df.columns.get_loc('trade')] = 1
                position = 1
                cooldown = cooldown_bars

    return df, trades

def calculate_performance(df: pd.DataFrame, trades: list) -> dict:
    closed_trades = [t for t in trades if "OPEN" not in t[1]]
    total_profit = sum(t[3] for t in closed_trades)
    num_trades = len(closed_trades)
    win_trades = len([t for t in closed_trades if t[3] > 0])
    win_rate = win_trades / num_trades if num_trades > 0 else 0

    gross_profit = sum(t[3] for t in closed_trades if t[3] > 0)
    gross_loss = abs(sum(t[3] for t in closed_trades if t[3] < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    df['cumulative_profit'] = df['profit'].cumsum()
    running_max = df['cumulative_profit'].cummax()
    drawdown = df['cumulative_profit'] - running_max
    max_drawdown = drawdown.min()

    if df['profit'].std() != 0:
        sharpe = (df['profit'].mean() / df['profit'].std()) * sqrt(len(df))
    else:
        sharpe = 0

    return {
        "total_profit": total_profit,
        "num_trades": num_trades,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe
    }

def visualize_backtest(df: pd.DataFrame, trades: list, title="Backtest: Beste Parameter"):
    plt.figure(figsize=(14, 7))
    plt.plot(df.index, df['close'], label="Schlusskurs", color="blue")
    
    # Unterteile Trades in Kategorien
    buy_times = [t[0] for t in trades if "LONG-OPEN" in t[1]]
    buy_prices = [t[2] for t in trades if "LONG-OPEN" in t[1]]
    long_close_times = [t[0] for t in trades if ("LONG-CLOSE" in t[1] or "STOP-LOSS-LONG" in t[1] or "TAKE-PROFIT-LONG" in t[1])]
    long_close_prices = [t[2] for t in trades if ("LONG-CLOSE" in t[1] or "STOP-LOSS-LONG" in t[1] or "TAKE-PROFIT-LONG" in t[1])]

    short_open_times = [t[0] for t in trades if "SHORT-OPEN" in t[1]]
    short_open_prices = [t[2] for t in trades if "SHORT-OPEN" in t[1]]
    short_close_times = [t[0] for t in trades if ("SHORT-CLOSE" in t[1] or "STOP-LOSS-SHORT" in t[1] or "TAKE-PROFIT-SHORT" in t[1])]
    short_close_prices = [t[2] for t in trades if ("SHORT-CLOSE" in t[1] or "STOP-LOSS-SHORT" in t[1] or "TAKE-PROFIT-SHORT" in t[1])]

    plt.scatter(buy_times, buy_prices, marker="^", color="green", s=100, label="LONG-OPEN")
    plt.scatter(long_close_times, long_close_prices, marker="v", color="red", s=100, label="LONG-CLOSE")

    plt.scatter(short_open_times, short_open_prices, marker="v", color="orange", s=100, label="SHORT-OPEN")
    plt.scatter(short_close_times, short_close_prices, marker="^", color="purple", s=100, label="SHORT-CLOSE")

    plt.title(title)
    plt.xlabel("Datum")
    plt.ylabel("Preis")
    plt.legend()
    
    ax = plt.gca()
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=45)
    plt.show()

def main():
    # Beispielhafte Dateipfade (hier werden CSVs als Fallback genutzt)
    hourly_file = "data/historical/BTC_1h_2024.csv"
    daily_file = "data/historical/BTC_1d_2024.csv"
    
    df_hourly = load_data(hourly_file)
    daily_df = load_daily_data(daily_file)
    
    # Beispielhafte Config, die Parameter aus dem Tuning übernimmt
    config = {
        'strategy': {
            'rsi_period': 10,
            'rsi_overbought': 65,
            'rsi_oversold': 35,
            'confirmation_bars': 1,
            'atr_period': 14,
            'ema_period': 50,
            'extended_debug': False,
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
        }
    }
    
    strategy = CompositeStrategy(config)
    # Hier wird auch das Symbol explizit übergeben (Beispiel: "BTCUSDT")
    df_sim, trades = run_backtest(df_hourly, strategy, config, daily_df=df_daily, account_balance=100000, symbol="BTCUSDT")
    perf = calculate_performance(df_sim, trades)
    logger.info(f"Performance: {perf}")
    visualize_backtest(df_sim, trades, title="Backtest: Beste Parameter")
    
if __name__ == "__main__":
    main()
