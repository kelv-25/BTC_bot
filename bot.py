import os, time, requests, asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID", "0"))

# PAPER TRADING SETTINGS
balance = 1000.0  # Starting fake USDT
btc_held = 0.0
entry_price = 0.0
history = []
last_price = None
ref_price = None
last_trade_time = 0
PAUSE = 12 * 60  # 12 min pause

def get_btc():
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=10)
        return float(r.json()["price"])
    except:
        return None

async def send_msg(app, text):
    try:
        await app.bot.send_message(chat_id=CHAT_ID, text=text)
    except Exception as e:
        print("Send error:", e)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Paper Trading Bot LIVE\nBalance: $1000\nRisk: 10% per trade\nCommands: /balance /position /history")

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = balance + (btc_held * (last_price or 0))
    await update.message.reply_text(f"💰 PAPER BALANCE\n\nCash: ${balance:.2f}\nBTC Held: {btc_held:.6f} BTC\nCurrent Price: ${last_price}\nTotal Value: ${total:.2f}\nProfit: ${total-1000:.2f}")

async def position_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if btc_held > 0:
        pnl = (last_price - entry_price) / entry_price * 100 if entry_price else 0
        await update.message.reply_text(f"📈 IN POSITION\nBought at: ${entry_price:.2f}\nNow: ${last_price:.2f}\nPnL: {pnl:.2f}%")
    else:
        await update.message.reply_text("📭 No position - Waiting for signal. Cash ready.")

async def history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not history:
        await update.message.reply_text("No trades yet.")
        return
    txt = "📜 LAST TRADES:\n\n" + "\n".join(history[-10:])
    await update.message.reply_text(txt)

async def trading_loop(app):
    global balance, btc_held, entry_price, last_price, ref_price, last_trade_time
    await send_msg(app, "🤖 Bot Started - PAPER TRADING\n💰 $1000 | 10% per trade\nAUTO + 1% SURGE LOCK + 1% DROP LOCK + 12 MIN PAUSE")
    while True:
        price = get_btc()
        if price:
            last_price = price
            if ref_price is None:
                ref_price = price
            change = (price - ref_price) / ref_price * 100
            now = time.time()
            # SURGE +1% -> BUY if not holding and pause over
            if change >= 1.0 and btc_held == 0 and (now - last_trade_time > PAUSE):
                amount_usdt = balance * 0.10
                btc_held = amount_usdt / price
                balance -= amount_usdt
                entry_price = price
                last_trade_time = now
                ref_price = price
                msg = f"🟢 SURGE LOCK +1% - PAPER BUY\nBought {btc_held:.6f} BTC @ ${price:.2f}\nSpent: ${amount_usdt:.2f}\nCash Left: ${balance:.2f}"
                history.append(f"BUY {btc_held:.4f} @ {price:.0f}")
                await send_msg(app, msg)
            # DROP -1% or Take Profit +1.5% -> SELL if holding
            elif btc_held > 0:
                pnl_pct = (price - entry_price) / entry_price * 100
                if change <= -1.0 or pnl_pct >= 1.5:
                    sell_value = btc_held * price
                    profit = sell_value - (btc_held * entry_price)
                    balance += sell_value
                    msg = f"🔴 SELL - PAPER TRADE CLOSED\nSold {btc_held:.6f} BTC @ ${price:.2f}\nProfit: ${profit:.2f}\nNew Balance: ${balance:.2f}"
                    history.append(f"SELL @ {price:.0f} Profit ${profit:.2f}")
                    btc_held = 0.0
                    last_trade_time = now
                    ref_price = price
                    await send_msg(app, msg)
                # Update ref if no trade for a while to avoid stale ref
            if abs(change) < 0.2:
                ref_price = price
        await asyncio.sleep(30)

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("position", position_cmd))
    app.add_handler(CommandHandler("history", history_cmd))
    asyncio.create_task(trading_loop(app))
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
