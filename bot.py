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
# Применение патча для работы с уже запущенным циклом событий
nest_asyncio.apply()

# Переменные окружения
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
CMC_API_KEY = os.getenv("CMC_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # URL для вебхука, например https://yourproject.onrender.com
USERS_FILE = "users.json"

# Flask-приложение для обработки вебхуков
app = Flask(__name__)

# Загрузка и сохранение пользователей
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

# Получение данных о криптовалютах
def get_crypto_data():
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    headers = {"Accepts": "application/json", "X-CMC_PRO_API_KEY": CMC_API_KEY}
    watchlist_symbols = ["BTC", "ETH", "ADA", "PEPE", "SOL"]
    symbol_param = ",".join(watchlist_symbols)

    params = {"symbol": symbol_param, "convert": "USD"}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()["data"]
        message = f"🗓️ Актуальные данные на {datetime.now().strftime('%Y-%m-%d')}:\n"
        for symbol in watchlist_symbols:
            if symbol in data:
                crypto = data[symbol]
                price = crypto["quote"]["USD"]["price"]
                message += f"{crypto['name']} ({crypto['symbol']}): ${price:.2f}\n"
        return message
    else:
        return f"Ошибка при запросе данных: {response.status_code}"

# Отправка сообщений всем пользователям
async def send_crypto_update(context: ContextTypes.DEFAULT_TYPE):
    message = get_crypto_data()
    users = load_users()
    for chat_id in users[:]:
        try:
            await context.bot.send_message(chat_id=chat_id, text=message)
            print(f"Сообщение отправлено пользователю {chat_id}")
        except Exception as e:
            print(f"Ошибка при отправке для {chat_id}: {e}")
            if "bot was blocked by the user" in str(e) or "user is deactivated" in str(e):
                users.remove(chat_id)
                save_users(users)
                print(f"Пользователь {chat_id} удалён из списка.")

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text("Привет! Вы подписаны на рассылку криптовалют в 9:00 и 19:00.")
    add_user(chat_id)

# Основная функция бота с вебхуком
async def main():
    # Инициализация бота и настройка обработчиков
    bot_app = Application.builder().token(TG_BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))

    # Настройка задач
    job_queue = bot_app.job_queue
    job_queue.run_daily(send_crypto_update, time(hour=9, minute=0))
    job_queue.run_daily(send_crypto_update, time(hour=19, minute=0))

    # Установка вебхука
    await bot_app.initialize()    # Инициализация перед стартом
    await bot_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    print("Webhook установлен!")

    # Запуск бота
    await bot_app.start()         # Запуск
    await bot_app.updater.start_polling()  # Запуск обновлений

# Flask endpoint для Telegram webhook
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    bot_app.update_queue.put_nowait(data)
    return "ok", 200

# Запуск бота с Flask
if __name__ == "__main__":
    asyncio.run(main())
    app.run(host="0.0.0.0", port=80)
