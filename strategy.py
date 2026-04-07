state = {
    "trading_balance": 100.0,
    "savings_balance": 0.0,
    "last_trades": [],  # 1 = win, 0 = loss
}

def calculate_umlage():
    trades = state["last_trades"][-3:]  # nur letzte 3 Trades
    if len(trades) == 0:
        winrate = 50
    else:
        winrate = sum(trades) / len(trades) * 100
    
    umlage = 85 - 0.75 * winrate
    return umlage

def process_trade_result(win):
    state["last_trades"].append(1 if win else 0)

def execute_trade(signal):
    balance = state["trading_balance"]
    risk = balance * 0.05
    
    # Fake win/loss (später durch echten Trade ersetzen!)
    import random
    win = random.random() < 0.68
    
    umlage = calculate_umlage()
    
    if win:
        profit = risk * 2.5
        transfer = profit * (umlage / 100)
        
        state["trading_balance"] += profit - transfer
        state["savings_balance"] += transfer
    else:
        state["trading_balance"] -= risk
    
    process_trade_result(win)
    
    # Safety Net
    if state["trading_balance"] <= 35 and state["savings_balance"] > 0:
        needed = 50 - state["trading_balance"]
        take = min(needed, state["savings_balance"])
        
        state["trading_balance"] += take
        state["savings_balance"] -= take
    
    return {
        "win": win,
        "trading_balance": state["trading_balance"],
        "savings_balance": state["savings_balance"],
        "umlage": umlage
    }
