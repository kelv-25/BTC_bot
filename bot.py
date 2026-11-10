import os
import time
import requests
import threading
import telebot

TOKEN = os.getenv("TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID", "0"))
bot = telebot.TeleBot(TOKEN)

balance = 1000.0
LEVERAGE = 10
MARGIN_PER_TRADE = 100.0
TRADEBACK = 0.002
ENTRY_MOVE = 0.002

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
    entry = position["entry"]
    margin = position["margin"]
    if position["side"] == "LONG":
        pnl_pct = (price - entry) / entry
    else:
        pnl_pct = (entry - price) / entry
    pnl = pnl_pct * margin * LEVERAGE
    balance += pnl
    msg = "CLOSED " + position["side"] + " at " + str(round(price, 2)) + " PnL " + str(round(pnl, 2)) + " Reason " + reason + " Balance " + str(round(balance, 2))
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
            if position is None:
                if prev_price_for_signal:
                    move = (price - prev_price_for_signal) / prev_price_for_signal
                    if move >= ENTRY_MOVE:
                        position = {"side": "LONG", "entry": price, "best": price, "margin": MARGIN_PER_TRADE}
                        bot.send_message(CHAT_ID, "LONG OPEN at " + str(round(price, 2)) + " Margin 100 10x")
                    elif move <= -ENTRY_MOVE:
                        position = {"side": "SHORT", "entry": price, "best": price, "margin": MARGIN_PER_TRADE}
                        bot.send_message(CHAT_ID, "SHORT OPEN at " + str(round(price, 2)) + " Margin 100 10x")
                prev_price_for_signal = price
            else:
                if position["side"] == "LONG":
                    if price > position["best"]:
                        position["best"] = price
                    pullback = (position["best"] - price) / position["best"]
                    profit = (price - position["entry"]) / position["entry"]
                    if pullback >= TRADEBACK and profit > 0:
                        close_position(price, "Pulled back from peak")
                        prev_price_for_signal = price
                        time.sleep(120)
                    elif profit <= -0.01:
                        close_position(price, "Stop Loss -1 pct")
                        prev_price_for_signal = price
                        time.sleep(120)
                else:
                    if price < position["best"]:
                        position["best"] = price
                    pullback = (price - position["best"]) / position["best"]
                    profit = (position["entry"] - price) / position["entry"]
                    if pullback >= TRADEBACK and profit > 0:
                        close_position(price, "Bounced from low")
                        prev_price_for_signal = price
                        time.sleep(120)
                    elif profit <= -0.01:
                        close_position(price, "Stop Loss -1 pct")
                        prev_price_for_signal = price
                        time.sleep(120)
        except Exception as e:
            print("Loop error: " + str(e))
        time.sleep(10)

@bot.message_handler(commands=["start"])
def start(m):
    bot.reply_to(m, "FUTURES SCALPER LIVE Balance " + str(round(balance, 2)) + " 10x")

@bot.message_handler(commands=["balance"])
def bal(m):
    bot.reply_to(m, "Balance " + str(round(balance, 2)) + " Price " + str(last_price))

@bot.message_handler(commands=["position"])
def pos(m):
    if position:
        bot.reply_to(m, "Position " + str(position))
    else:
        bot.reply_to(m, "No position - Waiting for 0.2 pct move")

@bot.message_handler(commands=["history"])
def hist(m):
    if history:
        bot.reply_to(m, "\n".join(history[-5:]))
    else:
        bot.reply_to(m, "No trades yet")

threading.Thread(target=trading_loop, daemon=True).start()
bot.send_message(CHAT_ID, "Bot Started - FUTURES PAPER TRADING 1000 USD 10x")
bot.polling(none_stop=True)
