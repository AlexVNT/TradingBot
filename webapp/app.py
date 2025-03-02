from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import yaml
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'dein_geheimer_schlüssel'  # Für Flash-Messages etc.

# Pfade zur Konfigurationsdatei und Log-Datei
CONFIG_PATH = os.path.join('..', 'config', 'config.yaml')
LOG_FILE_PATH = os.path.join('..', 'logs', 'tradingbot.log')

@app.route('/')
def dashboard():
    # Hier könntest du echte Performance-Metriken und Backtest-Ergebnisse einbinden.
    # Im Beispiel nutzen wir Dummy-Daten.
    performance = {
        'Profit': 1500.0,
        'Win-Rate': '60%',
        'Drawdown': '5%',
        'Sharpe-Ratio': 1.5
    }
    # Beispiel-Daten für ein Chart
    chart_data = {
        'labels': ["Jan", "Feb", "Mär", "Apr", "Mai"],
        'values': [1000, 1200, 1500, 1300, 1600]
    }
    return render_template('dashboard.html', performance=performance, chart_data=chart_data)

@app.route('/config', methods=['GET', 'POST'])
def config_view():
    if request.method == 'POST':
        # Aktualisierte Konfiguration speichern
        new_config = request.form.get('config_content')
        try:
            # Validierung: Prüfen, ob es gültiges YAML ist
            yaml.safe_load(new_config)
            # In die Konfigurationsdatei schreiben
            with open(CONFIG_PATH, 'w') as file:
                file.write(new_config)
            flash('Konfiguration erfolgreich gespeichert!', 'success')
        except yaml.YAMLError as e:
            flash(f'Fehler beim Parsen der YAML: {e}', 'danger')
        return redirect(url_for('config_view'))
    else:
        # Konfiguration laden
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r') as file:
                config_content = file.read()
        else:
            config_content = '# Keine Konfigurationsdatei gefunden!'
        return render_template('config.html', config_content=config_content)

@app.route('/logs')
def logs_view():
    # Log-Datei laden
    if os.path.exists(LOG_FILE_PATH):
        with open(LOG_FILE_PATH, 'r') as file:
            logs = file.read()
    else:
        logs = 'Keine Log-Datei gefunden.'
    return render_template('logs.html', logs=logs)

# Beispiel einer API-Route für die dynamische Aktualisierung der Logs (z.B. via Ajax)
@app.route('/api/logs')
def api_logs():
    if os.path.exists(LOG_FILE_PATH):
        with open(LOG_FILE_PATH, 'r') as file:
            logs = file.read()
    else:
        logs = 'Keine Log-Datei gefunden.'
    return jsonify({'logs': logs, 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    # Starte die App unter http://localhost:5000
    app.run(debug=True, host='127.0.0.1', port=5000)
