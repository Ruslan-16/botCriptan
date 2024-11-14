import os
import json
import aiohttp
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, ChatMemberHandler
import nest_asyncio
import asyncio
from flask import Flask, request
from hypercorn.asyncio import serve
from hypercorn.config import Config

# Применяем patch для поддержки asyncio
nest_asyncio.apply()

# Загружаем переменные среды
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
CMC_API_KEY = os.getenv("CMC_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not TG_BOT_TOKEN or not CMC_API_KEY or not WEBHOOK_URL:
    raise EnvironmentError("Не заданы обязательные переменные среды: TG_BOT_TOKEN, CMC_API_KEY или WEBHOOK_URL")

# Инициализация Flask
app = Flask(__name__)

# Файлы данных
USERS_FILE = "users.json"
DATA_FILE = "crypto_data.json"

# Настройка точности для криптовалют
precision = {
    "BTC": 2, "ETH": 2, "ADA": 3, "PEPE": 6, "SOL": 2, "SUI": 2, 'TON': 2, 'FET': 3,
    'APT': 3, 'AVAX': 2, 'FLOKI': 6, 'TWT': 3, 'ALGO': 3, 'CAKE': 2, '1INCH': 3,
    'MANA': 3, 'FLOW': 3, 'EGLD': 2, 'ARB': 3, 'DYDX': 2, 'APEX': 3, 'CRV': 3,
    'ATOM': 2, 'POL': 3, 'OP': 2, 'SEI': 3
}

# Идентификатор администратора (замените на свой Telegram ID)
ADMIN_USER_ID = 413537120

# Функция для добавления пользователя с именем
def add_user(chat_id, first_name=None, username=None):
    """Добавляет пользователя в файл."""
    users = load_json(USERS_FILE)
    if chat_id not in users:
        users[chat_id] = {"first_name": first_name, "username": username, "blocked": False}
        save_json(USERS_FILE, users)

# Функция для загрузки данных из JSON файла
def load_json(filename):
    """Загружает данные из файла JSON."""
    try:
        if os.path.exists(filename):
            with open(filename, "r") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        return {}
    except json.JSONDecodeError:
        print(f"Ошибка чтения файла {filename}. Возможно, файл поврежден.")
        return {}

# Функция для сохранения данных в JSON файл
def save_json(filename, data):
    """Сохраняет данные в файл JSON."""
    try:
        with open(filename, "w") as f:
            json.dump(data, f)
    except IOError as e:
        print(f"Ошибка записи файла {filename}: {e}")

# Форматирование данных криптовалют для вывода
def format_crypto_data(data, period):
    """Форматирует данные криптовалют для вывода."""
    if not data:
        return f"Данных {period} нет."

    message = f"🕒 Данные о криптовалютах {period}:\n"
    for ts, prices in data.items():
        formatted_time = datetime.fromisoformat(ts).strftime('%d.%m.%Y %H:%M:%S')
        message += f"\n⏱️ Время: {formatted_time}\n"
        for symbol, price in prices["prices"].items():
            decimals = precision.get(symbol, 2)
            message += f"💰 {symbol}: ${price:.{decimals}f}\n"
        break  # Выводим только одно обновление
    return message

# Функция для получения актуальных данных криптовалют
async def fetch_crypto_data():
    """Получает актуальные данные криптовалют из API CoinMarketCap."""
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

# Функция для подсчета пользователей с кнопкой и пояснением
async def count_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выводит количество пользователей с пояснением."""
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("🚫 У вас нет прав для просмотра списка пользователей.")
        return

    users = load_json(USERS_FILE)
    user_count = len(users)  # Количество пользователей
    keyboard = [
        [InlineKeyboardButton("ℹ️ Пояснение", callback_data="explain_users")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(f"Всего пользователей: {user_count}", reply_markup=reply_markup)

# Функция для объяснения кнопки пояснения
async def explain_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Объяснение для кнопки пояснения о пользователях."""
    query = update.callback_query
    await query.answer()

    message = "📊 Эта команда отображает количество пользователей, которые подписались на бота. Только администратор может просматривать этот список."

    # Отправляем сообщение с пояснением
    await query.message.reply_text(message)

# Хендлер для удаления пользователя, если он удаляет бота
async def on_user_left(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаляет пользователя, если он удаляет бота."""
    if update.chat_member:
        chat_member = update.chat_member
        if chat_member.status == "left":
            chat_id = chat_member.user.id
            users = load_json(USERS_FILE)
            if chat_id in users:
                del users[chat_id]
                save_json(USERS_FILE, users)
                print(f"Пользователь {chat_id} удален из списка, так как покинул чат.")

# Инициализация бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветственное сообщение."""
    chat_id = update.effective_chat.id
    first_name = update.effective_chat.first_name
    username = update.effective_chat.username

    keyboard = [[InlineKeyboardButton("🤑 Узнать цены", callback_data="explain_cripto")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"👋 Привет, {first_name}! Я помогу тебе отслеживать цены криптовалют.",
        reply_markup=reply_markup,
    )
    add_user(chat_id, first_name=first_name, username=username)

# Инициализация Flask
@app.route('/webhook', methods=['POST'])
async def webhook():
    """Обрабатывает вебхук Telegram."""
    data = request.get_json()
    if data:
        update = Update.de_json(data, bot_app.bot)
        await bot_app.update_queue.put(update)
    return "ok", 200

# Запуск Flask через Hypercorn
async def run_flask():
    """Запускает Flask через Hypercorn."""
    config = Config()
    config.bind = ["0.0.0.0:8443"]
    await serve(app, config)

# Запуск бота и настройка вебхуков
async def main():
    """Запускает бота и настраивает вебхук."""
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("count_users", count_users))
    bot_app.add_handler(CallbackQueryHandler(explain_users, pattern="^explain_users$"))
    bot_app.add_handler(ChatMemberHandler(on_user_left, chat_member_types=["left"]))

    await bot_app.initialize()
    await bot_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    await bot_app.start()

# Создаем экземпляр бота
bot_app = Application.builder().token(TG_BOT_TOKEN).build()

if __name__ == "__main__":
    asyncio.run(asyncio.gather(main(), run_flask()))
