#src/strategy.py
import talib
import yaml
import os
import pandas as pd
import numpy as np
from src.utils import logger
from datetime import timedelta

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')

def load_config():
    with open(CONFIG_PATH, "r") as file:
        return yaml.safe_load(file)

config = load_config()

def get_higher_trend_with_gradient(df_higher: pd.DataFrame, lookback: int = 5) -> str:
    if df_higher.empty or len(df_higher) < lookback + 1:
        logger.warning("Nicht genug H4-Daten für Trendbestimmung")
        return "UNKNOWN"
    closes = df_higher['close'].iloc[-lookback:]
    if closes.isnull().any():
        logger.warning("Ungültige H4-Daten (NaN-Werte)")
        return "UNKNOWN"
    price_changes = np.diff(closes)
    trend_score = np.mean(price_changes)
    if trend_score > 0.00005:
        logger.debug(f"BULLISH: Closes {list(closes)}, Trend Score {trend_score:.5f}")
        return "BULLISH"
    elif trend_score < -0.00005:
        logger.debug(f"BEARISH: Closes {list(closes)}, Trend Score {trend_score:.5f}")
        return "BEARISH"
    else:
        logger.debug(f"NEUTRAL: Closes {list(closes)}, Trend Score {trend_score:.5f}")
        return "NEUTRAL"

def detect_friday_close_or_monday_pause(current_time, df_1h, block_hours=4):
    if current_time.weekday() == 4 and current_time.hour >= 20:
        logger.info(f"Freitag {current_time}: Schließe alle Positionen vor dem Wochenende")
        return "CLOSE_ALL"
    if current_time.weekday() == 0:
        first_monday_time = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        hours_since_open = (current_time - first_monday_time).total_seconds() / 3600
        if hours_since_open <= block_hours:
            logger.debug(f"Montag {current_time}: Signale für {block_hours - hours_since_open:.2f} Stunden blockiert")
            return "BLOCK"
    return None

