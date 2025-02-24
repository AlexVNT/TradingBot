import os
from dotenv import load_dotenv

# ✅ Lade die .env Datei
load_dotenv()

# ✅ Teste, ob die API-Keys geladen werden
print("API Key:", os.getenv("BINANCE_API_KEY"))
print("Secret Key:", os.getenv("BINANCE_SECRET_KEY"))