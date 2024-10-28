import os
import json
import requests
from datetime import datetime, time
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio
import nest_asyncio
from flask import Flask, request

# Initialize Flask and apply nest_asyncio for compatibility
app = Flask(__name__)
nest_asyncio.apply()

# Load environment variables
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
CMC_API_KEY = os.getenv("CMC_API_KEY")
WEBHOOK_URL = "https://botcriptan.onrender.com/webhook"
USERS_FILE = "users.json"

# Load and save user functions
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

# Fetch cryptocurrency data
def get_crypto_data():
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    headers = {"Accepts": "application/json", "X-CMC_PRO_API_KEY": CMC_API_KEY}
    symbols = ["BTC", "ETH", "ADA", "PEPE", "SOL"]
    params = {"symbol": ",".join(symbols), "convert": "USD"}
    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()["data"]
        message = f"🗓️ Data on {datetime.now().strftime('%Y-%m-%d')}:\n"
        for symbol in symbols:
            if symbol in data:
                price = data[symbol]["quote"]["USD"]["price"]
                message += f"{symbol}: ${price:.2f}\n"
        return message
    else:
        return f"Error fetching data: {response.status_code}"

# Send updates to users
async def send_crypto_update(context: ContextTypes.DEFAULT_TYPE):
    message = get_crypto_data()
    users = load_users()
    for chat_id in users[:]:
        try:
            await context.bot.send_message(chat_id=chat_id, text=message)
        except Exception as e:
            if "bot was blocked" in str(e) or "user is deactivated" in str(e):
                users.remove(chat_id)
                save_users(users)

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text("You're subscribed to daily crypto updates at 9:00 and 19:00.")
    add_user(chat_id)

# Create bot application globally
bot_app = Application.builder().token(TG_BOT_TOKEN).build()

# Flask endpoint for Telegram webhook
@app.route('/webhook', methods=['POST'])
async def webhook():
    data = request.get_json()
    update = Update.de_json(data, bot_app.bot)
    await bot_app.update_queue.put(update)
    return "ok", 200

# Main bot initialization and webhook setup
async def main():
    bot_app.add_handler(CommandHandler("start", start))

    # Schedule daily updates
    job_queue = bot_app.job_queue
    job_queue.run_daily(send_crypto_update, time(hour=9, minute=0))
    job_queue.run_daily(send_crypto_update, time(hour=19, minute=0))

    # Set webhook
    await bot_app.initialize()
    await bot_app.bot.set_webhook(WEBHOOK_URL)
    await bot_app.start()

# Run the bot and Flask server
if __name__ == "__main__":
    asyncio.run(main())
    app.run(host="0.0.0.0", port=443)
