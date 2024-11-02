import os
import json
import requests
from datetime import datetime, time, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import nest_asyncio
import asyncio
from flask import Flask, request
from hypercorn.asyncio import serve
from hypercorn.config import Config

# Инициализация Flask
app = Flask(__name__)
nest_asyncio.apply()

# Переменные окружения
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
CMC_API_KEY = os.getenv("CMC_API_KEY")
YANDEX_DISK_TOKEN = os.getenv("YANDEX_DISK_TOKEN")
WEBHOOK_URL = "https://botcriptan.onrender.com"  # URL на Render

# URL для работы с Яндекс.Диском
YDB_URL = "https://cloud-api.yandex.net/v1/disk/resources"

# Загрузка и сохранение пользователей на Яндекс.Диске
def upload_to_yandex_disk(local_file_path, remote_file_path):
    """Загружает файл на Яндекс.Диск."""
    upload_url = f"{YDB_URL}/upload?path={remote_file_path}&overwrite=true"
    headers = {'Authorization': f'OAuth {YANDEX_DISK_TOKEN}'}

    response = requests.get(upload_url, headers=headers)
    if response.status_code == 200:
        upload_link = response.json().get("href")
        with open(local_file_path, 'rb') as f:
            upload_response = requests.put(upload_link, files={'file': f})
        return upload_response.status_code == 201
    else:
        print(f"Ошибка получения ссылки для загрузки: {response.status_code}")
        return False

def download_from_yandex_disk(remote_file_path, local_file_path):
    """Скачивает файл с Яндекс.Диска."""
    download_url = f"{YDB_URL}/download?path={remote_file_path}"
    headers = {'Authorization': f'OAuth {YANDEX_DISK_TOKEN}'}

    response = requests.get(download_url, headers=headers)
    if response.status_code == 200:
        download_link = response.json().get("href")
        file_response = requests.get(download_link)
        if file_response.status_code == 200:
            with open(local_file_path, 'wb') as f:
                f.write(file_response.content)
            return True
    print(f"Ошибка при скачивании файла: {response.status_code}")
    return False

def load_users():
    """Загружает список пользователей из файла users.json на Яндекс.Диске."""
    download_from_yandex_disk('users.json', 'users.json')
    if os.path.exists("users.json"):
        with open("users.json", "r") as f:
            return json.load(f)
    return []

def save_users(users):
    """Сохраняет список пользователей в файл users.json на Яндекс.Диске."""
    with open("users.json", "w") as f:
        json.dump(users, f)
    upload_to_yandex_disk('users.json', 'users.json')

def add_user(chat_id):
    users = load_users()
    if chat_id not in users:
        users.append(chat_id)
        save_users(users)

def get_user_count():
    users = load_users()
    return len(users)

# Работа с ценами на криптовалюты
def get_crypto_data():
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    headers = {"Accepts": "application/json", "X-CMC_PRO_API_KEY": CMC_API_KEY}
    symbols = ["BTC", "ETH", "ADA", "SOL", "TON", "APT", "AVAX", "ALGO", "CAKE", "OP"]
    params = {"symbol": ",".join(symbols), "convert": "USD"}
    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()["data"]
        return {symbol: data[symbol]["quote"]["USD"]["price"] for symbol in symbols if symbol in data}
    else:
        print(f"Ошибка получения данных: {response.status_code}")
        return {}

def save_current_prices():
    """Сохраняет текущие цены с отметкой времени для исторических данных."""
    current_prices = get_crypto_data()
    if current_prices:
        prices = load_prices()
        timestamp = datetime.now().isoformat()
        prices[timestamp] = current_prices
        save_prices(prices)
    else:
        print("Не удалось получить текущие данные о ценах.")

def load_prices():
    """Загружает исторические данные о ценах из файла prices.json на Яндекс.Диске."""
    download_from_yandex_disk('prices.json', 'prices.json')
    if os.path.exists("prices.json"):
        with open("prices.json", "r") as f:
            return json.load(f)
    return {}

