# src/risk_management.py

def calculate_position_size(account_balance: float, risk_pct: float, entry_price: float, stop_loss_price: float) -> float:
    """
    Berechnet die Positionsgröße basierend auf:
      - account_balance: Gesamtkapital
      - risk_pct: Der Anteil des Kapitals, den man pro Trade riskieren möchte (z.B. 0.01 für 1%)
      - entry_price: Der Einstiegspreis
      - stop_loss_price: Der Preis, bei dem der Trade geschlossen wird (Stop-Loss)
      
    Die Positionsgröße entspricht:
        positions_size = (account_balance * risk_pct) / (|entry_price - stop_loss_price|)
        
    Diese Formel geht davon aus, dass der Trade in einer Einheit gehandelt wird (z. B. Stück, Contract etc.).
    """
    risk_amount = account_balance * risk_pct
    stop_loss_distance = abs(entry_price - stop_loss_price)
    
    if stop_loss_distance == 0:
        return 0  # Vermeide Division durch Null
    
    position_size = risk_amount / stop_loss_distance
    return position_size
