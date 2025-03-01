import os
import time
import hmac
import hashlib
import requests
import urllib.parse
import pandas as pd
from dotenv import load_dotenv

load_dotenv()


class BinanceConnector:
    """Hauptklasse für die Binance API (Live & Testnet)."""

    def __init__(self, testnet=True):
        self.api_key = (
            os.getenv("BINANCE_TESTNET_API_KEY")
            if testnet
            else os.getenv("BINANCE_API_KEY")
        )
        self.secret_key = (
            os.getenv("BINANCE_TESTNET_SECRET_KEY")
            if testnet
            else os.getenv("BINANCE_SECRET_KEY")
        )
        self.base_url = (
            "https://testnet.binancefuture.com"
            if testnet
            else "https://api.binance.com"
        )
        self.session = requests.Session()
        self.session.headers.update({"X-MBX-APIKEY": self.api_key})

        # ✅ API-Schlüssel Überprüfung
        if not self.api_key or not self.secret_key:
            raise ValueError(
                "❌ API-Schlüssel oder Secret nicht gefunden! Bitte `.env` prüfen."
            )

    def sign(self, query_string: str) -> str:
        """Erstellt die Signatur für API-Anfragen."""
        return hmac.new(
            self.secret_key.encode(), query_string.encode(), hashlib.sha256
        ).hexdigest()

    def get_server_time(self):
        """Holt die aktuelle Serverzeit von Binance (Live & Testnet unterscheiden)."""
        endpoint = "/api/v3/time" if "binance.com" in self.base_url else "/fapi/v1/time"
        url = f"{self.base_url}{endpoint}"
        response = self.session.get(url)
        return response.json()

    def get_account_info(self):
        """Ruft die Kontoinformationen von Binance ab."""
        endpoint = "/fapi/v2/account"
        timestamp = int(time.time() * 1000)
        params = {"timestamp": timestamp}
        query_string = urllib.parse.urlencode(params)
        query_string += f"&signature={self.sign(query_string)}"
        url = f"{self.base_url}{endpoint}?{query_string}"

        response = self.session.get(url)
        data = response.json()

        print("🔍 API Response:", data)  # Debugging-Ausgabe

        if response.status_code != 200:
            raise Exception(f"API-Fehler: {data}")
        return data

    def get_balance(self, asset="USDT") -> float:
        """Ruft das Futures-Guthaben für das angegebene Asset ab."""
        account_info = self.get_account_info()
        if "assets" in account_info:
            for asset_data in account_info["assets"]:
                if asset_data["asset"] == asset:
                    return float(asset_data["walletBalance"])
        raise Exception(f"Kein Futures-Guthaben für {asset} gefunden!")

    def get_ohlcv(self, symbol: str, interval: str, limit: int = 500) -> pd.DataFrame:
        """Holt OHLCV-Daten als Pandas DataFrame."""
        endpoint = "/fapi/v1/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
            "timestamp": int(time.time() * 1000),
        }
        query_string = urllib.parse.urlencode(params)
        query_string += f"&signature={self.sign(query_string)}"
        url = f"{self.base_url}{endpoint}?{query_string}"

        response = self.session.get(url)
        data = response.json()
        if isinstance(data, dict) and "msg" in data:
            raise Exception(f"API-Fehler: {data}")

        df = pd.DataFrame(
            data,
            columns=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_asset_volume",
                "number_of_trades",
                "taker_buy_base_asset_volume",
                "taker_buy_quote_asset_volume",
                "ignore",
            ],
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def create_market_order(self, symbol: str, side: str, quantity: float) -> dict:
        """Platziert eine Market Order."""
        endpoint = "/fapi/v1/order"
        timestamp = int(time.time() * 1000)
        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": "MARKET",
            "quantity": quantity,
            "timestamp": timestamp,
        }
        query_string = urllib.parse.urlencode(params)
        query_string += f"&signature={self.sign(query_string)}"
        url = f"{self.base_url}{endpoint}?{query_string}"

        response = self.session.post(url, data=params)
        data = response.json()
        if response.status_code != 200:
            raise Exception(f"Order-Fehler: {data}")
        return data


# ✅ Testnet-Klasse erbt von BinanceConnector
class BinanceTestnetConnector(BinanceConnector):
    """Binance API Connector für das Testnet."""

    def __init__(self):
        super().__init__(testnet=True)
