import os, time, requests, threading
from flask import Flask

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
BASE = f"https://api.telegram.org/bot{TOKEN}" if TOKEN else ""
app = Flask(__name__)

# --- YOUR $10 ACCOUNT ---
balance_usdt = 10.0
balance_btc = 0.0
last_price = None
buy_price = None
running = False
trades = 0

print(f"BOT STARTING - Balance: ${balance_usdt}", flush=True)

@app.route('/')
def home(): return "Paper Trade Bot Alive", 200

def send(text):
    if not TOKEN or not CHAT_ID: return
    try:
        requests.post(f"{BASE}/sendMessage", json={"chat_id": CHAT_ID, "text": text}, timeout=10)
    except Exception as e: print(e, flush=True)

def get_price():
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=10)
        return float(r.json()['price'])
    except: return None

def trading_loop():
    global balance_usdt, balance_btc, last_price, buy_price, trades
    time.sleep(2)
    try: requests.get(f"{BASE}/deleteWebhook?drop_pending_updates=true", timeout=10)
    except: pass
    send("Paper Trade Bot Started\nBalance: $10.00 USDT\nStrategy: Buy on -0.15% dip, Sell on +0.15% pump")
    while True:
        try:
            if running:
                price = get_price()
                if price and last_price:
                    # WE HAVE USDT - LOOK TO BUY ON DIP
                    if balance_usdt > 0 and balance_btc == 0:
                        drop = ((price - last_price) / last_price) * 100
                        if drop <= -0.15:
                            balance_btc = balance_usdt / price
                            balance_usdt = 0
                            buy_price = price
                            trades += 1
                            send(f"🟢 BUY\nBought BTC at ${price:,.2f}\nSpent: $10.00\nBalance: 0 USDT | {balance_btc:.6f} BTC")
                    # WE HAVE BTC - LOOK TO SELL ON PUMP
                    elif balance_btc > 0 and buy_price:
                        profit = ((price - buy_price) / buy_price) * 100
                        if profit >= 0.15:
                            balance_usdt = balance_btc * price
                            balance_btc = 0
                            trades += 1
                            send(f"🔴 SELL\nSold BTC at ${price:,.2f}\nProfit: {profit:.3f}%\nNEW BALANCE: ${balance_usdt:.2f} USDT\nTotal Trades: {trades}")
                        elif profit <= -0.30: # Stop loss
                            balance_usdt = balance_btc * price
                            balance_btc = 0
                            trades += 1
                            send(f"🛑 STOP LOSS\nSold at ${price:,.2f}\nLoss: {profit:.3f}%\nNEW BALANCE: ${balance_usdt:.2f} USDT")
                if price: last_price = price
            time.sleep(5)
        except Exception as e:
            print(f"Loop error: {e}", flush=True)
            time.sleep(5)

def polling():
    global running
    offset = None
    while True:
        try:
            url = f"{BASE}/getUpdates?timeout=30"
            if offset: url += f"&offset={offset}"
            r = requests.get(url, timeout=35).json()
            for upd in r.get("result", []):
                offset = upd["update_id"] + 1
                text = upd.get("message", {}).get("text", "")
                if text == "/start":
                    running = True
                    send("Auto-Trading STARTED with $10\nI will now buy dips and sell pumps automatically.")
                elif text == "/stop":
                    running = False
                    send("Trading STOPPED.")
                elif text == "/balance":
                    price = get_price() or 0
                    total = balance_usdt + (balance_btc * price if balance_btc else 0)
                    send(f"💰 BALANCE\nUSDT: ${balance_usdt:.2f}\nBTC: {balance_btc:.6f}\nTotal Value: ${total:.2f}\nTrades: {trades}")
        except Exception as e:
            print(f"Poll error: {e}", flush=True)
            time.sleep(5)

threading.Thread(target=trading_loop, daemon=True).start()
threading.Thread(target=polling, daemon=True).start()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
