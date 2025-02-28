import pandas as pd

def load_csv_daily(data_file: str) -> pd.DataFrame:
    """
    Lädt einen Daily-DataFrame aus einer CSV-Datei. Es wird angenommen, dass die
    Spalten 'timestamp', 'open', 'high', 'low', 'close', 'volume_btc', 'volume_usdt' vorhanden sind.
    """
    df = pd.read_csv(data_file, parse_dates=['timestamp'], index_col='timestamp')
    # Spaltennamen vereinheitlichen (Kleinbuchstaben, Unterstriche statt Leerzeichen)
    df.columns = [col.strip().lower().replace(' ', '_') for col in df.columns]
    return df

def resample_hourly_to_daily(df_hourly: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregiert Hourly-Daten zu Daily-Daten.
    """
    df_daily = df_hourly.resample('1D').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume_btc': 'sum',
        'volume_usdt': 'sum'
    })
    return df_daily

def compare_daily_data(df_daily_csv: pd.DataFrame, df_daily_resampled: pd.DataFrame) -> pd.DataFrame:
    """
    Vergleicht zwei Daily-DataFrames und gibt die prozentuale Abweichung für
    Open, High, Low, Close und Volumen zurück.
    """
    # Wir mergen beide DataFrames anhand des Index (timestamp)
    df_compare = df_daily_csv.join(df_daily_resampled, lsuffix='_csv', rsuffix='_res', how='inner')
    metrics = {}
    for col in ['open', 'high', 'low', 'close', 'volume_btc', 'volume_usdt']:
        # Prozentuale Differenz: (Wert_res - Wert_csv) / Wert_csv * 100
        df_compare[f'{col}_diff_pct'] = (df_compare[f'{col}_res'] - df_compare[f'{col}_csv']) / df_compare[f'{col}_csv'] * 100
        metrics[col] = df_compare[f'{col}_diff_pct'].describe()  # Statistische Zusammenfassung
    return df_compare, metrics

if __name__ == "__main__":
    # Dateien anpassen:
    daily_csv_file = "data/historical/BTC_1d_2024.csv"  # Direkter Daily Chart aus CSV
    hourly_csv_file = "data/historical/BTC_1h_2024.csv"       # Hourly Daten, die aggregiert werden sollen

    # Lade Daily CSV
    df_daily_csv = load_csv_daily(daily_csv_file)
    # Lade Hourly CSV und vereinheitliche Spaltennamen
    df_hourly = load_csv_daily(hourly_csv_file)  # Falls die Struktur ähnlich ist
    # Aggregiere die Hourly-Daten zu Daily-Daten
    df_daily_resampled = resample_hourly_to_daily(df_hourly)
    
    # Vergleiche beide Daily DataFrames
    df_compare, metrics = compare_daily_data(df_daily_csv, df_daily_resampled)
    
    print("Vergleich der prozentualen Abweichungen:")
    for col, stats in metrics.items():
        print(f"\n{col.upper()}-Differenz in %:")
        print(stats)
    
    # Optional: Speichere den Vergleich als CSV
    df_compare.to_csv("daily_comparison.csv")
