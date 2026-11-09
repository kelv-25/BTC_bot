import os
import time
import requests
import threading
from flask import Flask

TELEGRAM_TOKEN = os.environ.get("8819205021:AAGKa6sArG1SJhygc-Zq3cVFE0khtRUA27o")
CHAT_ID = os.environ.get("7711171228")
LEVERAGE = 10

in_trade = False
entry_price = 0
side = ""
last_price = 0
last_rsi = 0
cooldown_until = 0
surge_locks = 0
drop_locks = 0

app = Flask(__name__)

@app.route("/")
def home():
    return f"Bot Alive. Price: {last_price} RSI: {last_rsi} In Trade: {in_trade} {side} Surge Locks: {surge_locks} Drop Locks: {drop_locks}"

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except:
        print("Telegram failed")

def get_data():
    global last_price, last_rsi
    try:
        url = "https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=5m&limit=100"
        data = requests.get(url, timeout=10).json()
        closes = [float(c[4]) for c in data]
        price = closes[-1]
        price_5m_ago = closes[-2]
        ema50 = sum(closes[-50:]) / 50
        ema200 = sum(closes[-100:]) / 100
        gains = [max(0, closes[i]-closes[i-1]) for i in range(1, len(closes))]
        losses = [max(0, closes[i-1]-closes[i]) for i in range(1, len(closes))]
        avg_gain = sum(gains[-14:]) / 14
        avg_loss = sum(losses[-14:]) / 14
        rsi = 100 if avg_loss == 0 else 100 - (100 / (1 + (avg_gain / avg_loss)))
        last_price, last_rsi = price, round(rsi,1)
        return price, rsi, ema50, ema200, price_5m_ago
    except:
        print("Price fetch failed")
        return None, None, None, None, None

def bot_loop():
    global in_trade, entry_price, side, cooldown_until, surge_locks, drop_locks
    send_telegram("Bot Started - AUTO + 1% SURGE LOCK + 1% DROP LOCK + 12 MIN PAUSE - BTC/USDT 5m - PAPER MODE")
    while True:
        price, rsi, ema50, ema200, price_5m_ago = get_data()
        if price is None:
            time.sleep(10)
            continue

        # --- 1% SINGLE CANDLE MOVE CHECK ---
        move_5m = ((price - price_5m_ago) / price_5m_ago) * 100

        # SURGE UP +1%
        if move_5m >= 1.0:
            surge_locks += 1
            if in_trade:
                if side == "LONG":
                    move = ((price - entry_price) / entry_price) * 100
                else:
                    move = ((entry_price - price) / entry_price) * 100
                profit = move * LEVERAGE
                send_telegram(f"SURGE LOCK +1% ACTIVATED\nSingle candle: +{move_5m:.2f}%\nClosed {side} at {price}\nResult: {profit:.2f}% with 10x\nPaused 12 mins")
                in_trade = False
            else:
                send_telegram(f"SURGE LOCK +1% ACTIVATED\nSingle candle: +{move_5m:.2f}%\nNo trade opened - Waiting 12 mins")
            cooldown_until = time.time() + (12 * 60)
            time.sleep(60)
            continue

        # DROP DOWN -1% - SINGLE DROP
        if move_5m <= -1.0:
            drop_locks += 1
            if in_trade:
                if side == "LONG":
                    move = ((price - entry_price) / entry_price) * 100
                else:
                    move = ((entry_price - price) / entry_price) * 100
                profit = move * LEVERAGE
                send_telegram(f"DROP LOCK -1% ACTIVATED\nSingle drop: {move_5m:.2f}% in 5m\nClosed {side} at {price}\nResult: {profit:.2f}% with 10x\nPaused 12 mins - Not catching falling knife")
                in_trade = False
            else:
                send_telegram(f"DROP LOCK -1% ACTIVATED\nSingle drop: {move_5m:.2f}% in 5m\nNo trade opened - Waiting 12 mins")
            cooldown_until = time.time() + (12 * 60)
            time.sleep(60)
            continue

        # --- COOLDOWN CHECK ---
        if time.time() < cooldown_until:
            remaining = int((cooldown_until - time.time()) / 60)
            print(f"In Lock Cooldown - {remaining} mins left - Price: {price}")
            time.sleep(60)
            continue

        print(f"Price: {price} | RSI: {rsi:.1f} | EMA50: {ema50:.0f} | EMA200: {ema200:.0f} | In Trade: {in_trade} | 5m Move: {move_5m:.2f}%")

        # --- ONLY TRADE WHEN CLEARLY BULLISH OR BEARISH - WAIT WHEN SIDEWAYS ---
        if not in_trade:
            if ema50 > ema200 and rsi < 65:
                in_trade, side, entry_price = True, "LONG", price
                send_telegram(f"AUTO LONG ENTERED - BULLISH\nPrice: {price}\nRSI: {rsi:.1f}\nTP: +0.4% | SL: -0.4% | Surge Lock: +1% | Drop Lock: -1%")
            elif ema50 < ema200 and rsi > 35:
                in_trade, side, entry_price = True, "SHORT", price
                send_telegram(f"AUTO SHORT ENTERED - BEARISH\nPrice: {price}\nRSI: {rsi:.1f}\nTP: +0.4% | SL: -0.4% | Surge Lock: +1% | Drop Lock: -1%")

        if in_trade:
            if side == "LONG":
                move = ((price - entry_price) / entry_price) * 100
            else:
                move = ((entry_price - price) / entry_price) * 100
            profit = move * LEVERAGE
            if move >= 0.4:
                send_telegram(f"PROFIT LOCK! {side}\nExit: {price}\nProfit: {profit:.2f}% with 10x")
                in_trade = False
            elif move <= -0.4:
                send_telegram(f"STOP LOSS! {side}\nExit: {price}\nLoss: {profit:.2f}% with 10x")
                in_trade = False

        time.sleep(60)

threading.Thread(target=bot_loop, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
