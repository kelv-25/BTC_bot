import os
import time
import requests
import threading
import telebot

# --- SECRETS FROM RENDER ENVIRONMENT (NOT IN CODE) ---
TOKEN = os.getenv("TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID", "0"))

bot = telebot.TeleBot(TOKEN)

# --- PAPER FUTURES ACCOUNT ---
balance = 1000.0
LEVERAGE = 10
MARGIN_PER_TRADE = 100.0  # $100 margin = $1000 notional with 10x
TRADEBACK = 0.002  # 0.2% pullback from peak = CLOSE
ENTRY_MOVE = 0.002  # 0.2% move in 60 sec = ENTER

position = None
history = []
last_price = None
prev_price_for_signal = None

def get_btc():
    try:
        r = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot", timeout=10)
        return float(r.json()["data"]["amount"])
    except:
        try:
            r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd", timeout=10)
            return float(r.json()["bitcoin"]["usd"])
        except:
            return None

def close_position(price, reason):
    global balance, position
    if not position:
        return
    entry = position['entry']
    margin = position['margin']
    if position['side'] == 'LONG':
        pnl_pct = (price - entry) / entry
    else:
        pnl_pct = (entry - price) / entry
    pnl = pnl_pct * margin * LEVERAGE
    balance += pnl
    msg = f"{'🟢' if pnl >= 0 else '🔴'} CLOSED {position['side']} @ ${price:,.2f}\nEntry: ${entry:,.2f}\nPnL: ${pnl:+.2f}\nReason: {reason}\nBalance: ${balance:,.2f}"
    history.append(msg)
    bot.send_message(CHAT_ID, msg)
    position = None

def trading_loop():
    global last_price, prev_price_for_signal, position
    prev_price_for_signal = get_btc()
    time.sleep(60)
    while True:
        try:
            price = get_btc()
            if price is None:
                time.sleep(10)
                continue
            last_price = price

            # --- NO POSITION: LOOK FOR ENTRY ---
            if position is None:
                if prev_price_for_signal:
                    move = (price - prev_price_for_signal) / prev_price_for_signal
                    if move >= ENTRY_MOVE:
                        position = {'side': 'LONG', 'entry': price, 'best': price, 'margin': MARGIN_PER_TRADE}
                        bot.send_message(CHAT_ID, f"🟢 LONG OPEN @ ${price:,.2f}\nMargin $100 | 10x | Riding UP - Will close on first pullback")
                    elif move <= -ENTRY_MOVE:
                        position = {'side': 'SHORT', 'entry': price, 'best': price, 'margin': MARGIN_PER_TRADE}
                        bot.send_message(CHAT_ID, f"🔴 SHORT OPEN @ ${price:,.2f}\nMargin $100 | 10x | Riding DOWN - Will close on first bounce")
                prev_price_for_signal = price

            # --- IN POSITION: TRAILING EXIT ---
            else:
                if position['side'] == 'LONG':
                    if price > position['best']:
                        position['best'] = price
                    pullback = (position['best'] -
