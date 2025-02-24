# src/strategy.py
import talib
import pandas as pd

class CompositeStrategy:
    def __init__(self, config):
        strategy_config = config.get("strategy", {})
        self.rsi_period = strategy_config.get("rsi_period", 14)
        self.overbought = strategy_config.get("rsi_overbought", 70)
        self.oversold = strategy_config.get("rsi_oversold", 30)
    
    def generate_signal(self, df: pd.DataFrame) -> str:
        # Berechne RSI
        df['RSI'] = talib.RSI(df['close'], timeperiod=self.rsi_period)
        
        # Berechne MACD
        macd, macd_signal, _ = talib.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
        df['MACD'] = macd
        
        # Berechne Bollinger Bands
        upper, middle, lower = talib.BBANDS(df['close'], timeperiod=20)
        df['Upper'] = upper
        df['Lower'] = lower

        latest_rsi = df['RSI'].iloc[-1]
        latest_macd = df['MACD'].iloc[-1]
        latest_price = df['close'].iloc[-1]
        latest_lower = df['Lower'].iloc[-1]
        latest_upper = df['Upper'].iloc[-1]

        # Kombiniertes Signal basierend auf RSI, MACD und Bollinger Bands:
        if latest_rsi < self.oversold and latest_macd > 0 and latest_price <= latest_lower * 1.01:
            return "BUY"
        elif latest_rsi > self.overbought and latest_macd < 0 and latest_price >= latest_upper * 0.99:
            return "SELL"
        return "HOLD"
