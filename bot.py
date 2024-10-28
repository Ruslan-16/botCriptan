import os
import json
import requests
from datetime import datetime, time
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import nest_asyncio
from flask import Flask, request
import asyncio

# Initialize Flask app and allow async compatibility
app = Flask(__name__)
app.debug = True
nest_asyncio.apply()

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
CMC_API_KEY = os.getenv("CMC_API_KEY")
WEBHOOK_URL = "https://botcriptan.onrender.com"

# User data functions
def load_users():
    if os.path.exists("users.json"):
        with open("users.json", "r") as f:
            return json.load(f)
    return []

def save_users(users):
    with open("users.json", "w") as f:
        json.dump(users, f)

def add_user(chat_id):
    users = load_users()
    if chat_id not in users:
        users.append(chat_id)
        save_users(users)

# Fetch crypto data
def get_crypto_data():
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    headers = {"Accepts": "application/json", "X-CMC_PRO_API_KEY": CMC_API_KEY}
    symbols = ["BTC", "ETH", "ADA", "PEPE", "SOL"]
    params = {"symbol": ",".join(symbols), "convert": "USD"}
    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()["data"]
        message = f"🗓️ Crypto Data on {datetime.now().strftime('%Y-%m-%d')}:\n"
        for symbol in symbols:
            if symbol in data:
                price = data[symbol]["quote"]["USD"]["price"]
                message += f"{symbol}: ${price:.2f}\n"
        return message
    else:
        return f"Error fetching data: {response.status_code}"

# Send crypto updates to users
async def send_crypto_update(context: ContextTypes.DEFAULT_TYPE):
    message = get_crypto_data()
    users = load_users()
    for chat_id in users[:]:
        try:
            await context.bot.send_message(chat_id=chat_id, text=message)
        except Exception as e:
            print(f"Error sending to {chat_id}: {e}")
            if "bot was blocked" in str(e) or "user is deactivated" in str(e):
                users.remove(chat_id)
                save_users(users)

# Handle /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text("You've subscribed to daily crypto updates.")
    add_user(chat_id)

# Initialize Telegram bot
bot_app = Application.builder().token(TG_BOT_TOKEN).build()

# Webhook handler for Telegram
@app.route('/webhook', methods=['POST'])
async def webhook():
    data = request.get_json()
    try:
        update = Update.de_json(data, bot_app.bot)
        await bot_app.update_queue.put(update)
        return "ok", 200
    except Exception as e:
        print(f"Webhook handling error: {e}")
        return "Error", 500

# Main bot function with webhook setup
async def main():
    bot_app.add_handler(CommandHandler("start", start))
    job_queue = bot_app.job_queue
    job_queue.run_daily(send_crypto_update, time(hour=9, minute=0))
    job_queue.run_daily(send_crypto_update, time(hour=19, minute=0))

    await bot_app.initialize()
    await bot_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    print("Webhook set up successfully!")

    await bot_app.start()

if __name__ == "__main__":
    # Run both the bot and Flask app in parallel
    asyncio.run(asyncio.gather(main(), app.run_task(host="0.0.0.0", port=5000)))
