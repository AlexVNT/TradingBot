import talib
import pandas as pd

def get_daily_trend_with_ema(df_daily: pd.DataFrame, ema_period: int = 50) -> str:
    """
    Berechnet den EMA auf dem Daily‑Chart und vergleicht den aktuellen Schlusskurs.
    Gibt "BULLISH" zurück, wenn der Schlusskurs über dem EMA liegt, ansonsten "BEARISH".
    """
    if df_daily.empty:
        return "UNKNOWN"
    ema = talib.EMA(df_daily['close'], timeperiod=ema_period)
    last_close = df_daily['close'].iloc[-1]
    last_ema = ema.iloc[-1]
    return "BULLISH" if last_close > last_ema else "BEARISH"

class CompositeStrategy:
    def __init__(self, config):
        strategy_config = config.get("strategy", {})
        self.rsi_period = strategy_config.get("rsi_period", 10)
        self.rsi_overbought = strategy_config.get("rsi_overbought", 65)
        self.rsi_oversold = strategy_config.get("rsi_oversold", 30)
        self.confirmation_bars = strategy_config.get("confirmation_bars", 1)
        self.atr_period = strategy_config.get("atr_period", 14)
        self.ema_period = strategy_config.get("ema_period", 50)
        self.volume_filter = strategy_config.get("volume_filter", False)
        self.volume_threshold = strategy_config.get("volume_threshold", None)
        self.extended_debug = strategy_config.get("extended_debug", True)

    def generate_signal(self, df_1h: pd.DataFrame, df_daily: pd.DataFrame, current_position: str = "NONE") -> str:
        """
        Generiert ein Signal basierend auf:
          - RSI im 1h-Chart (mit Bestätigung über die letzten confirmation_bars)
          - Übergeordnetem Trend (EMA) auf dem Daily-Chart
          - Optionaler Volumenanalyse (wenn aktiviert)
        Unterdrückt Long-Signale, wenn current_position "LONG" ist, und Short-Signale,
        wenn current_position "SHORT" ist.
        """
        if len(df_1h) < max(self.rsi_period, self.confirmation_bars):
            return "HOLD"
        
        # Berechne RSI für den 1h-Chart
        rsi_series = talib.RSI(df_1h['close'], timeperiod=self.rsi_period)
        recent_rsi = rsi_series.iloc[-self.confirmation_bars:]
        
        # Basis-Signal: BUY, wenn alle RSI-Werte unter rsi_oversold; SELL, wenn alle über rsi_overbought
        if (recent_rsi < self.rsi_oversold).all():
            signal = "BUY"
        elif (recent_rsi > self.rsi_overbought).all():
            signal = "SELL"
        else:
            signal = "HOLD"
        
        # Trendfilter: Berechne den übergeordneten Trend mittels EMA auf dem Daily-Chart
        daily_trend = get_daily_trend_with_ema(df_daily, ema_period=self.ema_period)
        
        # Optionale Volumenanalyse
        volume_ok = True
        if self.volume_filter and self.volume_threshold is not None:
            vol_col = 'volume' if 'volume' in df_1h.columns else 'volume_btc'
            volume_ok = df_1h[vol_col].iloc[-1] > self.volume_threshold
            if self.extended_debug:
                print(f"[DEBUG] Volume ({vol_col}): {df_1h[vol_col].iloc[-1]:.2f} (Threshold: {self.volume_threshold}) -> {volume_ok}")

        if self.extended_debug:
            current_time = df_1h.index[-1]
            current_close = df_1h['close'].iloc[-1]
            print(f"[DEBUG] Zeit: {current_time}, Recent RSI: {list(recent_rsi.round(2))}, Close: {current_close:.2f}")
            print(f"[DEBUG] Tagestrend (EMA {self.ema_period}): {daily_trend}")
            if self.volume_filter:
                vol_col = 'volume' if 'volume' in df_1h.columns else 'volume_btc'
                vol_value = df_1h[vol_col].iloc[-1]
                print(f"[DEBUG] {vol_col.capitalize()}: {vol_value:.2f} (Threshold: {self.volume_threshold}) -> {volume_ok}")

        # Filtere das Signal basierend auf dem übergeordneten Trend und Volumen
        if signal == "BUY" and daily_trend != "BULLISH":
            if self.extended_debug:
                print("[DEBUG] BUY-Signal verworfen, da Tagestrend nicht bullisch.")
            signal = "HOLD"
        if signal == "SELL" and daily_trend != "BEARISH":
            if self.extended_debug:
                print("[DEBUG] SELL-Signal verworfen, da Tagestrend nicht bärisch.")
            signal = "HOLD"
        if not volume_ok:
            if self.extended_debug:
                print("[DEBUG] Signal verworfen, da Volumen-Kriterium nicht erfüllt ist.")
            signal = "HOLD"
        
        # Unterdrücke gleichgerichtete Signale, wenn bereits eine Position offen ist
        if current_position.upper() == "LONG" and signal == "BUY":
            if self.extended_debug:
                print("[DEBUG] BUY-Signal unterdrückt, da bereits eine LONG-Position offen ist.")
            return "HOLD"
        if current_position.upper() == "SHORT" and signal == "SELL":
            if self.extended_debug:
                print("[DEBUG] SELL-Signal unterdrückt, da bereits eine SHORT-Position offen ist.")
            return "HOLD"
        
        return signal
