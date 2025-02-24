import os
from dotenv import load_dotenv

print("🚀 Test gestartet...")  # Debug-Print

# ✅ Expliziten Pfad für die `.env` Datei setzen
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)

# ✅ Teste, ob die API-Keys geladen werden
api_key = os.getenv("BINANCE_API_KEY")
secret_key = os.getenv("BINANCE_SECRET_KEY")

print("🔍 Debugging-Ausgabe:")
print(f"🌍 .env Datei geladen von: {dotenv_path}")  # Prüft, ob die Datei geladen wird
print(f"🔑 API Key: {'Gefunden' if api_key else '❌ NICHT gefunden'}")
print(f"🔑 Secret Key: {'Gefunden' if secret_key else '❌ NICHT gefunden'}")
