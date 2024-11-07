import os
import json
import aiohttp
from datetime import datetime, timedelta, time
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import nest_asyncio
import asyncio
from flask import Flask, request
from hypercorn.asyncio import serve
from hypercorn.config import Config

# Применяем поддержку асинхронности в Flask
nest_asyncio.apply()

# Инициализация Flask
app = Flask(__name__)

# Переменные окружения с вашими данными
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "7602913247:AAFFy0De4_DSBg_c0V_wiK1TECMtAgMZJA8")
CMC_API_KEY = os.getenv("CMC_API_KEY", "c923b3dc-cd07-4216-8edc-9d73beb665cc")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://ruslan-16-botcriptan-dd61.twc1.net/webhook")

# Файлы для хранения пользователей и данных
USERS_FILE = "users.json"
DATA_FILE = "crypto_data.json"

# Определяем точность для каждого символа
precision = {
    "BTC": 2, "ETH": 2, "ADA": 3, "PEPE": 6, "SOL": 2, "SUI": 2, 'TON': 2, 'FET': 3,
    'APT': 3, 'AVAX': 2, 'FLOKI': 6, 'TWT': 3, 'ALGO': 3, 'CAKE': 2, '1INCH': 3,
    'MANA': 3, 'FLOW': 3, 'EGLD': 2, 'ARB': 3, 'DYDX': 2, 'APEX': 3, 'CRV': 3,
    'ATOM': 2, 'POL': 3, 'OP': 2, 'SEI': 3
}

# Ваши функции и обработчики команд

# Создание приложения Telegram с JobQueue
bot_app = Application.builder().token(TG_BOT_TOKEN).build()

async def main():
    # Инициализация JobQueue
    job_queue = bot_app.job_queue
    if job_queue is None:
        print("Ошибка: job_queue не инициализирован.")
    else:
        # Добавляем задачи, если инициализация прошла успешно
        job_queue.run_daily(scheduled_crypto_update, time(hour=9, minute=0))
        job_queue.run_daily(scheduled_crypto_update, time(hour=19, minute=0))

    # Регистрация обработчиков команд
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("cripto", get_crypto))
    bot_app.add_handler(CommandHandler("history", get_crypto_history))
    bot_app.add_handler(CommandHandler("user_count", user_count))

    # Установка вебхука и запуск бота
    await bot_app.initialize()
    await bot_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    await bot_app.start()
    print("Бот запущен и вебхук установлен.")

# Запуск Flask
async def run_flask():
    config = Config()
    config.bind = ["0.0.0.0:8443"]
    await serve(app, config)

if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.run(asyncio.gather(main(), run_flask()))
