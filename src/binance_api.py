import os
import time
import hmac
import hashlib
import requests
import urllib.parse
import pandas as pd
from dotenv import load_dotenv

# Lade Umgebungsvariablen
load_dotenv()

API_KEY = os.getenv("BINANCE_API_KEY")
SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")
BASE_URL = "https://testnet.binancefuture.com"

def sign(query_string: str) -> str:
    return hmac.new(SECRET_KEY.encode(), query_string.encode(), hashlib.sha256).hexdigest()

def get_ohlcv(symbol: str, interval: str, limit: int = 500) -> pd.DataFrame:
    """
    Ruft OHLCV-Daten (Klines) vom Binance Futures Testnet ab und gibt sie als DataFrame zurück.
    """
    endpoint = "/fapi/v1/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
        "timestamp": int(time.time() * 1000)
    }
    query_string = urllib.parse.urlencode(params)
    signature = sign(query_string)
    query_string += f"&signature={signature}"
    headers = {"X-MBX-APIKEY": API_KEY}
    url = f"{BASE_URL}{endpoint}?{query_string}"
    
    response = requests.get(url, headers=headers)
    data = response.json()
    if isinstance(data, dict) and "msg" in data:
        raise Exception(f"API-Fehler: {data}")
    
    # Binance gibt eine Liste von Klines zurück; wir konvertieren diese in ein DataFrame
    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 
                                       'close_time', 'quote_asset_volume', 'number_of_trades', 
                                       'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    # Konvertiere numerische Spalten
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    return df

def get_balance() -> float:
    """
    Ruft den USDT-Kontostand vom Binance Futures Testnet ab.
    """
    endpoint = "/fapi/v2/account"
    timestamp = int(time.time() * 1000)
    params = {
        "timestamp": timestamp
    }
    query_string = urllib.parse.urlencode(params)
    signature = sign(query_string)
    query_string += f"&signature={signature}"
    headers = {"X-MBX-APIKEY": API_KEY}
    url = f"{BASE_URL}{endpoint}?{query_string}"
    response = requests.get(url, headers=headers)
    data = response.json()
    if response.status_code != 200:
        raise Exception(f"API-Fehler: {data}")
    futures_balance = next((asset for asset in data["assets"] if asset["asset"] == "USDT"), None)
    if futures_balance:
        return float(futures_balance['walletBalance'])
    else:
        raise Exception("Kein Futures-Guthaben gefunden!")

def create_market_order(symbol: str, side: str, quantity: float) -> dict:
    """
    Platziert eine Market Order auf dem Binance Futures Testnet.
    """
    endpoint = "/fapi/v1/order"
    timestamp = int(time.time() * 1000)
    params = {
        "symbol": symbol,
        "side": side.upper(),  # BUY oder SELL
        "type": "MARKET",
        "quantity": quantity,
        "timestamp": timestamp
    }
    query_string = urllib.parse.urlencode(params)
    signature = sign(query_string)
    query_string += f"&signature={signature}"
    headers = {"X-MBX-APIKEY": API_KEY}
    url = f"{BASE_URL}{endpoint}?{query_string}"
    
    response = requests.post(url, headers=headers)
    data = response.json()
    if response.status_code != 200:
        raise Exception(f"Order-Fehler: {data}")
    return data
