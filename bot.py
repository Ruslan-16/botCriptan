import os
import json
import requests
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update
from flask import Flask, request
import asyncio
from hypercorn.asyncio import serve
from hypercorn.config import Config

# Переменные окружения
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
CMC_API_KEY = os.getenv("CMC_API_KEY")
WEBHOOK_URL = "https://your_server_ip_or_domain/webhook"
WEBHOOK_PATH = "/webhook"
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = 8444

# Инициализация бота и диспетчера
bot = Bot(token=TG_BOT_TOKEN)
dp = Dispatcher(bot)

# Flask-приложение для вебхуков
app = Flask(__name__)

# Загрузка и сохранение пользователей
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

# Получение данных о криптовалютах
def get_crypto_data():
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    headers = {"Accepts": "application/json", "X-CMC_PRO_API_KEY": CMC_API_KEY}
    symbols = ["BTC", "ETH", "ADA", "PEPE", "SOL", "SUI", 'TON', 'FET', 'APT', 'AVAX', 'FLOKI', 'TWT', 'ALGO',
               'CAKE', '1INCH', 'MANA', 'FLOW', 'EGLD', 'ARB', 'DYDX', 'APEX', 'CRV', 'ATOM', 'POL', 'OP', 'SEI']
    params = {"symbol": ",".join(symbols), "convert": "USD"}
    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()["data"]
        message = f"🗓️ 🏦 Актуальные данные на {datetime.now().strftime('%d-%m-%Y')}:\n"
        for symbol in symbols:
            if symbol in data:
                price = data[symbol]["quote"]["USD"]["price"]
                message += f"💰{symbol}: 💲{price:.5f}\n"
        return message
    else:
        return f"Error fetching data: {response.status_code}"

# Функция для рассылки обновлений
async def send_crypto_update():
    message = get_crypto_data()
    if not message:
        print("Ошибка при получении данных о криптовалюте")
        return
    users = load_users()
    for chat_id in users:
        try:
            await bot.send_message(chat_id=chat_id, text=message)
        except Exception as e:
            print(f"Ошибка отправки для {chat_id}: {e}")
            if "bot was blocked" in str(e) or "user is deactivated" in str(e):
                users.remove(chat_id)
                save_users(users)

# Команда /start
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    chat_id = message.chat.id
    await message.reply("🤑 Вы подписались на ежедневную рассылку цен на Криптовалюты в 🕰️ 9:00 и 19:00.👍")
    add_user(chat_id)

# Webhook обработ
