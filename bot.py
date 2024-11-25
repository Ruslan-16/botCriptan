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

# ID администратора
ADMIN_USER_ID = 413537120  # Укажите ваш Telegram ID (без кавычек, как целое число)

# Настройка точности для криптовалют
precision = {
    "BTC": 2, "ETH": 2, "ADA": 3, "PEPE": 6, "SOL": 2, "SUI": 2, 'TON': 2, 'FET': 3,
    'APT': 3, 'AVAX': 2, 'FLOKI': 6, 'TWT': 3, 'ALGO': 3, 'CAKE': 2, '1INCH': 3,
    'MANA': 3, 'FLOW': 3, 'EGLD': 2, 'ARB': 3, 'DYDX': 2, 'APEX': 3, 'CRV': 3,
    'ATOM': 2, 'POL': 3, 'OP': 2, 'SEI': 3,'WEN': 6
}


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
    except Exception as e:
        print(f"Ошибка при загрузке файла {filename}: {e}")
        return {}


def save_json(filename, data):
    """Сохраняет данные в файл JSON."""
    try:
        with open(filename, "w") as f:
            json.dump(data, f)
    except IOError as e:
        print(f"Ошибка записи файла {filename}: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветственное сообщение."""
    chat_id = update.effective_chat.id
    first_name = update.effective_chat.first_name
    username = update.effective_chat.username

    # Кнопка "Узнать цены" всегда показывается
    keyboard = [
        [InlineKeyboardButton("🤑 Узнать цены", callback_data="explain_cripto")],
    ]
    # Кнопка "Пользователи" только для админа
    if chat_id == ADMIN_USER_ID:
        keyboard.append([InlineKeyboardButton("👥 Пользователи", callback_data="show_users")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"👋 Привет, {first_name}! Я помогу тебе отслеживать цены криптовалют.",
        reply_markup=reply_markup,
    )
    add_user(chat_id, first_name=first_name, username=username)


def add_user(chat_id, first_name=None, username=None):
    """Добавляет пользователя в файл."""
    users = load_json(USERS_FILE)

    # Добавляем отладочное сообщение
    print(f"Пытаемся добавить пользователя: {first_name} @{username}")

    if chat_id not in users:
        users[chat_id] = {"first_name": first_name, "username": username, "blocked": False}
        save_json(USERS_FILE, users)
        print(f"Новый пользователь добавлен: {first_name} @{username}")


async def show_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список всех пользователей (только для админа)."""
    chat_id = update.effective_chat.id

    # Проверяем, что это админ
    if chat_id != ADMIN_USER_ID:
        await update.message.reply_text("🚫 У вас нет прав для этого действия.")
        return

    # Загружаем пользователей
    users = load_json(USERS_FILE)

    # Добавляем отладочные сообщения
    print(f"Загруженные пользователи: {users}")

    if not users:
        message = "🚫 Нет зарегистрированных пользователей."
        print("Пользователи не найдены.")
    else:
        message = "Список пользователей:\n"
        for user_id, user_info in users.items():
            message += f"👤 {user_info['first_name']} @{user_info.get('username', 'Без имени')}\n"
        print(f"Список пользователей: {message}")

    # Проверка, откуда пришел запрос
    if update.message:
        # Это сообщение, на которое можно ответить
        await update.message.reply_text(message)
    elif update.callback_query:
        # Это callback запрос от кнопки
        await update.callback_query.message.reply_text(message)


async def explain_cripto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обновляет данные криптовалют и отправляет новое сообщение."""
    query = update.callback_query
    await query.answer()

    # Получаем актуальные данные и форматируем их
    current_data = await fetch_crypto_data()
    if not current_data:
        message = "🚫 Не удалось получить данные о криптовалюте в данный момент."
    else:
        message = format_crypto_data({current_data["timestamp"]: current_data}, "на текущий момент")

    # Клавиатура с кнопкой обновления
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить данные", callback_data="explain_cripto")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем новое сообщение вместо редактирования
    await query.message.reply_text(message, reply_markup=reply_markup)


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


@app.route('/webhook', methods=['POST'])
async def webhook():
    """Обрабатывает вебхук Telegram."""
    data = request.get_json()
    if data:
        update = Update.de_json(data, bot_app.bot)
        await bot_app.update_queue.put(update)
    return "ok", 200


async def main():
    """Запускает бота и настраивает вебхук."""
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(explain_cripto, pattern="^explain_cripto$"))
    bot_app.add_handler(CallbackQueryHandler(show_users, pattern="^show_users$"))

    await bot_app.initialize()
    await bot_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    await bot_app.start()


async def run_flask():
    """Запускает Flask через Hypercorn."""
    config = Config()
    config.bind = ["0.0.0.0:8443"]
    await serve(app, config)


# Создаем экземпляр бота
bot_app = Application.builder().token(TG_BOT_TOKEN).build()

if __name__ == "__main__":
    asyncio.run(asyncio.gather(main(), run_flask()))
