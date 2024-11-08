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


def save_json(filename, data):
    """Сохраняет данные в файл JSON."""
    try:
        with open(filename, "w") as f:
            json.dump(data, f)
    except IOError as e:
        print(f"Ошибка записи файла {filename}: {e}")


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


async def update_history_loop():
    """Фоновое задание для регулярного обновления истории."""
    while True:
        try:
            await update_history()
        except Exception as e:
            print(f"Ошибка при обновлении истории: {e}")
        await asyncio.sleep(3600)  # Ждем 1 час перед следующим обновлением


async def update_history():
    """Обновляет историю данных криптовалют."""
    all_data = load_json(DATA_FILE)
    history = all_data.get("history", [])

    # Получение новых данных
    new_data = await fetch_crypto_data()
    if new_data:
        timestamp = datetime.now().isoformat()

        # Добавляем новую запись и ограничиваем длину истории до 24 записей
        history.append({"timestamp": timestamp, "prices": new_data["prices"]})
        if len(history) > 24:
            history.pop(0)

        # Сохраняем обновленную историю
        all_data["history"] = history
        save_json(DATA_FILE, all_data)
        print("История обновлена:", history)
    else:
        print("Не удалось обновить данные криптовалют.")


async def get_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возвращает актуальные данные криптовалют."""
    current_data = await fetch_crypto_data()
    if not current_data:
        message = "🚫 Не удалось получить данные о криптовалюте в данный момент."
    else:
        message = format_crypto_data({current_data["timestamp"]: current_data}, "на текущий момент")
    await update.message.reply_text(message)


async def get_crypto_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возвращает данные о криптовалютах за последние 12 и 24 часа из истории."""
    all_data = load_json(DATA_FILE)
    history = all_data.get("history", [])
    if not history:
        await update.message.reply_text("🚫 История данных отсутствует.")
        return

    now = datetime.now()
    twelve_hours_ago = now - timedelta(hours=12)
    twenty_four_hours_ago = now - timedelta(hours=24)

    # Ищем записи в истории
    twelve_hour_data = next((entry for entry in history if
                             datetime.fromisoformat(entry["timestamp"]) <= twelve_hours_ago), None)
    twenty_four_hour_data = next((entry for entry in history if
                                  datetime.fromisoformat(entry["timestamp"]) <= twenty_four_hours_ago), None)

    # Формируем ответы
    message_12h = format_crypto_data({twelve_hour_data["timestamp"] if twelve_hour_data else "": twelve_hour_data}
                                     if twelve_hour_data else {}, "за последние 12 часов")
    message_24h = format_crypto_data({twenty_four_hour_data["timestamp"] if twenty_four_hour_data else "":
                                       twenty_four_hour_data} if twenty_four_hour_data else {}, "за последние 24 часа")

    await update.message.reply_text(message_12h)
    await update.message.reply_text(message_24h)


async def user_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возвращает количество пользователей, их имена и удаляет недоступных."""
    users = load_json(USERS_FILE)
    if not isinstance(users, dict):
        message = "🚫 Ошибка: файл данных пользователей имеет неверный формат."
    elif not users:
        message = "👥 В настоящее время нет зарегистрированных пользователей."
    else:
        accessible_users = {}
        user_list = []
        for chat_id, user_info in users.items():
            try:
                # Проверяем доступность чата
                chat = await context.bot.get_chat(chat_id)
                first_name = user_info.get("first_name", "Неизвестно")
                username = user_info.get("username", "нет_логина")
                user_list.append(f" - {first_name} (@{username})")
                accessible_users[chat_id] = user_info  # Пользователь доступен
            except Exception as e:
                print(f"Пользователь {chat_id} удален: {e}")

        # Обновляем файл пользователей
        save_json(USERS_FILE, accessible_users)

        # Формируем сообщение
        user_count = len(accessible_users)
        message = f"👥 Всего пользователей: {user_count}\n" + "\n".join(user_list)

    await update.message.reply_text(message)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветственное сообщение с клавиатурой."""
    chat_id = update.effective_chat.id
    first_name = update.effective_chat.first_name
    username = update.effective_chat.username

    # Клавиатура с кнопками
    keyboard = [[InlineKeyboardButton("Узнать цены", callback_data="/cripto"),
                 InlineKeyboardButton("История", callback_data="/history")]]
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
    """Добавляет пользователя в файл."""
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
    asyncio.run(asyncio.gather(main(), run_flask(), update_history_loop()))
