# src/strategy.py
import talib
import pandas as pd

def get_daily_trend(df_daily: pd.DataFrame) -> str:
    if df_daily.empty:
        return "UNKNOWN"
    if df_daily['close'].iloc[-1] > df_daily['open'].iloc[-1]:
        return "BULLISH"
    else:
        return "BEARISH"

class CompositeStrategy:
    def __init__(self, config):
        self.rsi_period = config['strategy'].get('rsi_period', 10)
        self.overbought = config['strategy'].get('rsi_overbought', 65)
        self.oversold = config['strategy'].get('rsi_oversold', 35)
        self.atr_period = config['strategy'].get('atr_period', 14)
        self.confirmation_bars = config['strategy'].get('confirmation_bars', 1)
        self.rsi_delta = config['strategy'].get('rsi_delta', 5)
        self.short_delta = config['strategy'].get('short_delta', 10)
        self.extended_debug = config['strategy'].get('extended_debug', True)
        self.debug_frequency = config['strategy'].get('debug_frequency', 50)
        self.debug_count = 0

    def generate_signal(self, df_1h: pd.DataFrame, df_daily: pd.DataFrame) -> str:
        if len(df_1h) < max(self.rsi_period, self.confirmation_bars):
            return "HOLD"
        
        rsi_series = talib.RSI(df_1h['close'], timeperiod=self.rsi_period)
        recent_rsi = rsi_series.iloc[-self.confirmation_bars:]
        current_time = df_1h.index[-1]
        current_close = df_1h['close'].iloc[-1]
        
        # Debug: Gib den aktuellen 1h Candle mit OHLC aus
        if self.extended_debug:
            current_candle = df_1h.iloc[-1]
            print(f"[DEBUG] Hourly Candle -> Zeit: {current_time}, Open: {current_candle['open']}, High: {current_candle['high']}, Low: {current_candle['low']}, Close: {current_close}")
        
        # Basis-Signal basierend auf RSI
        if (recent_rsi < self.oversold).all():
            signal = "BUY"
        elif (recent_rsi > self.overbought).all():
            signal = "SELL"
        else:
            signal = "HOLD"

        # Ermittle den Tagestrend: Hole nur die Daily-Kerze für den aktuellen Tag
        current_day = current_time.floor('D')
        try:
            # Versuche, genau die Daily-Kerze des aktuellen Tages zu bekommen
            daily_candle = df_daily.loc[current_day]
        except KeyError:
            # Falls der aktuelle Tag nicht existiert, setze Tagestrend auf UNKNOWN
            daily_candle = None

        if daily_candle is not None:
            # Wenn daily_candle eine Serie ist, packe sie in ein DataFrame
            if isinstance(daily_candle, pd.Series):
                daily_candle = pd.DataFrame([daily_candle])
            daily_trend = get_daily_trend(daily_candle)
        else:
            daily_trend = "UNKNOWN"

        if self.extended_debug:
            print(f"[DEBUG] Daily Candle for {current_day} -> {daily_candle.iloc[0].to_dict() if daily_candle is not None else 'None'}")
            print(f"[DEBUG] Tagestrend: {daily_trend}, Vor Filter Signal: {signal}")

        # Filter: Nur BUY zulassen, wenn Tagestrend bullisch; nur SELL, wenn bärisch
        if signal == "BUY" and daily_trend != "BULLISH":
            if self.extended_debug:
                print(f"[DEBUG] BUY-Signal verworfen, Tagestrend: {daily_trend}")
            signal = "HOLD"
        if signal == "SELL" and daily_trend != "BEARISH":
            if self.extended_debug:
                print(f"[DEBUG] SELL-Signal verworfen, Tagestrend: {daily_trend}")
            signal = "HOLD"
        
        return signal

