import talib
import pandas as pd

def get_daily_trend_with_ema(df_daily: pd.DataFrame, ema_period: int = 50) -> str:
    """
    Berechnet den EMA auf dem Daily‑Chart und vergleicht den aktuellen Schlusskurs.
    Gibt "BULLISH" zurück, wenn der Schlusskurs über dem EMA liegt, ansonsten "BEARISH".
    """
    if df_daily.empty or len(df_daily) < ema_period:
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
        # Individuelle Schwellenwerte aus Config (Dictionary) – falls vorhanden:
        self.volume_thresholds = strategy_config.get("volume_thresholds", {})
        self.extended_debug = strategy_config.get("extended_debug", True)

    def generate_signal(self, df_1h: pd.DataFrame, df_daily: pd.DataFrame, current_position: str = "NONE", symbol: str = None) -> str:
        """
        Generiert ein Trading-Signal basierend auf:
          - RSI im 1h-Chart (mit Bestätigung über die letzten confirmation_bars)
          - Übergeordnetem Trend (EMA) auf dem Daily-Chart
          - Optionaler Volumenanalyse (wenn aktiviert)
          - Verhindert doppelte Orders in der gleichen Richtung.

        Liefert umfangreiche Debug-Informationen, um die Entscheidungsfindung nachzuvollziehen.
        """
        if df_1h.empty or df_daily.empty:
            return "HOLD"

        # RSI-Berechnung für den 1h-Chart
        rsi_series = talib.RSI(df_1h['close'], timeperiod=self.rsi_period)
        recent_rsi = rsi_series.iloc[-self.confirmation_bars:]
        rsi_buy = (recent_rsi < self.rsi_oversold).all()
        rsi_sell = (recent_rsi > self.rsi_overbought).all()

        initial_signal = "BUY" if rsi_buy else "SELL" if rsi_sell else "HOLD"

        # Tagestrend berechnen
        daily_trend = get_daily_trend_with_ema(df_daily, ema_period=self.ema_period)
        daily_condition = True
        if initial_signal == "BUY" and daily_trend != "BULLISH":
            daily_condition = False
        if initial_signal == "SELL" and daily_trend != "BEARISH":
            daily_condition = False

        # Volumenfilter anwenden
        if self.volume_filter:
            vol_col = 'volume' if 'volume' in df_1h.columns else 'volume_btc'
            # Hole den individuellen Threshold, falls vorhanden, sonst Standardwert
            threshold = self.volume_thresholds.get(symbol, self.volume_threshold) if symbol is not None else self.volume_threshold
            if threshold is None:
                threshold = 1000  # Fallback-Wert
            volume_ok = df_1h[vol_col].iloc[-1] > threshold
        else:
            threshold = None
            volume_ok = True

        # Prüfe, ob bereits eine Position in derselben Richtung existiert
        duplicate_condition = True
        if (current_position == "LONG" and initial_signal == "BUY") or (current_position == "SHORT" and initial_signal == "SELL"):
            duplicate_condition = False

        # Finale Entscheidung: Nur wenn alle Bedingungen erfüllt sind, wird initial_signal übernommen, sonst HOLD.
        final_signal = initial_signal if (daily_condition and volume_ok and duplicate_condition) else "HOLD"

        if self.extended_debug:
            print(f"[DEBUG] Requested symbol: {symbol}")
            print(f"[DEBUG] RSI values: {list(recent_rsi.round(2))}")
            print(f"[DEBUG] Initial signal based on RSI: {initial_signal}")
            print(f"[DEBUG] Daily trend: {daily_trend} | Daily condition: {daily_condition}")
            if self.volume_filter:
                vol_value = df_1h[vol_col].iloc[-1]
                print(f"[DEBUG] Volume: {vol_value:.2f} | Threshold: {threshold} | Volume condition: {volume_ok}")
            print(f"[DEBUG] Current position: {current_position} | Duplicate condition: {duplicate_condition}")
            print(f"[DEBUG] Final signal: {final_signal}")

        return final_signal
