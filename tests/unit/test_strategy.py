# src/strategy.py
import talib
import pandas as pd
import pytest


class CompositeStrategy:
    """
    Strategie mit RSI + Bollinger:
      - RSI < oversold => BUY (Long-Signal)
      - RSI > overbought => SELL (Short-Signal)
    Bollinger kann man nutzen, um Signale zu verstärken:
      - Wenn close < BB_lower => starker BUY
      - Wenn close > BB_upper => starker SELL
    """
    @pytest.fixture
    def __init__(self, config):
        self.rsi_period = config['strategy'].get('rsi_period', 14)
        self.overbought = config['strategy'].get('rsi_overbought', 70)
        self.oversold = config['strategy'].get('rsi_oversold', 30)
        self.use_bollinger = config['strategy'].get('use_bollinger', True)
   
    @pytest.fixture
    def generate_signal(self, df: pd.DataFrame) -> str:
        if len(df) < self.rsi_period:
            return "HOLD"
        
        # Berechne RSI
        rsi_series = talib.RSI(df['close'], timeperiod=self.rsi_period)
        current_rsi = rsi_series.iloc[-1]
        
        # Debug-Ausgabe
        print(f"Zeit: {df.index[-1]}, RSI: {current_rsi:.2f}")
        
        if current_rsi < self.oversold:
            return "BUY"
        elif current_rsi > self.overbought:
            return "SELL"
        else:
            return "HOLD"



