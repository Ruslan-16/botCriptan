import os
import json
import requests
from datetime import datetime, timedelta, time
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


# Загрузка и сохранение данных на Яндекс.Диске
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


# Функции для работы с ценами на криптовалюты
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


def update_prices():
    """Обновляет текущие данные и сохраняет записи для трех точек: сейчас, 12 часов назад, и 24 часа назад."""
    current_prices = get_crypto_data()
    if current_prices:
        prices = load_prices()

        # Сохраняем текущие данные
        timestamp_now = datetime.now().isoformat()
        prices["now"] = {"timestamp": timestamp_now, "data": current_prices}

        # Сохраняем для 12 и 24 часов назад, если их временные метки отличаются от текущих
        timestamp_12h = (datetime.now() - timedelta(hours=12)).isoformat()
        timestamp_24h = (datetime.now() - timedelta(hours=24)).isoformat()

        if "12h" not in prices or prices["12h"]["timestamp"] != timestamp_12h:
            prices["12h"] = {"timestamp": timestamp_12h, "data": current_prices}
        if "24h" not in prices or prices["24h"]["timestamp"] != timestamp_24h:
            prices["24h"] = {"timestamp": timestamp_24h, "data": current_prices}

        save_prices(prices)
    else:
        print("Не удалось получить текущие данные о ценах.")


# Команды бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        "🤑 Вы подписались на рассылку (в 9:00 и 21:00) цен на Криптовалюты. "
        "Используйте /history для просмотра текущих и исторических цен.")
    add_user(chat_id)


async def count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_count = get_user_count()
    await update.message.reply_text(f"В боте {user_count} подписчиков 🙌.")


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prices = load_prices()
    message = f"🗓️ Актуальные данные на {datetime.now().strftime('%d-%m-%Y %H:%M')}:\n"

    # Текущие данные
    if "now" in prices:
        message += "Текущие цены:\n"
        for symbol, price in prices["now"]["data"].items():
            message += f"💰{symbol}: {price:.2f} USD\n"

    # Цены 12 часов назад
    if "12h" in prices:
        message += f"\nЦены 12 часов назад:\n"
        for symbol, price in prices["12h"]["data"].items():
            message += f"💰{symbol}: {price:.2f} USD\n"

    # Цены 24 часа назад
    if "24h" in prices:
        message += f"\nЦены 24 часа назад:\n"
        for symbol, price in prices["24h"]["data"].items():
            message += f"💰{symbol}: {price:.2f} USD\n"

    await update.message.reply_text(message)


async def send_crypto_update(context: ContextTypes.DEFAULT_TYPE):
    update_prices()
    prices = load_prices()
    message = "📈 Обновленные данные о ценах на криптовалюту:\n"

    # Текущие цены
    if "now" in prices:
        message += "Текущие цены:\n"
        for symbol, price in prices["now"]["data"].items():
            message += f"💰{symbol}: {price:.2f} USD\n"

    users = load_users()
    for chat_id in users:
        try:
            await context.bot.send_message(chat_id=chat_id, text=message)
        except Exception as e:
            print(f"Ошибка отправки для {chat_id}: {e}")
            if "bot was blocked" in str(e) or "user is deactivated" in str(e):
                users.remove(chat_id)
                save_users(users)


# Основные настройки бота
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


# Запуск бота и веб-сервера
async def main():
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("count", count))
    bot_app.add_handler(CommandHandler("history", history))

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
