import os, time, requests, threading
from flask import Flask

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
BASE = f"https://api.telegram.org/bot{TOKEN}" if TOKEN else ""
app = Flask(__name__)

balance_usdt = 10.0
balance_btc = 0.0
buy_price = None
running = False
trades = 0
last_heartbeat = time.time()

@app.route('/')
def home(): return "Paper Trade Bot Alive", 200

def send(text):
    if not TOKEN or not CHAT_ID: return
    try: requests.post(f"{BASE}/sendMessage", json={"chat_id": CHAT_ID, "text": text}, timeout=10)
    except Exception as e: print(e, flush=True)

def get_price():
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=10)
        return float(r.json()['price'])
    except: return None

def trading_loop():
    global balance_usdt, balance_btc, buy_price, trades, last_heartbeat
    time.sleep(2)
    try: requests.get(f"{BASE}/deleteWebhook?drop_pending_updates=true", timeout=10)
    except: pass
    send("Paper Bot V2 - FASTER\nBalance: $10.00\nNow buys on smaller dips so you see trades faster.")
    ref_price = get_price() # price we compare against
    while True:
        try:
            if running:
                price = get_price()
                if price and ref_price:
                    # HAVE USDT - BUY IF PRICE DROPS 0.05% FROM REF
                    if balance_usdt > 0 and balance_btc == 0:
                        drop = ((price - ref_price) / ref_price) * 100
                        if drop <= -0.05:
                            balance_btc = balance_usdt / price
                            balance_usdt = 0
                            buy_price = price
                            trades += 1
                            send(f"🟢 BUY\nPrice: ${price:,.2f}\nDrop: {drop:.3f}%\nSpent $10.00 -> {balance_btc:.6f} BTC\nTrade #{trades}")
                            ref_price = price
                        elif drop > 0:
                            ref_price = price # price went up, update ref to new high
                    # HAVE BTC - SELL IF +0.05% PROFIT OR -0.15% LOSS
                    elif balance_btc > 0 and buy_price:
                        profit = ((price - buy_price) / buy_price) * 100
                        if profit >= 0.05 or profit <= -0.15:
                            balance_usdt = balance_btc * price
                            balance_btc = 0
                            trades += 1
                            emoji = "🔴 SELL PROFIT" if profit >= 0 else "🛑 SELL LOSS"
                            send(f"{emoji}\nPrice: ${price:,.2f}\nProfit: {profit:.3f}%\nNEW BALANCE: ${balance_usdt:.2f}\nTrade #{trades}")
                            ref_price = price
                # Heartbeat every 30 mins so you know it's alive
                if time.time() - last_heartbeat > 1800:
                    last_heartbeat = time.time()
                    price = get_price()
                    total = balance_usdt + (balance_btc * price if balance_btc else 0)
                    send(f"💓 Still alive. BTC ${price:,.2f} | Balance ${total:.2f} | Trades: {trades}")
            time.sleep(5)
        except Exception as e:
            print(e, flush=True)
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
                    send("Trading STARTED - Faster Mode ON")
                elif text == "/stop":
                    running = False
                    send("Trading STOPPED.")
                elif text == "/balance":
                    price = get_price() or 0
                    total = balance_usdt + (balance_btc * price if balance_btc else 0)
                    send(f"💰 BALANCE\nUSDT: ${balance_usdt:.2f}\nBTC: {balance_btc:.6f}\nTotal: ${total:.2f}\nTrades: {trades}")
        except: time.sleep(5)

threading.Thread(target=trading_loop, daemon=True).start()
threading.Thread(target=polling, daemon=True).start()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
