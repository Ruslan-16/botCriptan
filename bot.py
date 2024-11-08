import os
import json
import aiohttp
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
import nest_asyncio
import asyncio
from flask import Flask, request
from hypercorn.asyncio import serve
from hypercorn.config import Config

nest_asyncio.apply()

app = Flask(__name__)

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "7602913247:AAFFy0De4_DSBg_c0V_wiK1TECMtAgMZJA8")
CMC_API_KEY = os.getenv("CMC_API_KEY", "c923b3dc-cd07-4216-8edc-9d73beb665cc")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://ruslan-16-botcriptan-dd61.twc1.net/webhook")

USERS_FILE = "users.json"
DATA_FILE = "crypto_data.json"

precision = {
    "BTC": 2, "ETH": 2, "ADA": 3, "PEPE": 6, "SOL": 2, "SUI": 2, 'TON': 2, 'FET': 3,
    'APT': 3, 'AVAX': 2, 'FLOKI': 6, 'TWT': 3, 'ALGO': 3, 'CAKE': 2, '1INCH': 3,
    'MANA': 3, 'FLOW': 3, 'EGLD': 2, 'ARB': 3, 'DYDX': 2, 'APEX': 3, 'CRV': 3,
    'ATOM': 2, 'POL': 3, 'OP': 2, 'SEI': 3
}


def format_crypto_data(data, period):
    if not data:
        return f"Данных {period} нет."

    message = f"🕒 Данные о криптовалютах {period}:\n"
    for ts, prices in sorted(data.items(), reverse=True):  # Сортируем и удаляем дубликаты
        formatted_time = datetime.fromisoformat(ts).strftime('%d.%m.%Y %H:%M:%S')
        message += f"\n⏱️ Время: {formatted_time}\n"
        for symbol, price in prices["prices"].items():
            decimals = precision.get(symbol, 2)
            message += f"💰 {symbol}: ${price:.{decimals}f}\n"
        break  # Ограничим вывод только последним обновлением

    return message


def load_json(filename):
    try:
        if os.path.exists(filename):
            with open(filename, "r") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
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


async def fetch_crypto_data():
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    headers = {"Accepts": "application/json", "X-CMC_PRO_API_KEY": CMC_API_KEY}
    symbols = list(precision.keys())
    params = {"symbol": ",".join(symbols), "convert": "USD"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
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
    new_data = await fetch_crypto_data()

    if new_data:
        timestamp = datetime.now().isoformat()
        all_data["history"] = {timestamp: new_data}
        save_json(DATA_FILE, all_data)
    else:
        print("Не удалось обновить данные криптовалют.")


async def get_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update_crypto_data()
    all_data = load_json(DATA_FILE).get("history", {})

    if not all_data:
        message = "🚫 Не удалось получить данные о криптовалюте в данный момент."
    else:
        message = format_crypto_data(all_data, "на текущий момент")
    await update.message.reply_text(message)


async def get_crypto_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    all_data = load_json(DATA_FILE).get("history", {})
    twelve_hours_ago = datetime.now() - timedelta(hours=12)
    twenty_four_hours_ago = datetime.now() - timedelta(hours=24)

    recent_data_12h = {ts: data for ts, data in all_data.items() if datetime.fromisoformat(ts) > twelve_hours_ago}
    recent_data_24h = {ts: data for ts, data in all_data.items() if datetime.fromisoformat(ts) > twenty_four_hours_ago}

    message_12h = format_crypto_data(recent_data_12h, "за последние 12 часов")
    message_24h = format_crypto_data(recent_data_24h, "за последние 24 часа")

    await update.message.reply_text(message_12h)
    await update.message.reply_text(message_24h)


async def user_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = load_json(USERS_FILE)
    if not isinstance(users, dict):
        message = "🚫 Ошибка: файл данных пользователей имеет неверный формат."
    elif not users:
        message = "👥 В настоящее время нет зарегистрированных пользователей."
    else:
        user_count = len(users)
        message = f"👥 Всего пользователей: {user_count}"
    await update.message.reply_text(message)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    first_name = update.effective_chat.first_name
    username = update.effective_chat.username

    keyboard = [[InlineKeyboardButton("/cripto", callback_data="/cripto"),
                 InlineKeyboardButton("/history", callback_data="/history")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"👋 Привет, {first_name}! Я помогу тебе отслеживать цены криптовалют.\n"
        "📌 Команды:\n"
        " - /cripto — узнать текущие цены\n"
        " - /history — получить данные за последние 12 и 24 часа\n"
        " - /user_count — узнать количество подписанных пользователей",
        reply_markup=reply_markup
    )

    add_user(chat_id, first_name=first_name, username=username)


def add_user(chat_id, first_name=None, username=None):
    users = load_json(USERS_FILE)
    if chat_id not in users:
        users[chat_id] = {"first_name": first_name, "username": username, "blocked": False}
        save_json(USERS_FILE, users)


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
    bot_app.add_handler(CommandHandler("cripto", get_crypto))
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
