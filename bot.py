import os
import json
import requests
from datetime import datetime, time
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes,MessageHandler, filters
import nest_asyncio
import asyncio
from flask import Flask, request
from hypercorn.asyncio import serve
from hypercorn.config import Config
from datetime import timedelta
# Инициализация Flask
app = Flask(__name__)
nest_asyncio.apply()

# Переменные окружения
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
CMC_API_KEY = os.getenv("CMC_API_KEY")
WEBHOOK_URL = "https://botcriptan.onrender.com"  # URL на Render


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

def get_user_count():
    users = load_users()  # Загрузка списка chat_id
    return len(users)  # Возвращает количество chat_id в списке


# Получение данных о криптовалютах
def get_crypto_data():
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    headers = {"Accepts": "application/json", "X-CMC_PRO_API_KEY": CMC_API_KEY}
    symbols = ["BTC", "ETH", "ADA", "PEPE", "SOL", "SUI", "TON", "FET", "APT", "AVAX", "FLOKI", "TWT",
               "ALGO", "CAKE", "1INCH", "MANA", "FLOW", "EGLD", "ARB", "DYDX", "APEX", "CRV", "ATOM", "POL", "OP",
               "SEI"]
    params = {"symbol": ",".join(symbols), "convert": "USD"}

    # Словарь с эмодзи для каждой криптовалюты
    crypto_emojis = {
        "BTC": "💰", "ETH": "⚡", "ADA": "🔷", "PEPE": "🐸", "SOL": "🌞", "SUI": "🌊",
        "TON": "📞", "FET": "🤖", "APT": "🚀", "AVAX": "❄️", "FLOKI": "🐶", "TWT": "🔐",
        "ALGO": "🔗", "CAKE": "🍰", "1INCH": "📏", "MANA": "🌐", "FLOW": "💧",
        "EGLD": "👑", "ARB": "🛡️", "DYDX": "⚔️", "APEX": "🌋", "CRV": "💹", "ATOM": "🪐",
        "POL": "🏛️", "OP": "📈", "SEI": "🌾"
    }

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()["data"]
        message = f"🗓️ Актуальные данные на {datetime.now().strftime('%Y-%m-%d')}:\n"
        for symbol in symbols:
            if symbol in data:
                price = data[symbol]["quote"]["USD"]["price"]
                emoji = crypto_emojis.get(symbol, "💸")  # Эмодзи по умолчанию, если не найдено
                message += f"{emoji} {symbol}: ${price:.5f}\n"
        return message
    else:
        return f"Error fetching data: {response.status_code}"


# Отправка обновлений пользователям
async def send_crypto_update(context: ContextTypes.DEFAULT_TYPE):
    print("Запуск send_crypto_update...")  # Проверка запуска задания
    message = get_crypto_data()
    if not message:
        print("Ошибка при получении данных о криптовалюте")
        return
    users = load_users()
    for chat_id in users:
        try:
            await context.bot.send_message(chat_id=chat_id, text=message)
            print(f"Сообщение отправлено пользователю {chat_id}")
        except Exception as e:
            print(f"Ошибка отправки для {chat_id}: {e}")
            if "bot was blocked" in str(e) or "user is deactivated" in str(e):
                users.remove(chat_id)
                save_users(users)


# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text("🤑 Вы подписались на рассылку цен на Криптовалюты , нажмите введите /crypto👍")
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
from datetime import timedelta

# Команда /crypto для запроса обновлений
async def crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = get_crypto_data()
    await update.message.reply_text(message)

# Основная функция инициализации
async def main():
    # Add all handlers here
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("crypto", crypto))
    bot_app.add_handler(CommandHandler("count", count))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Schedule daily update jobs
    job_queue = bot_app.job_queue
    job_queue = bot_app.job_queue
    job_queue.run_daily(send_crypto_update, time(hour=6, minute=0))
    job_queue.run_daily(send_crypto_update, time(hour=9, minute=30))
    job_queue.run_daily(send_crypto_update, time(hour=16, minute=0))

    # Initialize bot and set webhook
    await bot_app.initialize()
    await bot_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    print("Webhook set!")
    await bot_app.start()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Доступные команды: /start для подписки, /crypto для получения данных.")

async def count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_count = get_user_count()
    await update.message.reply_text(f"В боте {user_count} подписчиковс🥹.")


# Запуск Flask и бота с Hypercorn
async def run_flask():
    config = Config()
    config.bind = ["0.0.0.0:10000"]  # Render открывает порт 10000
    await serve(app, config)


# Запуск Flask и бота
if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.run(asyncio.gather(main(), run_flask()))
