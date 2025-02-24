# src/indicators.py
import talib

def calculate_rsi(close_prices, period=14):
    return talib.RSI(close_prices, timeperiod=period)

def calculate_macd(close_prices):
    macd, signal, hist = talib.MACD(close_prices, fastperiod=12, slowperiod=26, signalperiod=9)
    return macd, signal, hist
