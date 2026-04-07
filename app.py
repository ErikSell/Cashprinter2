from flask import Flask, request, jsonify
from strategy import execute_trade

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot läuft!"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    
    signal = data.get("signal")
    symbol = data.get("symbol")
    
    result = execute_trade(signal)
    
    print("Signal:", signal)
    print("Result:", result)
    
    return jsonify({
        "status": "ok",
        "result": result
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
  
