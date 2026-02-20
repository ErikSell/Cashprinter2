import os
from flask import Flask, request, jsonify
import ccxt
from dotenv import load_dotenv
import logging

load_dotenv()

app = Flask(__name__)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

exchange = ccxt.bitget({
    'apiKey': os.getenv('BITGET_API_KEY'),
    'secret': os.getenv('BITGET_SECRET'),
    'password': os.getenv('BITGET_PASSPHRASE'),
    'enableRateLimit': True,
    'options': {'defaultType': 'swap'},
})

SYMBOL = 'BTC/USDT:USDT'
LEVERAGE = 5
TARGET_MARGIN_PCT = 0.33

def set_up_exchange():
    try:
        exchange.set_leverage(LEVERAGE, SYMBOL)
        logger.info(f"Leverage {LEVERAGE}x für {SYMBOL}")
        exchange.set_margin_mode('isolated', SYMBOL)
        logger.info(f"Isolated Margin für {SYMBOL}")
    except Exception as e:
        logger.error(f"Setup Fehler: {e}")

set_up_exchange()

def get_futures_balance():
    try:
        balance = exchange.fetch_balance(params={'type': 'swap'})
        return balance.get('USDT', {}).get('free', 0)
    except Exception as e:
        logger.error(f"Balance Fehler: {e}")
        return 0

def calculate_position_size():
    balance = get_futures_balance()
    if balance <= 0:
        return 0
    target_usdt = balance * TARGET_MARGIN_PCT
    ticker = exchange.fetch_ticker(SYMBOL)
    price = ticker['last']
    amount = target_usdt / price
    amount = max(0.001, round(amount, 3))  # min 0.001 BTC
    logger.info(f"Size: {amount} BTC (~{amount*price:.2f} USDT)")
    return amount

def get_current_position():
    try:
        positions = exchange.fetch_positions([SYMBOL])
        for pos in positions:
            if pos['contracts'] > 0:
                return pos['side'], pos['contracts']
        return None, 0
    except Exception as e:
        logger.error(f"Position Fehler: {e}")
        return None, 0

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        signal = request.data.decode('utf-8').strip()
        logger.info(f"Signal: {signal}")

        side, current_amount = get_current_position()
        amount = calculate_position_size()
        if amount == 0:
            return jsonify({'status': 'no_balance'}), 200

        if "Bullish" in signal:
            if side == 'short':
                exchange.create_market_buy_order(SYMBOL, current_amount)   # close short
                exchange.create_market_buy_order(SYMBOL, amount)          # open long
                logger.info("Reversal: Short → Long")
            elif side is None:
                exchange.create_market_buy_order(SYMBOL, amount)
                logger.info("Open Long")
            else:
                logger.info("Bereits Long → skip")

        elif "Bearish" in signal:
            if side == 'long':
                exchange.create_market_sell_order(SYMBOL, current_amount)  # close long
                if "AI" in signal:
                    exchange.create_market_sell_order(SYMBOL, amount)
                    logger.info("Reversal: Long → Short")
                else:
                    logger.info("Nur Close Long (mild)")
            elif side is None and "AI" in signal:
                exchange.create_market_sell_order(SYMBOL, amount)
                logger.info("Open Short")
            else:
                logger.info("Bereits Short oder mild skip")

        return jsonify({'status': 'ok'}), 200

    except Exception as e:
        logger.error(f"Webhook Fehler: {e}")
        return jsonify({'status': 'error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
