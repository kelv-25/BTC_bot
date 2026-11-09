import os, time, requests, threading
import telebot

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID", "0"))
bot = telebot.TeleBot(TOKEN)

# PAPER TRADING SETTINGS
balance = 1000.0
btc_held = 0.0
entry_price = 0.0
history = []
last_price = None
ref_price = None
last_trade_time = 0
PAUSE = 12 * 60

def get_btc():
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=10)
        return float(r.json()["price"])
    except:
        return None

def send_msg(text):
    try:
        bot.send_message(CHAT_ID, text)
    except Exception as e:
        print("Send error:", e)

@bot.message_handler(commands=['start'])
def start_cmd(m):
    bot.reply_to(m, "🤖 Paper Trading Bot LIVE\nBalance: $1000\nRisk: 10% per trade\nCommands: /balance /position /history")

@bot.message_handler(commands=['balance'])
def balance_cmd(m):
    global last_price
    total = balance + (btc_held * (last_price or 0))
    bot.reply_to(m, f"💰 PAPER BALANCE\n\nCash: ${balance:.2f}\nBTC Held: {btc_held:.6f}\nPrice: ${last_price}\nTotal: ${total:.2f}\nProfit: ${total-1000:.2f}")

@bot.message_handler(commands=['position'])
def position_cmd(m):
    if btc_held > 0:
        pnl = (last_price - entry_price) / entry_price * 100 if entry_price else 0
        bot.reply_to(m, f"📈 IN POSITION\nBought at: ${entry_price:.2f}\nNow: ${last_price:.2f}\nPnL: {pnl:.2f}%")
    else:
        bot.reply_to(m, "📭 No position - Waiting for signal.")

@bot.message_handler(commands=['history'])
def history_cmd(m):
    if not history:
        bot.reply_to(m, "No trades yet.")
    else:
        bot.reply_to(m, "📜 LAST TRADES:\n\n" + "\n".join(history[-10:]))

def trading_loop():
    global balance, btc_held, entry_price, last_price, ref_price, last_trade_time
    send_msg("🤖 Bot Started - PAPER TRADING\n💰 $1000 | 10% per trade\nAUTO +1% SURGE LOCK +1% DROP LOCK + 12 MIN PAUSE")
    while True:
        price = get_btc()
        if price:
            last_price = price
            if ref_price is None:
                ref_price = price
            change = (price - ref_price) / ref_price * 100
            now = time.time()
            if change >= 1.0 and btc_held == 0 and (now - last_trade_time > PAUSE):
                amount = balance * 0.10
                btc_held = amount / price
                balance -= amount
                entry_price = price
                last_trade_time = now
                ref_price = price
                history.append(f"BUY {btc_held:.4f} @ {price:.0f}")
                send_msg(f"🟢 SURGE LOCK +1% - PAPER BUY\nBought {btc_held:.6f} BTC @ ${price:.2f}\nSpent: ${amount:.2f}\nCash Left: ${balance:.2f}")
            elif btc_held > 0:
                pnl_pct = (price - entry_price) / entry_price * 100
                if change <= -1.0 or pnl_pct >= 1.5:
                    sell_value = btc_held * price
                    profit = sell_value - (btc_held * entry_price)
                    balance += sell_value
                    history.append(f"SELL @ {price:.0f} Profit ${profit:.2f}")
                    send_msg(f"🔴 SELL - PAPER TRADE CLOSED\nSold {btc_held:.6f} BTC @ ${price:.2f}\nProfit: ${profit:.2f}\nNew Balance: ${balance:.2f}")
                    btc_held = 0.0
                    last_trade_time = now
                    ref_price = price
            if abs(change) < 0.2:
                ref_price = price
        time.sleep(30)

threading.Thread(target=trading_loop, daemon=True).start()
print("Bot polling...")
bot.infinity_polling()
