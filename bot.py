import os
import json
import requests
from datetime import datetime, time
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
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

    # Получение ссылки для загрузки файла
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

    # Получение ссылки для скачивания файла
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
    download_from_yandex_disk('users.json', 'users.json')  # Загрузить файл с Яндекс.Диска
    if os.path.exists("users.json"):
        with open("users.json", "r") as f:
            return json.load(f)
    return []


def save_users(users):
    """Сохраняет список пользователей в файл users.json на Яндекс.Диске."""
    with open("users.json", "w") as f:
        json.dump(users, f)
    upload_to_yandex_disk('users.json', 'users.json')  # Загрузить файл обратно на Яндекс.Диск


def add_user(chat_id):
    users = load_users()
    if chat_id not in users:
        users.append(chat_id)
        save_users(users)


def get_user_count():
    users = load_users()
    return len(users)


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
                message += f"💰{symbol}: 📈{price:.5f}\n"
        return message
    else:
        return f"Ошибка получения данных: {response.status_code}"


# Отправка обновлений пользователям
async def send_crypto_update(context: ContextTypes.DEFAULT_TYPE):
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
        "Нажмите /crypto для получения информации сразу.")
    add_user(chat_id)


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
        print(f"Ошибка обработки вебхука: {e}")
        return "Error", 500


# Команда /crypto для запроса обновлений
async def crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = get_crypto_data()
    await update.message.reply_text(message)


async def count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_count = get_user_count()
    await update.message.reply_text(f"В боте {user_count} подписчиков 🥹.")


async def main():
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("crypto", crypto))
    bot_app.add_handler(CommandHandler("count", count))

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
