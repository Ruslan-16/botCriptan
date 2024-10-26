import requests
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import nest_asyncio
import json
import os
import asyncio

# Применение патча для повторного использования текущего цикла событий
nest_asyncio.apply()

# Токены для работы
CMC_API_KEY = "c923b3dc-cd07-4216-8edc-9d73beb665cc"  # Токен CoinMarketCap
TG_BOT_TOKEN = "7602913247:AAFFy0De4_DSBg_c0V_wiK1TECMtAgMZJA8"  # Токен Telegram-бота
USERS_FILE = "users.json"  # Файл для хранения списка пользователей

# Загрузка списка пользователей из файла
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return []

# Сохранение списка пользователей в файл
def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)

# Добавление нового пользователя в список
def add_user(chat_id):
    users = load_users()
    if chat_id not in users:
        users.append(chat_id)
        save_users(users)

# Получение данных о криптовалютах
def get_crypto_data():
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": CMC_API_KEY
    }

    watchlist_symbols = ["BTC", "ETH", "ADA", "PEPE", "SOL", "POL", "FLOKI", "SEI", "SUI", "AVAX"]
    symbol_param = ",".join(watchlist_symbols)

    params = {
        "symbol": symbol_param,
        "convert": "USD"
    }

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()["data"]
        message = f"🗓️ Актуальные данные на {datetime.now().strftime('%Y-%m-%d')}:\n"
        for symbol in watchlist_symbols:
            if symbol in data:
                crypto = data[symbol]
                price = crypto["quote"]["USD"]["price"]
                message += f"{crypto['name']} ({crypto['symbol']}): ${price:.2f}\n"
        return message
    else:
        return f"Ошибка при запросе данных: {response.status_code}"

# Асинхронная функция для отправки сообщения с криптовалютами
async def send_crypto_update(app: Application):
    message = get_crypto_data()
    users = load_users()
    for chat_id in users:
        try:
            await app.bot.send_message(chat_id=chat_id, text=message)
            print(f"Сообщение отправлено пользователю {chat_id}")
        except Exception as e:
            print(f"Ошибка при отправке для {chat_id}: {e}")

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text("Привет! Вы подписались на ежедневную рассылку.")
    add_user(chat_id)

# Основной запуск бота с таймером завершения
async def main():
    app = Application.builder().token(TG_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    # Отправка сообщения о криптовалюте и запуск бота на 5 секунд
    try:
        await send_crypto_update(app)  # Отправка данных сразу при запуске
        await app.initialize()  # Инициализация
        await app.start()       # Запуск бота
        await asyncio.sleep(5)   # Ожидание 5 секунд
    finally:
        await app.stop()         # Принудительная остановка бота
        await app.shutdown()     # Завершение всех задач бота
        print("Бот завершил работу автоматически через 5 секунд.")

# Запуск бота
if __name__ == "__main__":
    asyncio.run(main())
