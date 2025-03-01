import talib
import pandas as pd

def calculate_rsi(close_prices: pd.Series, period: int = 14) -> pd.Series:
    """ Berechnet den RSI-Indikator. """
    if close_prices.isnull().any():
        close_prices = close_prices.dropna()
    return talib.RSI(close_prices, timeperiod=period)

def calculate_macd(close_prices: pd.Series, fast=12, slow=26, signal=9):
    """ Berechnet den MACD-Indikator. """
    macd, signal_line, hist = talib.MACD(close_prices, fastperiod=fast, slowperiod=slow, signalperiod=signal)
    return {
        "macd": macd,
        "signal": signal_line,
        "hist": hist
    }
