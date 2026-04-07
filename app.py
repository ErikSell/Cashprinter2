from flask import Flask, request, jsonify
import requests
import time
import hmac
import hashlib
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# =====================
# CONFIG
# =====================
API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_SECRET")
PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

BASE_URL = "https://api.bitget.com"

state = {
    "savings_balance": 0.0,
    "last_trades": []
}

# =====================
# HELPER FUNCTIONS
# =====================
def get_timestamp():
    return str(int(time.time() * 1000))

def sign(message):
    return hmac.new(API_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()

def get_headers(method, path, body=""):
    timestamp = get_timestamp()
    message = timestamp + method + path + body
    signature = sign(message)

    return {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json"
    }

# =====================
# GET BALANCE
# =====================
def get_balance():
    path = "/api/v2/mix/account/accounts"
    url = BASE_URL + path

    headers = get_headers("GET", path)

    res = requests.get(url, headers=headers)
    data = res.json()

    try:
        return float(data["data"][0]["available"])
    except:
        return 0

# =====================
# UMLAGE (LAST 3 TRADES)
# =====================
def calculate_umlage():
    trades = state["last_trades"][-3:]
    if len(trades) == 0:
        winrate = 50
    else:
        winrate = sum(trades) / len(trades) * 100
    
    return 85 - 0.75 * winrate

# =====================
# POSITION SIZE
# =====================
def calculate_position_size(balance, entry, sl):
    risk_amount = balance * 0.05
    sl_distance = abs(entry - sl)
    
    if sl_distance == 0:
        return 0
    
    size = risk_amount / sl_distance
    return round(size, 4)

# =====================
# PLACE ORDER
# =====================
def place_order(symbol, side, size, entry, sl, tp):
    path = "/api/v2/mix/order/place-order"
    url = BASE_URL + path

    body = {
        "symbol": symbol,
        "marginCoin": "USDT",
        "size": str(size),
        "side": side,
        "orderType": "market",
        "timeInForceValue": "normal"
    }

    body_str = json.dumps(body)
    headers = get_headers("POST", path, body_str)

    res = requests.post(url, headers=headers, data=body_str)
    return res.json()

# =====================
# STRATEGY EXECUTION
# =====================
def execute_trade(signal, symbol):
    balance = get_balance()

    # Fake Entry (später kannst du Live Price holen)
    entry = 100  

    if signal == "buy":
        sl = entry * (1 - 0.008)
        tp = entry + (entry - sl) * 2.5
        side = "open_long"
    else:
        sl = entry * (1 + 0.008)
        tp = entry - (sl - entry) * 2.5
        side = "open_short"

    size = calculate_position_size(balance, entry, sl)

    umlage = calculate_umlage()

    order = place_order(symbol, side, size, entry, sl, tp)

    # Dummy Ergebnis (echtes Tracking später)
    win = True  

    profit = balance * 0.05 * 2.5
    transfer = profit * (umlage / 100)

    state["savings_balance"] += transfer
    state["last_trades"].append(1 if win else 0)

    return {
        "balance": balance,
        "size": size,
        "sl": sl,
        "tp": tp,
        "umlage": umlage,
        "order": order
    }

# =====================
# WEBHOOK
# =====================
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    signal = data.get("signal")
    symbol = data.get("symbol")

    result = execute_trade(signal, symbol)

    return jsonify(result)

@app.route("/")
def home():
    return "Bot läuft!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
