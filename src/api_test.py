import ccxt
import os
from dotenv import load_dotenv

# Lade .env (sicherstellen, dass BINANCE_API_KEY und BINANCE_SECRET_KEY gesetzt sind)
load_dotenv()

api_key = os.getenv("BINANCE_API_KEY")
secret = os.getenv("BINANCE_SECRET_KEY")

# Konfiguriere die Binance Futures Testnet-Instanz
exchange = ccxt.binance({
    "apiKey": api_key,
    "secret": secret,
    "enableRateLimit": True,
    "test": True,  # Testnet aktivieren
    "options": {
         "defaultType": "future",
         "adjustForTimeDifference": True,
    }
})
exchange.verbose = True

# Überschreibe manuell die Endpoints für Testnet
exchange.urls['api'] = "https://testnet.binancefuture.com"
exchange.urls['fapiPublic'] = "https://testnet.binancefuture.com"
exchange.urls['fapiPrivate'] = "https://testnet.binancefuture.com/fapi/v1"

# Entferne den SAPI-Endpoint, falls vorhanden (CCXT neigt dazu, diesen automatisch zu nutzen)
if 'sapi' in exchange.urls:
    del exchange.urls['sapi']

# Gib die verwendeten URLs aus, um zu kontrollieren:
print("Verwendete Endpoints:")
for key, url in exchange.urls.items():
    print(f"{key}: {url}")

# Teste eine einfache API-Abfrage: z.B. das Abrufen des Kontostands über den direkten HTTP-Aufruf
import time, hmac, hashlib, requests

def get_balance_direct():
    BASE_URL = "https://testnet.binancefuture.com"
    timestamp = int(time.time() * 1000)
    query_string = f"timestamp={timestamp}"
    signature = hmac.new(secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    headers = {
        "X-MBX-APIKEY": api_key
    }
    url = f"{BASE_URL}/fapi/v2/account?{query_string}&signature={signature}"
    response = requests.get(url, headers=headers)
    return response.json()

print("\nDirekter API-Test (Balance):")
balance = get_balance_direct()
print(balance)

# Alternativ: Mit CCXT versuchen, den Balance abzurufen
try:
    ccxt_balance = exchange.fetch_balance()
    print("\nCCXT fetch_balance Ergebnis:")
    print(ccxt_balance)
except Exception as e:
    print("\nFehler bei fetch_balance:", e)
