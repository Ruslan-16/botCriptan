import os
import json
import aiohttp
from datetime import datetime, timedelta, time
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import nest_asyncio
import asyncio
from flask import Flask, request
from hypercorn.asyncio import serve
from hypercorn.config import Config

# Применяем поддержку асинхронности в Flask
nest_asyncio.apply()

# Инициализация Flask
app = Flask(__name__)

# Переменные окружения с вашими данными
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "7602913247:AAFFy0De4_DSBg_c0V_wiK1TECMtAgMZJA8")
CMC_API_KEY = os.getenv("CMC_API_KEY", "c923b3dc-cd07-4216-8edc-9d73beb665cc")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://ruslan-16-botcriptan-dd61.twc1.net/webhook")

# Файлы для хранения пользователей и данных
USERS_FILE = "users.json"
DATA_FILE = "crypto_data.json"

# Определяем точность для каждого символа
precision = {
    "BTC": 2, "ETH": 2, "ADA": 3, "PEPE": 6, "SOL": 2, "SUI": 2, 'TON': 2, 'FET': 3,
    'APT': 3, 'AVAX': 2, 'FLOKI': 6, 'TWT': 3, 'ALGO': 3, 'CAKE': 2, '1INCH': 3,
    'MANA': 3, 'FLOW': 3, 'EGLD': 2, 'ARB': 3, 'DYDX': 2, 'APEX': 3, 'CRV': 3,
    'ATOM': 2, 'POL': 3, 'OP': 2, 'SEI': 3
}

# Функция форматирования данных
def format_crypto_data(data, period):
    if not data:
        return f"Данных {period} нет."

    message = f"🕒 Данные о криптовалютах {period}:\n"

    for ts, prices in data.items():
        # Форматируем метку времени в формат DD.MM.YYYY HH:MM:SS
        formatted_time = datetime.fromisoformat(ts).strftime('%d.%m.%Y %H:%M:%S')
        message += f"\n⏱️ Время: {formatted_time}\n"

        for symbol, price in prices["prices"].items():
            # Применяем нужное количество знаков после запятой
            decimals = precision.get(symbol, 2)
            message += f"💰 {symbol}: ${price:.{decimals}f}\n"

    return message

# Функции для работы с файлами
def load_json(filename):
    try:
        if os.path.exists(filename):
            with open(filename, "r") as f:
                return json.load(f)
        return {}
    except json.JSONDecodeError:
        print(f"Ошибка чтения файла {filename}. Возможно, файл поврежден.")
        return {}

def save_json(filename, data):
    try:
        with open(filename, "w") as f:
            json.dump(data, f)
    except IOError as e:
        print(f"Ошибка записи файла {filename}: {e}")

# Функции для работы с крипто-данными
async def fetch_crypto_data():
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    headers = {"Accepts": "application/json", "X-CMC_PRO_API_KEY": CMC_API_KEY}
    symbols = ["BTC", "ETH", "ADA", "PEPE", "SOL", "SUI", 'TON', 'FET', 'APT', 'AVAX', 'FLOKI', 'TWT', 'ALGO',
               'CAKE', '1INCH', 'MANA', 'FLOW', 'EGLD', 'ARB', 'DYDX', 'APEX', 'CRV', 'ATOM', 'POL', 'OP', 'SEI']
    params = {"symbol": ",".join(symbols), "convert": "USD"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                current_data = {
                    "timestamp": datetime.now().isoformat(),
                    "prices": {
                        symbol: round(data["data"][symbol]["quote"]["USD"]["price"], precision.get(symbol, 2))
                        for symbol in symbols if symbol in data["data"]
                    }
                }
                print("Данные по криптовалютам получены успешно.")
                return current_data
            else:
                print("Ошибка при получении данных:", response.status, await response.text())
                return None

async def update_crypto_data():
    all_data = load_json(DATA_FILE)
    new_data = await fetch_crypto_data()

    if new_data:
        timestamp = datetime.now().isoformat()
        all_data["current"] = new_data
        all_data["history"] = all_data.get("history", {})
        all_data["history"][timestamp] = new_data

        # Оставляем только последние 24 часа данных
        one_day_ago = datetime.now() - timedelta(hours=24)
        all_data["history"] = {ts: data for ts, data in all_data["history"].items() if
                               datetime.fromisoformat(ts) > one_day_ago}

        save_json(DATA_FILE, all_data)
        print("Данные обновлены и сохранены.")
    else:
        print("Не удалось обновить данные.")

# Команда /crypto для отправки текущих данных
async def get_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Команда /crypto вызвана.")
    all_data = load_json(DATA_FILE).get("current", {})
    if not all_data:
        print("Данные не найдены, выполняется обновление...")
        await update_crypto_data()
        all_data = load_json(DATA_FILE).get("current", {})

    message = format_crypto_data({"current": all_data}, "на текущий момент")
    await update.message.reply_text(message)

# Команда /history для данных за последние 12 и 24 часа
async def get_crypto_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Команда /history вызвана.")
    all_data = load_json(DATA_FILE).get("history", {})
    twelve_hours_ago = datetime.now() - timedelta(hours=12)
    twenty_four_hours_ago = datetime.now() - timedelta(hours=24)

    recent_data_12h = {ts: data for ts, data in all_data.items() if datetime.fromisoformat(ts) > twelve_hours_ago}
    recent_data_24h = {ts: data for ts, data in all_data.items() if datetime.fromisoformat(ts) > twenty_four_hours_ago}

    message_12h = format_crypto_data(recent_data_12h, "за последние 12 часов")
    message_24h = format_crypto_data(recent_data_24h, "за последние 24 часа")

    await update.message.reply_text(message_12h)
    await update.message.reply_text(message_24h)

# Команда /user_count для получения информации о пользователях
async def user_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Команда /user_count вызвана.")
    users = load_json(USERS_FILE)
    user_count = len(users)
    user_list = [f"{user['first_name']} (@{user['username']})" for user in users.values()]
    message = f"👥 Всего пользователей: {user_count}\n" + "\n".join(user_list)
    await update.message.reply_text(message)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    first_name = update.effective_chat.first_name
    username = update.effective_chat.username
    await update.message.reply_text("🤑 Вы подписались на рассылку (в 9:00 и 19:00) цен на криптовалюты. "
                                    "Введите /crypto для получения текущей информации, и /history для данных за "
                                    "последние 12 и 24 часа.")
    add_user(chat_id, first_name=first_name, username=username)

# Добавление пользователя
def add_user(chat_id, first_name=None, username=None):
    users = load_json(USERS_FILE)
    if chat_id not in users:
        users[chat_id] = {
            "first_name": first_name,
            "username": username,
            "blocked": False
        }
        save_json(USERS_FILE, users)
        print(f"Пользователь {first_name} добавлен.")
    else:
        print(f"Пользователь {first_name} уже существует.")

# Создание и запуск приложения Telegram
bot_app = Application.builder().token(TG_BOT_TOKEN).build()

@app.route('/webhook', methods=['POST'])
async def webhook():
    data = request.get_json()
    if data:
        update = Update.de_json(data, bot_app.bot)
        await bot_app.update_queue.put(update)
    return "ok", 200

async def main():
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("crypto", get_crypto))
    bot_app.add_handler(CommandHandler("history", get_crypto_history))
    bot_app.add_handler(CommandHandler("user_count", user_count))

    await bot_app.initialize()
    await bot_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    await bot_app.start()

async def run_flask():
    config = Config()
    config.bind = ["0.0.0.0:8443"]
    await serve(app, config)

if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.run(asyncio.gather(main(), run_flask()))
