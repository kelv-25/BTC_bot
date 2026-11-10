import os
import time
import threading
import requests
import telebot
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- FAKE WEB SERVER SO RENDER FREE STAYS ALIVE ---
def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is alive")
        def log_message(self, *a):
            pass
    HTTPServer(("0.0.0.0", port), H).serve_forever()

threading.Thread(target=keep_alive, daemon=True).start()
# ---------------------------------------------------

TOKEN = os.environ.get("TOKEN")
CHAT_ID = int(os.environ.get("CHAT_ID", "0"))
bot = telebot.TeleBot(TOKEN)

BALANCE = 1000.0
LEVERAGE = 10
MARGIN = 100.0
ENTRY_TRIGGER = 0.0015  # 0.15%
TAKE_PROFIT_PULLBACK = 0.0015
STOP_LOSS = 0.01  # 1%
COOLDOWN = 120  # 2 min

position = None
history = []
last_price = None
peak_price = None
last_trade_time = 0

def get_price():
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=5)
        return float(r.json()["price"])
    except:
        return None

def send(msg):
    try:
        bot.send_message(CHAT_ID, msg)
    except Exception as e:
        print(f"Send error: {e}")

@bot.message_handler(commands=['start'])
def start(m):
    bot.reply_to(m, f"FUTURES SCALPER LIVE\nBalance {BALANCE} {LEVERAGE}x")

@bot.message_handler(commands=['balance'])
def balance(m):
    p = get_price()
    bot.reply_to(m, f"Balance: ${BALANCE:.2f}\nBTC: ${p:,.2f}" if p else f"Balance: ${BALANCE:.2f}")

@bot.message_handler(commands=['position'])
def pos(m):
    if position:
        bot.reply_to(m, f"Position: {position['side']} Entry ${position['entry']:.2f} PnL ${position.get('pnl',0):.2f}")
    else:
        bot.reply_to(m, "No position - Waiting for 0.2 pct move")

@bot.message_handler(commands=['history'])
def hist(m):
    if not history:
        bot.reply_to(m, "No trades yet")
    else:
        txt = "\n".join([f"{h['side']} PnL ${h['pnl']:.2f}" for h in history[-10:]])
        bot.reply_to(m, txt)

def trading_loop():
    global BALANCE, position, last_price, peak_price, last_trade_time
    print("Bot Started - Trading Loop Running")
    while True:
        try:
            price = get_price()
            if price is None:
                time.sleep(10)
                continue

            if last_price is None:
                last_price = price
                peak_price = price

            if position is None:
                # Check for entry
                change = (price - last_price) / last_price
                if time.time() - last_trade_time > COOLDOWN:
                    if change >= ENTRY_TRIGGER:
                        position = {"side": "LONG", "entry": price, "peak": price}
                        send(f"🚀 LONG OPEN\nEntry ${price:,.2f}\nMargin $100 10x")
                        print(f"LONG opened at {price}")
                    elif change <= -ENTRY_TRIGGER:
                        position = {"side": "SHORT", "entry": price, "peak": price}
                        send(f"🔻 SHORT OPEN\nEntry ${price:,.2f}\nMargin $100 10x")
                        print(f"SHORT opened at {price}")
                last_price = price
            else:
                # Manage position
                entry = position["entry"]
                if position["side"] == "LONG":
                    if price > position["peak"]:
                        position["peak"] = price
                    pnl_pct = (price - entry) / entry * LEVERAGE
                    # Take profit on pullback
                    pullback = (position["peak"] - price) / position["peak"]
                    if pnl_pct > 0 and pullback >= TAKE_PROFIT_PULLBACK:
                        pnl = MARGIN * pnl_pct
                        BALANCE += pnl
                        history.append({"side": "LONG", "pnl": pnl})
                        send(f"✅ LONG CLOSED\nPnL ${pnl:.2f}\nBalance ${BALANCE:.2f}")
                        position = None
                        last_trade_time = time.time()
                        last_price = price
                    elif pnl_pct <= -STOP_LOSS * LEVERAGE:
                        pnl = MARGIN * pnl_pct
                        BALANCE += pnl
                        history.append({"side": "LONG", "pnl": pnl})
                        send(f"🛑 LONG STOP LOSS\nPnL ${pnl:.2f}\nBalance ${BALANCE:.2f}")
                        position = None
                        last_trade_time = time.time()
                        last_price = price
                else:  # SHORT
                    if price < position["peak"]:
                        position["peak"] = price
                    pnl_pct = (entry - price) / entry * LEVERAGE
                    pullback = (price - position["peak"]) / position["peak"]
                    if pnl_pct > 0 and pullback >= TAKE_PROFIT_PULLBACK:
                        pnl = MARGIN * pnl_pct
                        BALANCE += pnl
                        history.append({"side": "SHORT", "pnl": pnl})
                        send(f"✅ SHORT CLOSED\nPnL ${pnl:.2f}\nBalance ${BALANCE:.2f}")
                        position = None
                        last_trade_time = time.time()
                        last_price = price
                    elif pnl_pct <= -STOP_LOSS * LEVERAGE:
                        pnl = MARGIN * pnl_pct
                        BALANCE += pnl
                        history.append({"side": "SHORT", "pnl": pnl})
                        send(f"🛑 SHORT STOP LOSS\nPnL ${pnl:.2f}\nBalance ${BALANCE:.2f}")
                        position = None
                        last_trade_time = time.time()
                        last_price = price

            time.sleep(10)
        except Exception as e:
            print(f"Loop error: {e}")
            time.sleep(10)

threading.Thread(target=trading_loop, daemon=True).start()
print("Bot Started")
bot.infinity_polling()
