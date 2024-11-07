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

# Применяем поддержку асинхронности в Flask
nest_asyncio.apply()

# Инициализация Flask
app = Flask(__name__)

# Переменные окружения
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


# Функции для работы с файлами
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    return {}


def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f)


# Функции для работы с пользователями
def add_user(chat_id, first_name=None, username=None):
    users = load_json(USERS_FILE)
    if chat_id not in users:
        users[chat_id] = {
            "first_name": first_name,
            "username": username,
            "blocked": False
        }
        save_json(USERS_FILE, users)


def remove_user(chat_id):
    users = load_json(USERS_FILE)
    if chat_id in users:
        del users[chat_id]
        save_json(USERS_FILE, users)


def get_user_count():
    users = load_json(USERS_FILE)
    return len(users)


# Функция для получения списка пользователей
def get_user_list():
    users = load_json(USERS_FILE)
    user_list = []
    for user in users.values():
        name = user.get("first_name", "Unknown")
        username = f"@{user['username']}" if user.get("username") else ""
        user_list.append(f"{name} {username}".strip())
    return user_list


# Функции для работы с крипто-данными
def fetch_crypto_data():
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    headers = {"Accepts": "application/json", "X-CMC_PRO_API_KEY": CMC_API_KEY}
    symbols = ["BTC", "ETH", "ADA", "PEPE", "SOL", "SUI", 'TON', 'FET', 'APT', 'AVAX', 'FLOKI', 'TWT', 'ALGO',
               'CAKE', '1INCH', 'MANA', 'FLOW', 'EGLD', 'ARB', 'DYDX', 'APEX', 'CRV', 'ATOM', 'POL', 'OP', 'SEI']
    params = {"symbol": ",".join(symbols), "convert": "USD"}

    # Запрос данных с CoinMarketCap
    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()["data"]
        current_data = {
            "timestamp": datetime.now().isoformat(),
            # Применяем нужное количество знаков после запятой для каждого символа
            "prices": {
                symbol: round(data[symbol]["quote"]["USD"]["price"], precision.get(symbol, 2))
                for symbol in symbols if symbol in data
            }
        }
        return current_data
    else:
        return None


def update_crypto_data():
    # Загружаем данные
    all_data = load_json(DATA_FILE)
    new_data = fetch_crypto_data()

    if new_data:
        # Добавляем данные за текущий момент
        timestamp = datetime.now().isoformat()
        all_data["current"] = new_data
        all_data["history"] = all_data.get("history", {})
        all_data["history"][timestamp] = new_data

        # Оставляем только последние 24 часа данных
        one_day_ago = datetime.now() - timedelta(hours=24)
        all_data["history"] = {ts: data for ts, data in all_data["history"].items() if
                               datetime.fromisoformat(ts) > one_day_ago}

        # Сохраняем обновлённые данные
        save_json(DATA_FILE, all_data)


# Функция для отправки данных пользователям по расписанию
async def send_crypto_update(context: ContextTypes.DEFAULT_TYPE):
    all_data = load_json(DATA_FILE).get("current", {})
    if not all_data:
        await update_crypto_data()  # Если данных нет, обновим их
        all_data = load_json(DATA_FILE).get("current", {})

    message = format_crypto_data({"current": all_data}, "на текущий момент")
    users = load_json(USERS_FILE)

    for chat_id in list(users.keys()):
        try:
            await context.bot.send_message(chat_id=chat_id, text=message)
        except Exception as e:
            print(f"Ошибка отправки для {chat_id}: {e}")
            # Удаляем пользователя, если бот был заблокирован или пользователь деактивирован
            if "bot was blocked" in str(e) or "user is deactivated" in str(e):
                remove_user(chat_id)


# Команда для запроса данных за последние 12 и 24 часа
async def get_crypto_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем данные за последние 12 часов
    all_data = load_json(DATA_FILE).get("history", {})
    twelve_hours_ago = datetime.now() - timedelta(hours=12)
    recent_data_12h = {ts: data for ts, data in all_data.items() if datetime.fromisoformat(ts) > twelve_hours_ago}

    # Получаем данные за последние 24 часа
    twenty_four_hours_ago = datetime.now() - timedelta(hours=24)
    recent_data_24h = {ts: data for ts, data in all_data.items() if datetime.fromisoformat(ts) > twenty_four_hours_ago}

    # Формируем сообщения
    message_12h = format_crypto_data(recent_data_12h, "за последние 12 часов")
    message_24h = format_crypto_data(recent_data_24h, "за последние 24 часа")

    # Отправляем оба сообщения
    await update.message.reply_text(message_12h)
    await update.message.reply_text(message_24h)


# Функция форматирования данных
def format_crypto_data(data, period):
    if not data:
        return f"Данных {period} нет."
    message = f"🕒 Данные о криптовалютах {period}:\n"
    for ts, prices in data.items():
        message += f"\n⏱️ Время: {ts}\n"
        for symbol, price in prices["prices"].items():
            # Применяем нужное количество знаков после запятой
            decimals = precision.get(symbol, 2)
            message += f"💰 {symbol}: ${price:.{decimals}f}\n"
    return message


# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    first_name = update.effective_chat.first_name
    username = update.effective_chat.username
    await update.message.reply_text("🤑 Вы подписались на рассылку (в 9:00 и 19:00) цен на криптовалюты. "
                                    "Введите /crypto для получения текущей информации, и /history для данных за "
                                    "последние 12 и 24 часа.")
    add_user(chat_id, first_name=first_name, username=username)


# Команда для получения количества пользователей и списка
async def user_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_count = get_user_count()
    user_list = get_user_list()
    message = f"👥 Всего подписчиков: {user_count}\n" + "\n".join(user_list)
    await update.message.reply_text(message)


# Создание бота
bot_app = Application.builder().token(TG_BOT_TOKEN).build()


# Вебхук Telegram
@app.route('/webhook', methods=['POST'])
async def webhook():
    data = request.get_json()
    update = Update.de_json(data, bot_app.bot)
    await bot_app.update_queue.put(update)
    return "ok", 200


# Основная функция инициализации
async def main():
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("crypto", get_crypto_history))
    bot_app.add_handler(CommandHandler("history", get_crypto_history))
    bot_app.add_handler(CommandHandler("user_count", user_count))

    # Регулярное обновление данных
    job_queue = bot_app.job_queue
    job_queue.run_repeating(lambda _: update_crypto_data(), interval=3600)

    # Отправка данных пользователям по расписанию (9:00 и 19:00)
    job_queue.run_daily(send_crypto_update, time(hour=9, minute=0))
    job_queue.run_daily(send_crypto_update, time(hour=19, minute=0))

    # Настройка вебхука и запуск бота
    await bot_app.initialize()
    await bot_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    await bot_app.start()


# Запуск Flask и бота с Hypercorn
async def run_flask():
    config = Config()
    config.bind = ["0.0.0.0:10000"]
    await serve(app, config)


# Запуск приложения
if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.run(asyncio.gather(main(), run_flask()))
