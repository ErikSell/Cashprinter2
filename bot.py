# bot.py – Komplett neu geschrieben für deine exakte Logik
import os
import logging
from flask import Flask, request, jsonify
import ccxt
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Logging – wichtig für Render-Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# Bitget Exchange Konfiguration
exchange = ccxt.bitget({
    'apiKey': os.getenv('BITGET_API_KEY'),
    'secret': os.getenv('BITGET_SECRET'),
    'password': os.getenv('BITGET_PASSPHRASE'),
    'enableRateLimit': True,
    'options': {'defaultType': 'swap'},  # USDT-Perpetual
})

SYMBOL = 'BTC/USDT:USDT'
LEVERAGE = 5
TARGET_MARGIN_PCT = 0.33           # 33 % des verfügbaren USDT
MIN_AMOUNT_BTC = 0.001             # Bitget Minimum für BTC/USDT:USDT

def setup_exchange():
    """Einmalig Leverage + Isolated setzen"""
    try:
        exchange.set_leverage(LEVERAGE, SYMBOL)
        logger.info(f"Leverage auf {LEVERAGE}x gesetzt")
        
        exchange.set_margin_mode('isolated', SYMBOL)
        logger.info("Margin Mode → isolated")
    except Exception as e:
        logger.error(f"Setup Fehler: {e}")

setup_exchange()

def get_usdt_balance():
    """Verfügbarer USDT in Futures holen"""
    try:
        bal = exchange.fetch_balance(params={'type': 'swap'})
        return float(bal.get('USDT', {}).get('free', 0))
    except Exception as e:
        logger.error(f"Balance Fehler: {e}")
        return 0

def get_position():
    """Aktuelle Position: (side: 'long'/'short'/None, amount: float)"""
    try:
        pos = exchange.fetch_positions([SYMBOL])
        for p in pos:
            amt = float(p.get('contracts', 0))
            if amt > 0:
                return p['side'], amt
        return None, 0.0
    except Exception as e:
        logger.error(f"Position abfragen Fehler: {e}")
        return None, 0.0

def calculate_size():
    """Berechne Positionsgröße in BTC (~33 % Balance)"""
    usdt_free = get_usdt_balance()
    if usdt_free <= 0:
        logger.warning("Kein freier USDT → Größe = 0")
        return 0.0

    target_usdt = usdt_free * TARGET_MARGIN_PCT
    
    try:
        price = float(exchange.fetch_ticker(SYMBOL)['last'])
        size_btc = target_usdt / price
        size_btc = max(MIN_AMOUNT_BTC, round(size_btc, 3))
        logger.info(f"Berechnete Größe: {size_btc:.3f} BTC (~{size_btc*price:,.0f} USDT)")
        return size_btc
    except Exception as e:
        logger.error(f"Größe berechnen Fehler: {e}")
        return 0.0

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        signal = request.data.decode('utf-8').strip()
        logger.info(f"Signal empfangen → {signal}")

        side, current_size = get_position()
        new_size = calculate_size()
        if new_size <= 0:
            logger.warning("Keine gültige Größe → Abbruch")
            return jsonify({"status": "no_size"}), 200

        is_strong = "AI" in signal
        is_bullish = "Bullish" in signal
        is_bearish = "Bearish" in signal

        if not (is_bullish or is_bearish):
            logger.warning("Unbekanntes Signal → ignoriert")
            return jsonify({"status": "unknown"}), 200

        # ────────────────────────────────────────────────
        # Bullish Signale (AI oder Mild)
        # ────────────────────────────────────────────────
        if is_bullish:
            if side == 'short':
                # Short schließen + Long öffnen (Reversal bei AI, nur close bei Mild)
                logger.info("Short schließen")
                exchange.create_market_buy_order(SYMBOL, current_size)  # buy = short schließen
                if is_strong:
                    logger.info("AI Bullish → Long öffnen")
                    exchange.create_market_buy_order(SYMBOL, new_size)
            elif side is None and is_strong:
                # Flat + AI Bullish → Long öffnen
                logger.info("AI Bullish → Long öffnen")
                exchange.create_market_buy_order(SYMBOL, new_size)
            else:
                logger.info("Bereits Long oder Mild ohne Action → skip")

        # ────────────────────────────────────────────────
        # Bearish Signale (AI oder Mild)
        # ────────────────────────────────────────────────
        elif is_bearish:
            if side == 'long':
                # Long schließen + Short öffnen (Reversal bei AI, nur close bei Mild)
                logger.info("Long schließen")
                exchange.create_market_sell_order(SYMBOL, current_size)  # sell = long schließen
                if is_strong:
                    logger.info("AI Bearish → Short öffnen")
                    exchange.create_market_sell_order(SYMBOL, new_size)
            elif side is None and is_strong:
                # Flat + AI Bearish → Short öffnen
                logger.info("AI Bearish → Short öffnen")
                exchange.create_market_sell_order(SYMBOL, new_size)
            else:
                logger.info("Bereits Short oder Mild ohne Action → skip")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logger.error(f"Webhook Fehler: {str(e)}")
        return jsonify({"status": "error", "msg": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return "OK", 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
