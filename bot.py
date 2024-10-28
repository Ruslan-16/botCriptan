import os
import json
import requests
from datetime import datetime, time
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import nest_asyncio
import asyncio
from flask import Flask, request
from hypercorn.asyncio import serve
from hypercorn.config import Config

# Инициализация Flask
app = Flask(__name__)
nest_asyncio.apply()

# Переменные окружения
TG_BOT_TOKEN = "7602913247:AAFFy0De4_DSBg_c0V_wiK1TECMtAgMZJA8"
CMC_API_KEY = "c923b3dc-cd07-4216-8edc-9d73beb665cc"
WEBHOOK_URL = "https://botcriptan.onrender.com"  # URL на Rende

# Загрузка пользователей
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

# Получение данных о криптовалютах
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

# Отправка обновлений пользователям
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

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text("Вы подписались на ежедневную рассылку анализа цен на  Криптовалюты в 9:00 и 19:00.")
    add_user(chat_id)
    print("Received /start command")

# Создание бота
bot_app = Application.builder().token(TG_BOT_TOKEN).build()

# Вебхук Telegram
@app.route('/webhook', methods=['POST'])
async def webhook():
    data = request.get_json()
    try:
        update = Update.de_json(data, bot_app.bot)
        await bot_app.update_queue.put(update)
        return "ok", 200
    except Exception as e:
        print(f"Webhook processing error: {e}")
        return "Error", 500

# Основная функция инициализации
async def main():
    bot_app.add_handler(CommandHandler("start", start))

    # Задание на отправку обновлений дважды в день
    job_queue = bot_app.job_queue
    job_queue.run_daily(send_crypto_update, time(hour=9, minute=0))
    job_queue.run_daily(send_crypto_update, time(hour=15, minute=45))
    job_queue.run_daily(send_crypto_update, time(hour=15, minute=50))
    await bot_app.initialize()
    await bot_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    print("Webhook set!")
    await bot_app.start()

# Запуск Flask и бота с Hypercorn
async def run_flask():
    config = Config()
    config.bind = ["0.0.0.0:10000"]  # Render открывает порт 10000
    await serve(app, config)

# Запуск Flask и бота
if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.run(asyncio.gather(main(), run_flask()))
