# src/risk_management.py
def calculate_order_volume(balance, risk_percent, stop_loss_distance, current_price):
    """
    Berechnet das Ordervolumen basierend auf:
      - balance: Aktueller Kontostand
      - risk_percent: Anteil des Kontostands, der riskiert werden soll (z. B. 0.20 für 20%)
      - stop_loss_distance: Distanz in Preis-Einheiten bis zum Stop-Loss
      - current_price: Aktueller Preis des Assets

    Die Formel nimmt an, dass das Risiko (in Geldeinheiten) geteilt wird durch (stop_loss_distance * current_price)
    """
    risk_amount = balance * risk_percent
    if stop_loss_distance * current_price == 0:
        return 0  # Vermeidet Division durch Null
    volume = risk_amount / (stop_loss_distance * current_price)
    return volume
