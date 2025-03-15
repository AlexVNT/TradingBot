from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import yaml
import time  # Hinzufügen am Anfang der Datei
from datetime import datetime
from src.backtesting_improved import run_backtest
from src.bot import TradingBot
from src.tuning import tune_all_symbols
from src.ohlcv_fetcher import fetch_ohlcv
from src.strategy import CompositeStrategy
from src.metatrader_connector import MetaTraderConnector
import MetaTrader5 as mt5
import threading
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = 'dein_geheimer_schlüssel'
CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')

BOT_RUNNING = False
bot_instance = None
bot_thread = None

def load_config():
    with open(CONFIG_PATH, 'r') as file:
        return yaml.safe_load(file)

@app.route('/', methods=['GET', 'POST'])
def dashboard():
    config = load_config()
    platforms = [p for p, enabled in config['platforms'].items() if enabled]
    selected_platform = request.form.get('platform') if request.method == 'POST' and request.form.get('platform') in platforms else (session.get('selected_platform') or (platforms[0] if platforms else 'binance'))
    trade_conf = config['trading'][selected_platform]
    symbols = list(trade_conf['symbols'].keys())
    current_symbol = request.form.get('symbol') if request.method == 'POST' and request.form.get('symbol') in symbols else session.get('selected_symbol')
    if current_symbol and current_symbol in symbols:
        selected_symbol = current_symbol
    else:
        selected_symbol = symbols[0] if symbols else 'BTCUSDT'

    interval = trade_conf.get('timeframe', '1h')

    print(f"Dashboard - Selected Platform: {selected_platform}, Selected Symbol: {selected_symbol}, Session Before: {session.get('selected_symbol')}")
    session['selected_platform'] = selected_platform
    session['selected_symbol'] = selected_symbol
    print(f"Session After: {session.get('selected_symbol')}")

    backtest_file = os.path.join('..', 'results', f'backtest_summary_{selected_platform}_{selected_symbol}.csv')
    if os.path.exists(backtest_file):
        backtest_results = pd.read_csv(backtest_file)
        profit = backtest_results['profit'].sum() if 'profit' in backtest_results.columns else 0
        win_rate = backtest_results['win_rate'].iloc[-1] if 'win_rate' in backtest_results.columns and not backtest_results.empty else 0
        max_drawdown = backtest_results['max_drawdown'].iloc[-1] if 'max_drawdown' in backtest_results.columns and not backtest_results.empty else None
        sharpe = backtest_results['sharpe'].iloc[-1] if 'sharpe' in backtest_results.columns and not backtest_results.empty else None
        labels = backtest_results['entry_time'].dropna().tolist() if 'entry_time' in backtest_results.columns else ["Start", "End"]
        values = backtest_results['profit'].fillna(0).cumsum().tolist() if 'profit' in backtest_results.columns else [0, 0]
    else:
        profit = 0
        win_rate = 0
        max_drawdown = None
        sharpe = None
        labels = ["Start", "End"]
        values = [0, 0]

    performance = {
        'Profit': f"{profit:.2f}",
        'Win-Rate': f"{win_rate:.1f}%" if win_rate is not None else "N/A",
        'Drawdown': f"{max_drawdown:.2%}" if max_drawdown is not None else "N/A",
        'Sharpe-Ratio': f"{sharpe:.2f}" if sharpe is not None else "N/A"
    }
    chart_data = {'labels': labels, 'values': values}
    return render_template('dashboard.html', performance=performance, chart_data=chart_data, bot_running=BOT_RUNNING,
                          platforms=platforms, symbols=symbols, selected_platform=selected_platform, selected_symbol=selected_symbol)
    
@app.route('/start_bot', methods=['POST'])
def start_bot():
    global BOT_RUNNING, bot_instance, bot_thread
    if not BOT_RUNNING:
        config = load_config()
        bot_instance = TradingBot(config)
        BOT_RUNNING = True
        bot_thread = threading.Thread(target=bot_instance.start)
        bot_thread.start()
        flash('Bot gestartet!', 'success')
    else:
        flash('Bot läuft bereits!', 'warning')
    return redirect(url_for('dashboard'))

@app.route('/stop_bot', methods=['POST'])
def stop_bot():
    global BOT_RUNNING, bot_instance, bot_thread
    if BOT_RUNNING:
        BOT_RUNNING = False
        if bot_instance:
            bot_instance.stop()
        if bot_thread:
            bot_thread.join()
        flash('Bot gestoppt!', 'success')
    else:
        flash('Bot läuft nicht!', 'warning')
    return redirect(url_for('dashboard'))

