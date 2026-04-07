from flask import Flask, request
import json

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    
    signal = data.get("signal")
    symbol = data.get("symbol")
    
    # 👉 hier deine Strategie rein
    execute_trade(signal, symbol)
    
    return {"status": "ok"}

def execute_trade(signal, symbol):
    print(signal, symbol)
    # später Bitget API call

app.run()
