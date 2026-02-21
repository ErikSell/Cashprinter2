# bot.py – Komplett neu, sauber und auf deine exakte Logik zugeschnitten (Feb 2026)
import os
import logging
from flask import Flask, request, jsonify
import ccxt
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Logging für Render-Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# Bitget Konfiguration – USDT Perpetual Futures
exchange = ccxt.bitget({
    'apiKey': os.getenv('BITGET_API_KEY'),
    'secret': os.getenv('BITGET_SECRET'),
    'password': os.getenv('BITGET_PASSPHRASE'),
    'enableRateLimit': True,
    'options': {'defaultType': 'swap'},
})

SYMBOL = 'BTC/USDT:USDT'
LEVERAGE = 5
TARGET_MARGIN_PCT = 0.33          # 33 % des verfügbaren USDT
MIN_AMOUNT_BTC = 0.001            # Bitget Minimum

def setup_exchange():
    try:
        exchange.set_leverage(LEVERAGE, SYMBOL)
        logger.info(f"Leverage {LEVERAGE}x gesetzt für {SYMBOL}")
        exchange.set_margin_mode('isolated', SYMBOL)
        logger.info(f"Isolated Margin gesetzt für {SYMBOL}")
    except Exception as e:
        logger.error(f"Setup Fehler: {e}")

setup_exchange()

def get_usdt_balance():
    try:
        bal = exchange.fetch_balance(params={'type': 'swap'})
        return float(bal.get('USDT', {}).get('free', 0))
    except Exception as e:
        logger.error(f"Balance Fehler: {e}")
        return 0

def calculate_size():
    usdt = get_usdt_balance()
    if usdt <= 0:
        logger.warning("Kein USDT frei → Größe 0")
        return 0.0
    target = usdt * TARGET_MARGIN_PCT
    try:
        price = float(exchange.fetch_ticker(SYMBOL)['last'])
        size = target / price
        size = max(MIN_AMOUNT_BTC, round(size, 3))
        logger.info(f"Größe: {size:.3f} BTC (~{size*price:,.0f} USDT)")
        return size
    except Exception as e:
        logger.error(f"Größe-Fehler: {e}")
        return 0.0

def get_position():
    try:
        pos = exchange.fetch_positions([SYMBOL])
        for p in pos:
            amt = float(p.get('contracts', 0))
            if amt > 0:
                return p['side'], amt
        return None, 0.0
    except Exception as e:
        logger.error(f"Position-Fehler: {e}")
        return None, 0.0

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        signal = request.data.decode('utf-8').strip()
        logger.info(f"Signal empfangen: '{signal}'")

        side, current_size = get_position()
        new_size = calculate_size()
        if new_size <= 0:
            logger.warning("Keine gültige Größe → Abbruch")
            return jsonify({"status": "no_size"}), 200

        signal_clean = signal.strip().lower()

        # AI Bullish Reversal → Long öffnen / Reversal
        if "ai bullish reversal" in signal_clean:
            logger.info("AI Bullish Reversal → Long öffnen / Reversal")
            if side == 'short':
                logger.info("Short schließen (reduceOnly)")
                exchange.create_market_buy_order(SYMBOL, current_size, params={'reduceOnly': True})
            if side != 'long':
                logger.info("Long öffnen")
                exchange.create_market_buy_order(SYMBOL, new_size)

        # AI Bearish Reversal → Short öffnen / Reversal
        elif "ai bearish reversal" in signal_clean:
            logger.info("AI Bearish Reversal → Short öffnen / Reversal")
            if side == 'long':
                logger.info("Long schließen (reduceOnly)")
                exchange.create_market_sell_order(SYMBOL, current_size, params={'reduceOnly': True})
            if side != 'short':
                logger.info("Short öffnen")
                exchange.create_market_sell_order(SYMBOL, new_size)

        # Mild Bullish Reversal → nur Short schließen (wenn offen)
        elif "mild bullish reversal" in signal_clean:
            logger.info("Mild Bullish Reversal → nur Exit wenn Short")
            if side == 'short':
                logger.info("Short schließen (reduceOnly)")
                exchange.create_market_buy_order(SYMBOL, current_size, params={'reduceOnly': True})

        # Mild Bearish Reversal → nur Long schließen (wenn offen)
        elif "mild bearish reversal" in signal_clean:
            logger.info("Mild Bearish Reversal → nur Exit wenn Long")
            if side == 'long':
                logger.info("Long schließen (reduceOnly)")
                exchange.create_market_sell_order(SYMBOL, current_size, params={'reduceOnly': True})

        else:
            logger.warning(f"Unbekanntes Signal: '{signal}'")