@app.route('/run_backtest', methods=['POST'])
def run_backtest_route():
    config = load_config()
    selected_platform = request.form.get('platform') if request.form.get('platform') in config['platforms'] else (session.get('selected_platform') or (next(iter(config['platforms']), 'binance')))
    trade_conf = config['trading'][selected_platform]
    symbols = list(trade_conf['symbols'].keys())
    selected_symbol = request.form.get('symbol') if request.form.get('symbol') in symbols else (symbols[0] if symbols else 'BTCUSDT')
    if selected_symbol not in trade_conf['symbols']:
        flash(f"Symbol {selected_symbol} nicht verfügbar für Plattform {selected_platform}.", 'danger')
        return redirect(url_for('dashboard'))
    interval = trade_conf.get('timeframe', '1h')
    higher_tf = trade_conf.get('higher_timeframe', '1d')

    try:
        if selected_platform == "binance":
            df_hourly = fetch_ohlcv(selected_symbol, interval.lower(), limit=1000)
            df_higher = fetch_ohlcv(selected_symbol, higher_tf.lower(), limit=1000)
        elif selected_platform == "metatrader":
            connector = MetaTraderConnector()
            tf_mapping = {
                "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
                "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
                "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1, "MN1": mt5.TIMEFRAME_MN1
            }
            mt_tf = tf_mapping.get(interval.upper(), mt5.TIMEFRAME_H1)
            mt_higher_tf = tf_mapping.get(higher_tf.upper(), mt5.TIMEFRAME_H4)
            df_hourly = connector.get_ohlcv(selected_symbol, mt_tf, limit=1000)
            df_higher = connector.get_ohlcv(selected_symbol, mt_higher_tf, limit=1000)
            if df_hourly is not None and not df_hourly.empty:
                df_hourly = df_hourly.rename(columns={"tick_volume": "volume"})
            if df_higher is not None and not df_higher.empty:
                df_higher = df_higher.rename(columns={"tick_volume": "volume"})
        else:
            raise ValueError(f"Ungültige Plattform: {selected_platform}")

        if df_hourly is None or df_higher is None or df_hourly.empty or df_higher.empty:
            flash(f"Datenabruf für {selected_platform}/{selected_symbol} fehlgeschlagen. Bitte prüfen Sie, ob MT5 läuft und das Symbol verfügbar ist.", 'danger')
            return redirect(url_for('dashboard'))

        strategy = CompositeStrategy(config)
        df_sim, trades = run_backtest(
            df=df_hourly,
            strategy=strategy,
            config=config,
            df_higher=df_higher,
            symbol=selected_symbol,
            platform=selected_platform
        )
        os.makedirs(os.path.join('..', 'results'), exist_ok=True)
        trades_df = pd.DataFrame(trades) if isinstance(trades, list) else trades
        # Berechne Performance-Metriken
        from src.backtesting_improved import calculate_performance
        perf = calculate_performance(df_sim, trades)
        # Füge Metriken als zusätzliche Zeile hinzu
        summary_row = pd.DataFrame([{
            'symbol': selected_symbol,
            'entry_time': 'Summary',
            'profit': perf['total_profit'],
            'win_rate': perf['win_rate'] * 100,
            'max_drawdown': perf['max_drawdown'],
            'sharpe': perf['sharpe']
        }])
        trades_df = pd.concat([trades_df, summary_row], ignore_index=True)
        trades_df.to_csv(os.path.join('..', 'results', f'backtest_summary_{selected_platform}_{selected_symbol}.csv'), index=False)
        print(f"Trades DataFrame shape: {trades_df.shape}")
        with open(os.path.join('..', 'results', f'backtest_summary_{selected_platform}_{selected_symbol}.csv'), 'r') as f:
            print(f"File content after save: {f.read()}")
        flash('Backtest abgeschlossen!', 'success')
        time.sleep(1)
    except Exception as e:
        flash(f'Backtest fehlgeschlagen: {e}', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/run_tuning', methods=['POST'])
def run_tuning():
    config = load_config()
    try:
        tune_all_symbols(config)
        flash('Tuning abgeschlossen! Beste Parameter gespeichert.', 'success')
    except Exception as e:
        flash(f'Tuning fehlgeschlagen: {e}', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/config', methods=['GET', 'POST'])
def config_view():
    if request.method == 'POST':
        new_config = request.form.get('config_content')
        try:
            yaml.safe_load(new_config)
            with open(CONFIG_PATH, 'w') as file:
                file.write(new_config)
            flash('Konfiguration erfolgreich gespeichert!', 'success')
        except yaml.YAMLError as e:
            flash(f'Fehler beim Parsen der YAML: {e}', 'danger')
        return redirect(url_for('config_view'))
    else:
        with open(CONFIG_PATH, 'r') as file:
            config_content = file.read()
        return render_template('config.html', config_content=config_content)

@app.route('/logs')
def logs_view():
    log_file_path = os.path.join('..', 'data', 'logs', 'tradingbot.log')
    if os.path.exists(log_file_path):
        with open(log_file_path, 'r') as file:
            logs = file.read()
    else:
        logs = 'Keine Log-Datei gefunden.'
    return render_template('logs.html', logs=logs)

@app.route('/api/live_data')
def live_data():
    global bot_instance
    config = load_config()
    platforms = [p for p, enabled in config['platforms'].items() if enabled]
    selected_platform = session.get('selected_platform') or (platforms[0] if platforms else 'binance')
    trade_conf = config['trading'][selected_platform]
    if bot_instance and BOT_RUNNING:
        try:
            balance = bot_instance.connectors[selected_platform].get_balance() if selected_platform in bot_instance.connectors else 0
            positions = []
            for symbol in trade_conf['symbols'].keys():
                pos = bot_instance.get_current_position(selected_platform, symbol)
                if pos != "NONE":
                    positions.append({"symbol": symbol, "position": pos})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    else:
        balance = 0
        positions = []
    return jsonify({'balance': balance, 'positions': positions})

@app.route('/api/logs')
def api_logs():
    log_file_path = os.path.join('..', 'data', 'logs', 'tradingbot.log')
    if os.path.exists(log_file_path):
        with open(log_file_path, 'r') as file:
            logs = file.read()
    else:
        logs = 'Keine Log-Datei gefunden.'
    return jsonify({'logs': logs, 'timestamp': datetime.now().isoformat()})

@app.route('/bot')
def bot_page():
    global bot_instance, BOT_RUNNING
    config = load_config()
    selected_platform = session.get('selected_platform') or next(iter(config['platforms']), 'binance')
    trade_conf = config['trading'][selected_platform]
    symbols = list(trade_conf['symbols'].keys())
    selected_symbol = session.get('selected_symbol') or (symbols[0] if symbols else 'BTCUSDT')
    return render_template('bot.html', bot_running=BOT_RUNNING, selected_platform=selected_platform, selected_symbol=selected_symbol)

@app.route('/backtest')
def backtest_page():
    config = load_config()
    selected_platform = session.get('selected_platform') or next(iter(config['platforms']), 'binance')
    trade_conf = config['trading'][selected_platform]
    symbols = list(trade_conf['symbols'].keys())
    selected_symbol = session.get('selected_symbol') or (symbols[0] if symbols else 'BTCUSDT')
    backtest_file = os.path.join('..', 'results', f'backtest_summary_{selected_platform}_{selected_symbol}.csv')
    if os.path.exists(backtest_file):
        backtest_results = pd.read_csv(backtest_file)
        trades = backtest_results.to_dict('records')
    else:
        trades = []
    return render_template('backtest.html', trades=trades, selected_platform=selected_platform, selected_symbol=selected_symbol)

@app.route('/tuning')
def tuning_page():
    config = load_config()
    selected_platform = session.get('selected_platform') or next(iter(config['platforms']), 'binance')
    trade_conf = config['trading'][selected_platform]
    symbols = list(trade_conf['symbols'].keys())
    selected_symbol = session.get('selected_symbol') or (symbols[0] if symbols else 'BTCUSDT')
    tuning_file = os.path.join('..', 'results', 'tuning', 'best_params.yaml')
    if os.path.exists(tuning_file):
        with open(tuning_file, 'r') as f:
            tuning_params = yaml.safe_load(f)
    else:
        tuning_params = {}
    return render_template('tuning.html', tuning_params=tuning_params, selected_platform=selected_platform, selected_symbol=selected_symbol)

# ... (bestehende Routen bleiben gleich) ...

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)