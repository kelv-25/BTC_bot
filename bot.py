import time, requests, threading
import telebot

TOKEN = "8819205021:AAFXlBuQ40mXY-EJwp-hME_UOVBpKc60Yjc"
CHAT_ID = "7711171228"

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
    if not position: return
    entry = position['entry']
    margin = position['margin']
    if position['side'] == 'LONG':
        pnl_pct = (price - entry) / entry
    else:
        pnl_pct = (entry - price) / entry
    pnl = pnl_pct * margin * LEVERAGE
    balance += pnl
    msg = f"{'🟢' if pnl>=0 else '🔴'} CLOSED {position['side']} @ ${price:,.2f}\nEntry: ${entry:,.2f}\nPnL: ${pnl:+.2f}\nReason: {reason}\nBalance: ${balance:,.2f}"
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
                time.sleep(10); continue
            last_price = price
            if position is None:
                if prev_price_for_signal:
                    move = (price - prev_price_for_signal) / prev_price_for_signal
                    if move >= ENTRY_MOVE:
                        position = {'side':'LONG','entry':price,'best':price,'margin':MARGIN_PER_TRADE}
                        bot.send_message(CHAT_ID, f"🟢 LONG OPEN @ ${price:,.2f}\nMargin $100 | 10x | Riding UP")
                    elif move <= -ENTRY_MOVE:
                        position = {'side':'SHORT','entry':price,'best':price,'margin':MARGIN_PER_TRADE}
                        bot.send_message(CHAT_ID, f"🔴 SHORT OPEN @ ${price:,.2f}\nMargin $100 | 10x | Riding DOWN")
                prev_price_for_signal = price
            else:
                if position['side'] == 'LONG':
                    if price > position['best']:
                        position['best'] = price
                    pullback = (position['best'] - price) / position['best']
                    profit = (price - position['entry']) / position['entry']
                    if pullback >= TRADEBACK and profit > 0:
                        close_position(price, f"Pulled back {pullback*100:.2f}% from peak")
                        prev_price_for_signal = price
                        time.sleep(120)
                    elif profit <= -0.01:
                        close_position(price, "Stop Loss -1%")
                        prev_price_for_signal = price
                        time.sleep(120)
                else:
                    if price < position['best']:
                        position['best'] = price
                    pullback = (price - position['best']) / position['best']
                    profit = (position['entry'] - price) / position['entry']
                    if pullback >= TRADEBACK and profit > 0:
                        close_position(price, f"Bounced back {pullback*100:.2f}% from low")
                        prev_price_for_signal = price
                        time.sleep(120)
                    elif profit <= -0.01:
                        close_position(price, "Stop Loss -1%")
                        prev_price_for_signal = price
                        time.sleep(120)
        except Exception as e:
            print(f"Loop error: {e}")
        time.sleep(10)

@bot.message_handler(commands=['start'])
def start(m):
    bot.reply_to(m, f"🤖 FUTURES SCALPER LIVE\n💰 ${balance:.2f} | 10x Leverage\nLONG/SHORT + Trailing Exit")

@bot.message_handler(commands=['balance'])
def bal(m):
    bot.reply_to(m, f"💰 FUTURES BALANCE\nCash: ${balance:.2f}\nPrice: ${last_price}\nPosition: {position}")

@bot.message_handler(commands=['position'])
def pos(m):
    if position:
        bot.reply_to(m, f"📊 {position['side']} @ ${position['entry']:,.2f}\nBest: ${position['best']:,.2f}\nNow: ${last_price}")
    else:
        bot.reply_to(m, "📭 No position - Waiting for 0.2% move")

@bot.message_handler(commands=['history'])
def hist(m):
    bot.reply_to(m, "\n\n".join(history[-5:]) if history else "No trades yet")

threading.Thread(target=trading_loop, daemon=True).start()
bot.send_message(CHAT_ID, "🤖 Bot Started - FUTURES PAPER TRADING\n💰 $1000 | 10x | Trailing Exit")
bot.polling(none_stop=True)
