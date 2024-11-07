import os
import json
import aiohttp
from datetime import datetime, timedelta, time
from telegram import Update
import nest_asyncio
import asyncio
from flask import Flask, request
from hypercorn.asyncio import serve
from hypercorn.config import Config
from telegram.ext import Application, CommandHandler, ContextTypes

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
        formatted_time = datetime.fromisoformat(ts).strftime('%d.%m.%Y %H:%M:%S')
        message += f"\n⏱️ Время: {formatted_time}\n"
        for symbol, price in prices["prices"].items():
            decimals = precision.get(symbol, 2)
            message += f"💰 {symbol}: ${price:.{decimals}f}\n"

    return message

# Загрузка и сохранение данных в файлах JSON
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

# Асинхронная функция для получения данных криптовалют
async def fetch_crypto_data():
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    headers = {"Accepts": "application/json", "X-CMC_PRO_API_KEY": CMC_API_KEY}
    symbols = list(precision.keys())
    params = {"symbol": ",".join(symbols), "convert": "USD"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                print("Данные от API получены:", data)
                return {
                    "timestamp": datetime.now().isoformat(),
                    "prices": {
                        symbol: round(data["data"][symbol]["quote"]["USD"]["price"], precision[symbol])
                        for symbol in symbols if symbol in data["data"]
                    }
                }
            else:
                print("Ошибка при получении данных:", response.status, await response.text())
                return None

async def update_crypto_data():
    all_data = load_json(DATA_FILE)
    print("Данные перед обновлением:", all_data)

    # Получение новых данных
    new_data = await fetch_crypto_data()
    print("Полученные новые данные от API:", new_data)

    if new_data:
        # Обновляем текущие данные
        all_data["current"] = new_data  # сохраняем текущие данные отдельно
        timestamp = datetime.now().isoformat()

        # Обновляем историю с текущей временной меткой
        all_data["history"] = all_data.get("history", {})
        all_data["history"][timestamp] = new_data

        # Оставляем данные последних 24 часов, исключая ключ 'current'
        one_day_ago = datetime.now() - timedelta(hours=24)
        all_data["history"] = {
            ts: data for ts, data in all_data["history"].items()
            if datetime.fromisoformat(ts) > one_day_ago
        }

        # Сохраняем обновлённые данные в файл
        save_json(DATA_FILE, all_data)
        print("Данные после сохранения:", all_data)
    else:
        print("Не удалось обновить данные криптовалюты.")

# Асинхронный обработчик команды /cripto
async def get_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Команда /cripto вызвана.")
    all_data = load_json(DATA_FILE).get("current", {})
    print("Загруженные данные для 'current' после загрузки из файла:", all_data)

    if not all_data:
        print("Данные не найдены, выполняется обновление...")
        await update_crypto_data()
        all_data = load_json(DATA_FILE).get("current", {})
        print("Данные после обновления и загрузки из файла:", all_data)

    # Формируем сообщение с текущими данными напрямую
    if not all_data:
        message = "🚫 Не удалось получить данные о криптовалюте в данный момент."
    else:
        message = "🕒 Данные о криптовалютах на текущий момент:\n"
        for symbol, price in all_data["prices"].items():
            decimals = precision.get(symbol, 2)
            message += f"💰 {symbol}: ${price:.{decimals}f}\n"

    await update.message.reply_text(message)

# Асинхронный обработчик команды /history
async def get_crypto_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Команда /history вызвана.")
    all_data = load_json(DATA_FILE).get("history", {})
    twelve_hours_ago = datetime.now() - timedelta(hours=12)
    twenty_four_hours_ago = datetime.now() - timedelta(hours=24)

    # Фильтруем временные метки, исключая 'current'
    recent_data_12h = {
        ts: data for ts, data in all_data.items()
        if datetime.fromisoformat(ts) > twelve_hours_ago
    }
    recent_data_24h = {
        ts: data for ts, data in all_data.items()
        if datetime.fromisoformat(ts) > twenty_four_hours_ago
    }

    message_12h = format_crypto_data(recent_data_12h, "за последние 12 часов")
    message_24h = format_crypto_data(recent_data_24h, "за последние 24 часа")

    await update.message.reply_text(message_12h)
    await update.message.reply_text(message_24h)

# Асинхронный обработчик команды /user_count
async def user_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Команда /user_count вызвана.")
    users = load_json(USERS_FILE)
    print("Загруженные пользователи:", users)

    if not isinstance(users, dict):
        message = "🚫 Ошибка: файл данных пользователей имеет неверный формат."
        print("Ошибка: Ожидался словарь, но получен объект типа:", type(users))
    elif not users:
        message = "👥 В настоящее время нет зарегистрированных пользователей."
    else:
        user_count = len(users)
        user_list = [f"{user.get('first_name', 'Неизвестно')} (@{user.get('username', 'нет_логина')})" for user in users.values()]
        message = f"👥 Всего пользователей: {user_count}\n" + "\n".join(user_list)

    await update.message.reply_text(message)

# Асинхронный обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    first_name = update.effective_chat.first_name
    username = update.effective_chat.username
    await update.message.reply_text(
        "👋 Привет! Теперь вы подписаны на рассылку цен криптовалют.\n"
        "🔔 Мы будем присылать актуальные данные дважды в день: в 9:00 и 19:00.\n\n"
        "📌 Команды:\n"
        " - /cripto — узнать текущие цены\n"
        " - /history — получить данные за последние 12 и 24 часа\n\n"
        "💹 Удачного трейдинга и следите за ценами!"
    )
    add_user(chat_id, first_name=first_name, username=username)

# Добавление пользователя в файл
def add_user(chat_id, first_name=None, username=None):
    users = load_json(USERS_FILE)
    if chat_id not in users:
        users[chat_id] = {"first_name": first_name, "username": username, "blocked": False}
        save_json(USERS_FILE, users)
        print(f"Пользователь {first_name} добавлен.")
    else:
        print(f"Пользователь {first_name} уже существует.")

# Функция для отправки крипто-данных всем пользователям по расписанию
async def scheduled_crypto_update(context: ContextTypes.DEFAULT_TYPE):
    print("Рассылка крипто-данных по расписанию.")
    users = load_json(USERS_FILE)
    all_data = load_json(DATA_FILE).get("current", {})

    if not all_data:
        message = "🚫 Не удалось получить данные о криптовалюте в данный момент."
    else:
        message = "🕒 Данные о криптовалютах на текущий момент:\n"
        for symbol, price in all_data["prices"].items():
            decimals = precision.get(symbol, 2)
            message += f"💰 {symbol}: ${price:.{decimals}f}\n"

    for chat_id, user_info in users.items():
        try:
            await context.bot.send_message(chat_id=chat_id, text=message)
            print(f"Сообщение отправлено пользователю {user_info.get('first_name', 'Неизвестно')}")
        except Exception as e:
            print(f"Ошибка при отправке сообщения пользователю {user_info.get('first_name', 'Неизвестно')}: {e}")

# Создание приложения Telegram с JobQueue
bot_app = Application.builder().token(TG_BOT_TOKEN).build()

# Обработка вебхуков
@app.route('/webhook', methods=['POST'])
async def webhook():
    data = request.get_json()
    if data:
        update = Update.de_json(data, bot_app.bot)
        await bot_app.update_queue.put(update)
        print("Получен новый вебхук.")
    return "ok", 200

# Запуск бота Telegram
async def main():
    await bot_app.initialize()

    # Настройка задач для рассылки крипто-данных в 9:00 и 19:00 каждый день
    job_queue = bot_app.job_queue
    if job_queue is None:
        print("Ошибка: job_queue не инициализирован.")
    else:
        job_queue.run_daily(scheduled_crypto_update, time(hour=9, minute=0))
        job_queue.run_daily(scheduled_crypto_update, time(hour=19, minute=0))

    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("cripto", get_crypto))
    bot_app.add_handler(CommandHandler("history", get_crypto_history))
    bot_app.add_handler(CommandHandler("user_count", user_count))

    await bot_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    await bot_app.start()
    print("Бот запущен, вебхук установлен и задачи по расписанию настроены.")

# Запуск Flask
async def run_flask():
    config = Config()
    config.bind = ["0.0.0.0:8443"]
    await serve(app, config)

if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.run(asyncio.gather(main(), run_flask()))
