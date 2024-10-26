import os
import json
import requests
from datetime import datetime, time
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio
import nest_asyncio

# Патч для работы с уже запущенным циклом событий
nest_asyncio.apply()

# Переменные окружения для токенов
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
CMC_API_KEY = os.getenv("CMC_API_KEY")
USERS_FILE = "users.json"

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
    headers = {"Accepts": "application/json", "X-CMC_PRO_API_KEY": CMC_API_KEY}
    watchlist_symbols = ["BTC", "ETH", "ADA", "PEPE", "SOL", "POL", "FLOKI", "SEI", "SUI", "AVAX"]
    symbol_param = ",".join(watchlist_symbols)
    params = {"symbol": symbol_param, "convert": "USD"}

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()["data"]
        message = f"🗓️ Актуальные данные на {datetime.now().strftime('%Y-%m-%d')}:\n"
        for symbol in watchlist_symbols:
            if symbol in data:
                crypto = data[symbol]
                price = crypto["quote"]["USD"]["price"]
                message += f"{crypto['name']} ({crypto['symbol']}): ${price:.5f}\n"
        return message
    else:
        return f"Ошибка при запросе данных: {response.status_code}"

# Функция для отправки сообщений всем пользователям
async def send_crypto_update(context: ContextTypes.DEFAULT_TYPE):
    message = get_crypto_data()
    users = load_users()
    for chat_id in users[:]:
        try:
            await context.bot.send_message(chat_id=chat_id, text=message)
            print(f"Сообщение отправлено пользователю {chat_id}")
        except Exception as e:
            print(f"Ошибка при отправке для {chat_id}: {e}")
            if "bot was blocked by the user" in str(e) or "user is deactivated" in str(e):
                users.remove(chat_id)
                save_users(users)
                print(f"Пользователь {chat_id} удалён из списка.")

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text("Привет! Вы подписаны на рассылку актуальных цен на криптовалюту в 9:00 и 19:00 ежедневно.")
    add_user(chat_id)

# Основная функция запуска
async def main():
    app = Application.builder().token(TG_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    # Настройка задач JobQueue для регулярных сообщений
    job_queue = app.job_queue
    job_queue.run_daily(send_crypto_update, time(hour=9, minute=0, second=0))
    job_queue.run_daily(send_crypto_update, time(hour=19, minute=0, second=0))

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
