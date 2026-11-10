import os
import time
import threading
import requests
from flask import Flask

# --- CONFIG ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

ENTRY_TRIGGER = 0.0015  # 0.15% - entry
TAKE_PROFIT_PULLBACK = 0.0015  # 0.15% - pullback to close
STOP_LOSS = 0.003  # 0.3% stop loss
SYMBOL = "BTCUSDT"

app = Flask(__name__)

running = False
in_trade = False
entry_price = 0
peak_price = 0

def send_telegram(text):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": text}, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def get_price():
    try:
        r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={SYMBOL}", timeout=10)
        return float(r.json()["price"])
    except:
        return None

def trading_loop():
    global running, in_trade, entry_price, peak_price
    last_price = get_price()
    if not last_price:
        return
    send_telegram(f"Bot started...\nWaiting for 0.15% move on {SYMBOL}...")
    while True:
        if not running:
            time.sleep(2)
            continue
        price = get_price()
        if not price:
            time.sleep(2)
            continue

        if not in_trade:
            # Check for 0.15% up move
            if price >= last_price * (1 + ENTRY_TRIGGER):
                in_trade = True
                entry_price = price
                peak_price = price
                send_telegram(f"🟢 ENTER LONG @ ${price:,.2f}\nWaiting for 0.15% pullback to take profit...")
            # Check for 0.15% down move
            elif price <= last_price * (1 - ENTRY_TRIGGER):
                in_trade = True
                entry_price = price
                peak_price = price
                send_telegram(f"🔴 ENTER SHORT @ ${price:,.2f}\nWaiting for 0.15% pullback to take profit...")
        else:
            # Update peak and check pullback / stop
            if price > peak_price:
                peak_price = price
            # Take profit on 0.15% pullback from peak
            if price <= peak_price * (1 - TAKE_PROFIT_PULLBACK):
                profit_pct = ((price - entry_price) / entry_price) * 100
                send_telegram(f"✅ CLOSED @ ${price:,.2f}\nProfit: {profit_pct:.3f}%")
                in_trade = False
            elif price <= entry_price * (1 - STOP_LOSS):
                send_telegram(f"🛑 STOP LOSS @ ${price:,.2f}")
                in_trade = False

        last_price = price
        time.sleep(2)

def telegram_polling():
    global running
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={offset}&timeout=30"
            r = requests.get(url, timeout=35).json()
            for upd in r.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message", {})
                text = msg.get("text", "")
                if text == "/start":
                    running = True
                    send_telegram("Bot started...\nWaiting for 0.15% move on BTC...")
                elif text == "/stop":
                    running = False
                    send_telegram("Bot stopped.")
                elif text == "/status":
                    price = get_price()
                    send_telegram(f"Status: {'Running' if running else 'Stopped'}\nIn Trade: {in_trade}\nBTC: ${price:,.2f}" if price else "Status check failed")
        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(5)

@app.route("/")
def home():
    return "Bot is alive"

if __name__ == "__main__":
    threading.Thread(target=telegram_polling, daemon=True).start()
    threading.Thread(target=trading_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
