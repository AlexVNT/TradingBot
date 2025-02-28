# src/ohlcv_fetcher.py
import requests
import pandas as pd

def fetch_ohlcv(symbol, interval, limit=500):
    """
    Ruft OHLCV-Daten direkt von der Binance Futures Live API ab.
    Da das Testnet für öffentliche Endpunkte nicht existiert, nutzen wir den Live-Endpoint.
    """
    # Falls symbol als Liste übergeben wird, wähle das erste Element aus.
    if isinstance(symbol, list):
        symbol = symbol[0]
    
    # Entferne den Slash, falls vorhanden:
    symbol = symbol.replace("/", "")
    
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    
    df = pd.DataFrame(data, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'num_trades',
        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
    ])
    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    
    numeric_columns = ['open', 'high', 'low', 'close', 'volume']
    df[numeric_columns] = df[numeric_columns].astype(float)
    
    return df

if __name__ == "__main__":
    df = fetch_ohlcv("BTC/USDT", "1h")
    print(df.head())
