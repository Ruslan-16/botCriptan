import os
import json
import requests
from datetime import datetime, timedelta, time
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import nest_asyncio
import asyncio
from flask import Flask, request
from hypercorn.asyncio import serve
from hypercorn.config import Config

import firebase_admin
from firebase_admin import credentials, firestore

# Инициализация Flask
app = Flask(__name__)
nest_asyncio.apply()

# Переменные окружения
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
CMC_API_KEY = os.getenv("CMC_API_KEY")
WEBHOOK_URL = "https://botcriptan.onrender.com"  # URL на Render

# Инициализация Firebase с использованием отдельных переменных окружения
firebase_credentials = {
    "type": os.getenv("FIREBASE_TYPE"),
    "project_id": os.getenv("FIREBASE_PROJECT_ID"),
    "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("FIREBASE_PRIVATE_KEY"),
    "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
    "client_id": os.getenv("FIREBASE_CLIENT_ID"),
    "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
    "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_X509_CERT_URL"),
    "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_X509_CERT_URL")
}

# Инициализация Firebase
cred = credentials.Certificate(firebase_credentials)
firebase_admin.initialize_app(cred)
db = firestore.client()

# Список символов криптовалют
SYMBOLS = ["BTC", "ETH", "ADA", "PEPE", "SOL", "SUI", 'TON', 'FET', 'APT', 'AVAX', 'FLOKI', 'TWT', 'ALGO',
           'CAKE', '1INCH', 'MANA', 'FLOW', 'EGLD', 'ARB', 'DYDX', 'APEX', 'CRV', 'ATOM', 'POL', 'OP', 'SEI']


# Функция для сохранения данных в Firestore
def save_crypto_data(data, doc_name):
    db.collection("crypto_data").document(doc_name).set({
        "data": data,
        "timestamp": int(datetime.now().timestamp())
    })


# Получение данных о криптовалютах с API
def fetch_crypto_data():
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    headers = {"Accepts": "application/json", "X-CMC_PRO_API_KEY": CMC_API_KEY}
    params = {"symbol": ",".join(SYMBOLS), "convert": "USD"}
    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        return response.json()["data"]
    else:
        print(f"Error fetching data: {response.status_code}")
        return None


# Формирование сообщения с текущими данными о криптовалютах
def generate_crypto_message(current_data):
    message = f"🗓️ Актуальные данные на {datetime.now().strftime('%d-%m-%Y %H:%M')}:\n"
    for symbol in SYMBOLS:
        if symbol in current_data:
            price = current_data[symbol]["quote"]["USD"]["price"]
            message += f"💰{symbol}: 📈{price:.2f} USD\n"
    return message


# Формирование сообщения с историческими данными за последние 12 и 24 часа
def generate_history_message():
    # Получаем данные за последние 12 и 24 часа из Firestore
    data_12hr = db.collection("crypto_data").document("12hr").get().to_dict()
    data_24hr = db.collection("crypto_data").document("24hr").get().to_dict()

    message = "📊 Исторические данные цен на криптовалюты:\n\n"
    if data_12hr:
        message += "⏳ Цены 12 часов назад:\n"
        for symbol in SYMBOLS:
            if symbol in data_12hr["data"]:
                price_12hr = data_12hr["data"][symbol]["quote"]["USD"]["price"]
                message += f"💰{symbol}: {price_12hr:.2f} USD\n"
        message += "\n"
    if data_24hr:
        message += "⏳ Цены 24 часа назад:\n"
        for symbol in SYMBOLS:
            if symbol in data_24hr["data"]:
                price_24hr = data_24hr["data"][symbol]["quote"]["USD"]["price"]
                message += f"💰{symbol}: {price_24hr:.2f} USD\n"

    return message


# Функция для команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # Приветственное сообщение с описанием доступных команд
    welcome_message = (
        "👋 Добро пожаловать! Вы подписаны на бота для отслеживания цен на криптовалюты.\n\n"
        "Вот доступные команды:\n"
        "/crypto — Получить текущие данные о криптовалютах\n"
        "/count — Узнать количество подписчиков бота\n"
        "/history — Посмотреть цены за последние 12 и 24 часа\n"
        "/start — Подписаться на рассылку\n\n"
        "Рассылка с актуальными ценами будет приходить автоматически дважды в день: в 6:00 и 16:00.\n"
        "Введите команду, чтобы получить нужную информацию! 📈"
    )

    # Отправляем приветственное сообщение пользователю
    await update.message.reply_text(welcome_message)

    # Добавляем пользователя в базу данных Firestore
    db.collection('users').document(str(chat_id)).set({"subscribed": True})


# Функция для команды /crypto
async def crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем и отправляем текущие данные о криптовалютах
    current_data = fetch_crypto_data()
    if current_data:
        message = generate_crypto_message(current_data)
        await update.message.reply_text(message)
    else:
        await update.message.reply_text("Не удалось получить данные о криптовалютах.")


# Функция для команды /count
async def count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем количество подписанных пользователей
    users = db.collection('users').stream()
    user_count = sum(1 for _ in users)
    await update.message.reply_text(f"В боте {user_count} подписчиков.")


# Функция для команды /history
async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем исторические данные за последние 12 и 24 часа
    message = generate_history_message()
    await update.message.reply_text(message)


# Функция для обработки обычных текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Доступные команды: /start, /crypto, /count, /history.")


# Функция для отправки обновлений пользователям
async def send_crypto_update(context: ContextTypes.DEFAULT_TYPE):
    print("Запуск send_crypto_update...")
    current_data = fetch_crypto_data()
    if not current_data:
        print("Ошибка при получении данных о криптовалюте")
        return

    # Формируем сообщение
    message = generate_crypto_message(current_data)

    # Отправляем сообщение всем подписанным пользователям
    users_ref = db.collection('users')
    users = [doc.id for doc in users_ref.stream()]

    for chat_id in users:
        try:
            await context.bot.send_message(chat_id=chat_id, text=message)
            print(f"Сообщение отправлено пользователю {chat_id}")
        except Exception as e:
            print(f"Ошибка отправки для {chat_id}: {e}")
            if "bot was blocked" in str(e) or "user is deactivated" in str(e):
                db.collection('users').document(str(chat_id)).delete()


# Сохранение данных каждые 12 и 24 часа
async def update_crypto_data(context: ContextTypes.DEFAULT_TYPE):
    print("Запуск обновления данных криптовалюты...")
    current_data = fetch_crypto_data()
    if current_data:
        # Сохраняем текущие данные как "последние 12 часов" и "последние 24 часа"
        save_crypto_data(current_data, "12hr")
        save_crypto_data(current_data, "24hr")
        print("Данные криптовалюты обновлены.")


# Основная функция инициализации
async def main():
    # Создание бота
    bot_app = Application.builder().token(TG_BOT_TOKEN).build()

    # Добавление обработчиков команд
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("crypto", crypto))
    bot_app.add_handler(CommandHandler("count", count))
    bot_app.add_handler(CommandHandler("history", history))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запланировать ежедневное обновление и обновления каждые 12 и 24 часа
    job_queue = bot_app.job_queue
    job_queue.run_daily(send_crypto_update, time(hour=6, minute=0))
    job_queue.run_daily(send_crypto_update, time(hour=16, minute=0))
    job_queue.run_repeating(update_crypto_data, interval=timedelta(hours=12), first=0)

    # Инициализация бота и установка вебхука
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
