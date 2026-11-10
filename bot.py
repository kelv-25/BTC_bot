import os
import time
import requests
import threading
from flask import Flask

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
BASE = f"https://api.telegram.org/bot{TOKEN}" if TOKEN else ""

print(f"=== BOT STARTING ===", flush=True)
print(f"TOKEN found: {'YES' if TOKEN else 'NO - CHECK RENDER ENV!'}", flush=True)
print(f"CHAT_ID: {CHAT_ID}", flush=True)

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!", 200

running = False
last_price = None

def send_telegram(text):
    if not TOKEN or not CHAT_ID:
        print("CANNOT SEND: TOKEN or CHAT_ID missing!", flush=True)
        return
    try:
        r = requests.post(f"{BASE}/sendMessage", json={"chat_id": CHAT_ID, "text": text}, timeout=10)
        print(f"Telegram send: {r.status_code} - {r.text[:200]}", flush=True)
    except Exception as e:
        print(f"Telegram send error: {e}", flush=True)

def get_price():
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=10)
        return float(r.json()['price'])
    except Exception as e:
        print(f"Price error: {e}", flush=True)
        return None

def trading_loop():
    global last_price
    time.sleep(3)
    # 1. Clear old webhook - THIS IS THE FIX
    try:
        requests.get(f"{BASE}/deleteWebhook?drop_pending_updates=true", timeout=10)
        print("Webhook deleted - polling can now work", flush=True)
    except Exception as e:
        print(f"Webhook delete error: {e}", flush=True)
    
    send_telegram("Bot started... Waiting for 0.15% move...")
    print("Startup message sent, entering loop", flush=True)
    
    while True:
        try:
            if running:
                price = get_price()
                if price and last_price:
                    change = ((price - last_price) / last_price) * 100
                    if abs(change) >= 0.15:
                        send_telegram(f"BTC moved {change:.3f}% - Price: {price}")
                        last_price = price
                if price:
                    last_price = price
            time.sleep(5)
        except Exception as e:
            print(f"Trading loop error: {e}", flush=True)
            time.sleep(5)

def polling_loop():
    offset = None
    print("Polling started - waiting for /start", flush=True)
    while True:
        try:
            url = f"{BASE}/getUpdates?timeout=30"
            if offset:
                url += f"&offset={offset}"
            r = requests.get(url, timeout=35)
            data = r.json()
            if not data.get("ok"):
                print(f"Polling bad response: {data}", flush=True)
                time.sleep(5)
                continue
            for upd in data.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message", {})
                text = msg.get("text", "")
                chat_id = str(msg.get("chat", {}).get("id", ""))
                print(f"Got message: '{text}' from {chat_id}", flush=True)
                if text == "/start":
                    global running
                    running = True
                    send_telegram("Bot started... Waiting for 0.15% move...")
                elif text == "/stop":
                    running = False
                    send_telegram("Bot stopped.")
        except Exception as e:
            print(f"Polling error: {e}", flush=True)
            time.sleep(5)

threading.Thread(target=trading_loop, daemon=True).start()
threading.Thread(target=polling_loop, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
