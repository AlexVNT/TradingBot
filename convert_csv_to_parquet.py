#!/usr/bin/env python
import pandas as pd
import argparse
import os

def convert_csv_to_parquet(csv_file, parquet_file=None):
    print(f"Lade CSV-Datei: {csv_file}")
    try:
        # Wenn deine CSV ein Zeitstempel-Feld namens 'timestamp' hat, kannst du z.B. parse_dates=['timestamp'] setzen
        df = pd.read_csv(csv_file, parse_dates=['timestamp'])
    except Exception as e:
        print("Fehler beim Laden der CSV-Datei:", e)
        return

    if parquet_file is None:
        base, _ = os.path.splitext(csv_file)
        parquet_file = base + ".parquet"

    print(f"Speichere als Parquet-Datei: {parquet_file}")
    try:
        df.to_parquet(parquet_file)
        print("Konvertierung erfolgreich abgeschlossen!")
    except Exception as e:
        print("Fehler beim Speichern der Parquet-Datei:", e)

def main():
    parser = argparse.ArgumentParser(description="Konvertiert eine CSV-Datei in das Parquet-Format.")
    parser.add_argument("csv_file", help="Pfad zur CSV-Datei, die konvertiert werden soll")
    parser.add_argument("-o", "--output", help="Pfad zur Ausgabedatei (Parquet). Standard: gleicher Name wie CSV mit .parquet")
    args = parser.parse_args()

    convert_csv_to_parquet(args.csv_file, args.output)

if __name__ == "__main__":
    main()
