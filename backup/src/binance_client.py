import os
import requests
from dotenv import load_dotenv
import time
import hashlib
import hmac
import urllib.parse
import ccxt

# Lade die .env-Datei
load_dotenv()

api_key = os.getenv("BINANCE_API_KEY")
secret_key = os.getenv("BINANCE_SECRET_KEY")

# Binance Futures Testnet API
BASE_URL = "https://testnet.binancefuture.com"

def get_balance():
    """Holt das Guthaben vom Binance Futures Testnet über die direkte API."""
    try:
        timestamp = int(time.time() * 1000)  # Aktuelle Zeit in Millisekunden
        query_string = f"timestamp={timestamp}"
        signature = hmac.new(secret_key.encode(), query_string.encode(), hashlib.sha256).hexdigest()
        
        headers = {
            "X-MBX-APIKEY": api_key
        }
        
        url = f"{BASE_URL}/fapi/v2/account?{query_string}&signature={signature}"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            futures_balance = next((asset for asset in data["assets"] if asset["asset"] == "USDT"), None)
            if futures_balance:
                return f"USDT Balance: {futures_balance['walletBalance']}"
            return "❌ Kein Futures-Guthaben gefunden!"
        else:
            return f"❌ API-Fehler: {response.json()}"
    
    except Exception as e:
        return f"❌ Fehler beim Abrufen des Guthabens: {str(e)}"

if __name__ == "__main__":
    print("🔄 Teste die Binance Futures Testnet-Verbindung...")
    balance = get_balance()
    print("💰 Binance Futures Testnet Balance:", balance)