class CompositeStrategy:
    def __init__(self, config, symbol=None, balance=None):
        self.config = config
        strategy_config = config.get("strategy", {})
        risk_config = config.get("risk_management", {})
        self.rsi_period = strategy_config.get("rsi_period", 5)
        self.rsi_overbought = strategy_config.get("rsi_overbought", 75)
        self.rsi_oversold = strategy_config.get("rsi_oversold", 25)
        self.atr_period = strategy_config.get("atr_period", 14)
        self.lookback = strategy_config.get("lookback", 5)
        self.volume_filter = strategy_config.get("volume_filter", False)
        self.volume_threshold = strategy_config.get("volume_threshold", None)
        self.extended_debug = strategy_config.get("extended_debug", True)
        self.gap_threshold = strategy_config.get("gap_threshold", 0.005)
        self.gap_block_hours = strategy_config.get("gap_block_hours", 4)
        self.volume_weight = strategy_config.get("volume_weight", 0.5)
        self.initial_balance = risk_config.get("initial_balance", 16000)
        self.base_risk = risk_config.get("base_risk", 0.01)
        self.dynamic_risk_factor = risk_config.get("dynamic_risk_factor", 0.001)
        self.balance = balance if balance is not None else self.initial_balance
        
        # Plattform-spezifische Parameter laden
        if symbol:
            if config["platforms"]["metatrader"] and "metatrader" in config["trading"]:
                symbol_params = config["trading"]["metatrader"]["symbols"].get(symbol, {})
            elif config["platforms"]["binance"] and "binance" in config["trading"]:
                symbol_params = config["trading"]["binance"]["symbols"].get(symbol, {})
            else:
                symbol_params = {}
            self.atr_tp_multiplier = symbol_params.get("atr_tp_multiplier", strategy_config.get("atr_tp_multiplier", 6.0))
            self.atr_sl_multiplier = symbol_params.get("atr_sl_multiplier", strategy_config.get("atr_sl_multiplier", 1.5))
        else:
            self.atr_tp_multiplier = strategy_config.get("atr_tp_multiplier", 6.0)
            self.atr_sl_multiplier = strategy_config.get("atr_sl_multiplier", 1.5)
        
        self.highest_price = None
        self.lowest_price = None
        self.prev_rsi = None
        self.prev_volume = None

    def calculate_risk(self):
        return self.initial_balance * self.base_risk + self.balance * self.dynamic_risk_factor

    def generate_signal(self, df_1h: pd.DataFrame, df_higher: pd.DataFrame, current_position: str = "NONE", symbol: str = None, entry_price: float = None) -> str:
        if df_1h.empty or df_higher.empty or len(df_1h) < max(self.rsi_period, self.atr_period) + 1:
            logger.warning("Daten leer oder nicht genug Daten – Signal: HOLD")
            return "HOLD"

        rsi_series = talib.RSI(df_1h['close'], timeperiod=self.rsi_period)
        current_rsi = rsi_series.iloc[-1]
        prev_rsi = rsi_series.iloc[-2] if len(rsi_series) > 1 else None
        rsi_buy = prev_rsi is not None and prev_rsi <= self.rsi_oversold and current_rsi > self.rsi_oversold
        rsi_sell = prev_rsi is not None and prev_rsi >= self.rsi_overbought and current_rsi < self.rsi_overbought
        initial_signal = "BUY" if rsi_buy else "SELL" if rsi_sell else "HOLD"

        higher_trend = get_higher_trend_with_gradient(df_higher, lookback=self.lookback)

        trend_condition = True
        if higher_trend == "NEUTRAL":
            trend_condition = False
        elif initial_signal == "BUY" and higher_trend != "BULLISH":
            trend_condition = False
        elif initial_signal == "SELL" and higher_trend != "BEARISH":
            trend_condition = False

        current_time = df_1h.index[-1]
        weekend_action = detect_friday_close_or_monday_pause(current_time, df_1h, self.gap_block_hours)
        if weekend_action == "CLOSE_ALL":
            if current_position == "LONG":
                return "CLOSE_LONG"
            elif current_position == "SHORT":
                return "CLOSE_SHORT"
            return "HOLD"
        elif weekend_action == "BLOCK":
            initial_signal = "HOLD"
            logger.info("Signale blockiert wegen Montag-Pause")

        if current_position == "LONG" and entry_price is not None:
            atr = talib.ATR(df_1h['high'], df_1h['low'], df_1h['close'], timeperiod=self.atr_period).iloc[-1]
            current_price = df_1h['close'].iloc[-1]
            stop_loss = entry_price - self.atr_sl_multiplier * atr
            if self.highest_price is None or current_price > self.highest_price:
                self.highest_price = current_price
            trailing_tp = self.highest_price - self.atr_tp_multiplier * atr
            if self.extended_debug:
                print(f"[DEBUG] ATR: {atr:.5f}, Trailing TP: {trailing_tp:.5f}, SL: {stop_loss:.5f}, Current: {current_price:.5f}, Highest: {self.highest_price:.5f}")
            if current_price <= trailing_tp or current_price <= stop_loss or (higher_trend == "BEARISH" and current_position == "LONG"):
                self.highest_price = None
                return "CLOSE_LONG"
        elif current_position == "SHORT" and entry_price is not None:
            atr = talib.ATR(df_1h['high'], df_1h['low'], df_1h['close'], timeperiod=self.atr_period).iloc[-1]
            current_price = df_1h['close'].iloc[-1]
            stop_loss = entry_price + self.atr_sl_multiplier * atr
            if self.lowest_price is None or current_price < self.lowest_price:
                self.lowest_price = current_price
            trailing_tp = self.lowest_price + self.atr_tp_multiplier * atr
            if self.extended_debug:
                print(f"[DEBUG] ATR: {atr:.5f}, Trailing TP: {trailing_tp:.5f}, SL: {stop_loss:.5f}, Current: {current_price:.5f}, Lowest: {self.lowest_price:.5f}")
            if current_price >= trailing_tp or current_price >= stop_loss or (higher_trend == "BULLISH" and current_position == "SHORT"):
                self.lowest_price = None
                return "CLOSE_SHORT"

        if current_position == "NONE":
            self.highest_price = None
            self.lowest_price = None

        duplicate_condition = True
        if (current_position == "LONG" and initial_signal == "BUY") or (current_position == "SHORT" and initial_signal == "SELL"):
            duplicate_condition = False

        if self.extended_debug:
            current_time = df_1h.index[-1]
            current_close = df_1h['close'].iloc[-1]
            print(f"[DEBUG] Zeit: {current_time}, RSI: {current_rsi:.2f}, Close: {current_close:.2f}")
            print(f"[DEBUG] Tagestrend (Gradient Lookback {self.lookback}): {higher_trend}")
            print(f"[DEBUG] Requested symbol: {symbol}")
            print(f"[DEBUG] RSI values: {current_rsi:.2f}")
            print(f"[DEBUG] Initial signal based on RSI: {initial_signal}")
            print(f"[DEBUG] Trend condition: {trend_condition}")
            print(f"[DEBUG] Current position: {current_position} | Duplicate condition: {duplicate_condition}")

        final_signal = initial_signal if (trend_condition and duplicate_condition) else "HOLD"
        if self.extended_debug:
            print(f"[DEBUG] Final signal: {final_signal}")
        return final_signal