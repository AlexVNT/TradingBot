import time
import os
import yaml
import pandas as pd
from binance_connector import BinanceConnector

def download_historical_data(symbol: str, interval: str, start_str: str, limit: int = 500):
    """
    Lädt historische OHLCV-Daten von Binance herunter.
    
    :param symbol: Symbol, z. B. "BTCUSDT"
    :param interval: Intervall, z. B. "1h" oder "1d"
    :param start_str: Startdatum als String, z. B. "2024-01-01"
    :param limit: Anzahl der Kerzen pro Abruf (Standard: 500)
    :return: DataFrame mit den historischen Daten
    """
    connector = BinanceConnector(testnet=True)  # Passe testnet je nach Bedarf an
    all_data = []
    start_time = int(pd.Timestamp(start_str).timestamp() * 1000)
    
    while True:
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
            "startTime": start_time
        }
        url = f"{connector.base_url}/fapi/v1/klines"
        response = connector.session.get(url, params=params)
        data = response.json()
        
        if not data or len(data) == 0:
            break
        
        all_data.extend(data)
        last_time = data[-1][0]
        if len(data) < limit:
            break
        start_time = last_time + 1  # Nächste Runde beginnen
        time.sleep(0.5)  # Rate-Limit beachten

    # Konvertiere die abgerufenen Daten in ein DataFrame
    df = pd.DataFrame(
        all_data,
        columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "number_of_trades",
            "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
        ]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    
    # Wandle numerische Spalten in Float um
    numeric_columns = ["open", "high", "low", "close", "volume"]
    df[numeric_columns] = df[numeric_columns].astype(float)
    
    return df

def load_config(config_path="config/config.yaml"):
    """Lädt die Konfigurationsdatei."""
    with open(config_path, "r") as file:
        return yaml.safe_load(file)

if __name__ == "__main__":
    # Lade die Konfiguration und erhalte die Liste der Symbole (Fallback: trade_pair)
    config = load_config()
    symbols = config['trading'].get("symbols", [config['trading'].get("trade_pair", "BTCUSDT")])
    intervals = ["1h", "1d"]
    start_str = "2024-01-01"  # Startdatum für 2024
    
    # Stelle sicher, dass der Ordner zum Speichern existiert
    os.makedirs("data/historical", exist_ok=True)
    
    for symbol in symbols:
        for interval in intervals:
            print(f"Downloading historical data for {symbol} at {interval} interval...")
            df = download_historical_data(symbol, interval, start_str)
            filename = f"data/historical/{symbol}_{interval}_2024_data.csv"
            df.to_csv(filename)
            print(f"Historische Daten für {symbol} ({interval}) wurden in {filename} gespeichert.")
