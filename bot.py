import os
import json
import requests
from datetime import datetime, time
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio
import nest_asyncio
from flask import Flask, request
from background import keep_alive

keep_alive()
nest_asyncio.apply()

# Environment variables
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
CMC_API_KEY = os.getenv("CMC_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
USERS_FILE = "users.json"

app = Flask(__name__)

# Global bot application initialization
bot_app = Application.builder().token(TG_BOT_TOKEN).build()

# Load and save users
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return []

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)

def add_user(chat_id):
    users = load_users()
    if chat_id not in users:
        users.append(chat_id)
        save_users(users)

# Crypto data retrieval
def get_crypto_data():
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    headers = {"Accepts": "application/json", "X-CMC_PRO_API_KEY": CMC_API_KEY}
    symbols = ["BTC", "ETH", "ADA", "PEPE", "SOL"]
    params = {"symbol": ",".join(symbols), "convert": "USD"}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()["data"]
        message = f"🗓️ Data as of {datetime.now().strftime('%Y-%m-%d')}:\n"
        for symbol in symbols:
            if symbol in data:
                crypto = data[symbol]
                price = crypto["quote"]["USD"]["price"]
                message += f"{crypto['name']} ({crypto['symbol']}): ${price:.2f}\n"
        return message
    return f"Error retrieving data: {response.status_code}"

# Send crypto updates
async def send_crypto_update(context: ContextTypes.DEFAULT_TYPE):
    message = get_crypto_data()
    users = load_users()
    for chat_id in users[:]:
        try:
            await context.bot.send_message(chat_id=chat_id, text=message)
            print(f"Message sent to {chat_id}")
        except Exception as e:
            print(f"Error for {chat_id}: {e}")
            if "bot was blocked by the user" in str(e) or "user is deactivated" in str(e):
                users.remove(chat_id)
                save_users(users)
                print(f"Removed user {chat_id}")

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text("Subscribed to crypto updates at 9:00 and 19:00.")
    add_user(chat_id)

# Webhook setup function
async def main():
    bot_app.add_handler(CommandHandler("start", start))
    job_queue = bot_app.job_queue
    job_queue.run_daily(send_crypto_update, time(hour=9, minute=0))
    job_queue.run_daily(send_crypto_update, time(hour=19, minute=0))

    await bot_app.initialize()
    await bot_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    print("Webhook set!")

    await bot_app.start()
    await bot_app.updater.start_polling()

# Flask endpoint for webhook
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    update = Update.de_json(data, bot_app.bot)
    asyncio.run(bot_app.update_queue.put(update))
    return "ok", 200

if __name__ == "__main__":
    asyncio.run(main())
    app.run(host="0.0.0.0", port=443)
