import os
from dotenv import load_dotenv

# Lade .env-Datei
load_dotenv()

# Prüfe, ob die Variablen geladen wurden
print("BINANCE_TESTNET_API_KEY:", os.getenv("BINANCE_TESTNET_API_KEY"))
print("BINANCE_TESTNET_SECRET_KEY:", os.getenv("BINANCE_TESTNET_SECRET_KEY"))