def save_prices(prices):
    """Сохраняет исторические данные о ценах в файл prices.json на Яндекс.Диске."""
    with open("prices.json", "w") as f:
        json.dump(prices, f)
    upload_to_yandex_disk('prices.json', 'prices.json')

def get_historical_prices(hours_ago):
    """Возвращает цены на определенное количество часов назад."""
    prices = load_prices()
    target_time = datetime.now() - timedelta(hours=hours_ago)
    closest_time = None
    closest_prices = None

    for timestamp, price_data in prices.items():
        time = datetime.fromisoformat(timestamp)
        if closest_time is None or abs((time - target_time).total_seconds()) < abs(
                (closest_time - target_time).total_seconds()):
            closest_time = time
            closest_prices = price_data

    return closest_prices, closest_time

# Команда для показа количества пользователей
async def count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_count = get_user_count()
    await update.message.reply_text(f"В боте {user_count} подписчиков 🥹.")

# Команда для показа цен с историей 12 и 24 часа назад
async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_prices = get_crypto_data()
    prices_12h, time_12h = get_historical_prices(12)
    prices_24h, time_24h = get_historical_prices(24)

    message = f"🗓️ Актуальные данные на {datetime.now().strftime('%d-%m-%Y %H:%M')}:\n"
    for symbol, price in current_prices.items():
        message += f"💰{symbol}: {price:.2f} USD\n"

    if prices_12h and time_12h:
        message += f"\n💰 Цены 12 часов назад ({time_12h.strftime('%d-%m-%Y %H:%M')}):\n"
        for symbol, price in prices_12h.items():
            message += f"{symbol}: {price:.2f} USD\n"

    if prices_24h and time_24h:
        message += f"\n💰 Цены 24 часа назад ({time_24h.strftime('%d-%m-%Y %H:%M')}):\n"
        for symbol, price in prices_24h.items():
            message += f"{symbol}: {price:.2f} USD\n"

    await update.message.reply_text(message)

# Отправка обновлений пользователям
async def send_crypto_update(context: ContextTypes.DEFAULT_TYPE):
    save_current_prices()
    message = get_crypto_data()
    if not message:
        print("Ошибка при получении данных о криптовалюте")
        return
    users = load_users()
    for chat_id in users:
        try:
            await context.bot.send_message(chat_id=chat_id, text=message)
        except Exception as e:
            print(f"Ошибка отправки для {chat_id}: {e}")
            if "bot was blocked" in str(e) or "user is deactivated" in str(e):
                users.remove(chat_id)
                save_users(users)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        "🤑 Вы подписались на рассылку (в 9:00 и 19:00) цен на Криптовалюты. "
        "Нажмите /history для просмотра текущих и исторических цен.")
    add_user(chat_id)

# Создание бота и обработчики команд
bot_app = Application.builder().token(TG_BOT_TOKEN).build()

@app.route('/webhook', methods=['POST'])
async def webhook():
    data = request.get_json()
    try:
        update = Update.de_json(data, bot_app.bot)
        await bot_app.update_queue.put(update)
        return "ok", 200
    except Exception as e:
        print(f"Ошибка обработки вебхука: {e}")
        return "Error", 500

# Основная функция для запуска бота
async def main():
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("history", history))
    bot_app.add_handler(CommandHandler("count", count))  # Регистрация команды /count

    job_queue = bot_app.job_queue
    job_queue.run_daily(send_crypto_update, time(hour=6, minute=0))
    job_queue.run_daily(send_crypto_update, time(hour=16, minute=0))

    await bot_app.initialize()
    await bot_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    await bot_app.start()

async def run_flask():
    config = Config()
    config.bind = ["0.0.0.0:10000"]
    await serve(app, config)

if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.run(asyncio.gather(main(), run_flask()))
