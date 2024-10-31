import os
import json
import requests
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update
from flask import Flask, request
import asyncio

# Переменные окружения
TG_BOT_TOKEN = "7602913247:AAFFy0De4_DSBg_c0V_wiK1TECMtAgMZJA8"
CMC_API_KEY = "c923b3dc-cd07-4216-8edc-9d73beb665cc"
WEBHOOK_URL = "https://213.226.112.83/webhook"
WEBHOOK_PATH = "/webhook"
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = 8443

# Инициализация бота и диспетчера
bot = Bot(token=TG_BOT_TOKEN)
dp = Dispatcher(bot)

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

# Webhook обработчик Flask
app = Flask(__name__)

@app.route(WEBHOOK_PATH, methods=['POST'])
async def webhook():
    data = await request.get_json()
    update = Update.to_object(data)
    await dp.process_update(update)
    return "ok", 200

# Планировщик задач
async def schedule_updates():
    while True:
        now = datetime.now()
        next_run_time = now.replace(hour=9, minute=0, second=0, microsecond=0) if now.hour < 9 else now.replace(hour=19, minute=0, second=0, microsecond=0)
        if next_run_time <= now:
            next_run_time += timedelta(days=1) if now.hour >= 19 else timedelta(hours=10)
        sleep_duration = (next_run_time - now).total_seconds()
        await asyncio.sleep(sleep_duration)
        await send_crypto_update()

# Запуск вебхука и расписания
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    asyncio.create_task(schedule_updates())

async def on_shutdown():
    await bot.delete_webhook()
    await bot.session.close()

# Основной запуск приложения
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(on_startup())

    try:
        app.run(host=WEBAPP_HOST, port=WEBAPP_PORT, ssl_context=('path/to/your/cert.pem', 'path/to/your/key.pem'))
    except KeyboardInterrupt:
        print("Бот остановлен")
    finally:
        loop.run_until_complete(on_shutdown())
