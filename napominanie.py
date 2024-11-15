import os
import json
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, ChatMemberHandler

# Загружаем переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
JSON_DB_PATH = "users.json"  # Путь к JSON-файлу для хранения данных

# Инициализация JSON-базы данных (создает файл, если его нет)
def init_json_db():
    if not os.path.exists(JSON_DB_PATH):
        with open(JSON_DB_PATH, 'w') as f:
            json.dump({"users": {}, "schedule": {}}, f)

# Сохранение данных в JSON-файл
def save_data(data):
    with open(JSON_DB_PATH, 'w') as f:
        json.dump(data, f, indent=4)

# Загрузка данных из JSON-файла
def load_data():
    with open(JSON_DB_PATH, 'r') as f:
        return json.load(f)

# Добавление пользователя в JSON
def add_user(user_id, username, first_name):
    data = load_data()
    data["users"][user_id] = {
        "username": username,
        "first_name": first_name
    }
    save_data(data)

# Добавление расписания для пользователя в JSON
def add_schedule(user_id, day, time, description):
    data = load_data()
    if user_id not in data["schedule"]:
        data["schedule"][user_id] = []
    data["schedule"][user_id].append({
        "day": day,
        "time": time,
        "description": description,
        "reminder_sent": False
    })
    save_data(data)

# Удаление расписания пользователя по его username
def remove_schedule(username):
    data = load_data()
    user_id = None
    # Найти user_id по username
    for uid, info in data["users"].items():
        if info["username"] == username:
            user_id = uid
            break

    if user_id and user_id in data["schedule"]:
        del data["schedule"][user_id]
        save_data(data)
        return True
    return False

# Команда /start для регистрации пользователя
async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    add_user(user.id, user.username, user.first_name)

    if user.id == ADMIN_ID:
        await update.message.reply_text(
            "Вы зарегистрированы как администратор! Доступные команды:",
            reply_markup=ReplyKeyboardMarkup([["/schedule", "/remove_schedule", "/users", "/my_schedule"]], resize_keyboard=True)
        )
    else:
        await update.message.reply_text("Вы зарегистрированы! Вы будете получать напоминания о занятиях.")

# Команда /schedule для добавления расписания
async def schedule(update: Update, context: CallbackContext):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("У вас нет прав для изменения расписания.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Использование: /schedule @username день время описание"
        )
        return

    username, day, time, *description = context.args
    description = " ".join(description)

    data = load_data()
    user_id = None
    # Поиск user_id по username
    for uid, info in data["users"].items():
        if info["username"] == username.lstrip('@'):
            user_id = uid
            break

    if user_id:
        add_schedule(user_id, day, time, description)
        await update.message.reply_text(f"Занятие для пользователя @{username} добавлено.")
    else:
        await update.message.reply_text(f"Пользователь @{username} не найден.")

# Команда /remove_schedule для удаления расписания пользователя
async def remove_schedule_cmd(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("У вас нет прав для удаления расписания.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Использование: /remove_schedule @username")
        return

    username = context.args[0].lstrip('@')
    if remove_schedule(username):
        await update.message.reply_text(f"Все занятия для @{username} были удалены.")
    else:
        await update.message.reply_text(f"Пользователь @{username} не найден или у него нет расписания.")

# Команда /my_schedule для просмотра расписания пользователя
async def my_schedule(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    data = load_data()
    if user_id in data["schedule"]:
        schedule_text = "Ваше расписание:\n"
        for entry in data["schedule"][user_id]:
            schedule_text += f"{entry['day']} {entry['time']} - {entry['description']}\n"
        await update.message.reply_text(schedule_text)
    else:
        await update.message.reply_text("Ваше расписание пусто.")

# Команда /users для просмотра зарегистрированных пользователей (только для администратора)
async def list_users(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("У вас нет прав для просмотра списка пользователей.")
        return

    data = load_data()
    users_text = "Зарегистрированные пользователи:\n"
    for user_id, info in data["users"].items():
        users_text += f"{info['first_name']} (@{info['username']})\n"
    await update.message.reply_text(users_text)

# Основная функция для запуска бота
def main():
    init_json_db()
    application = Application.builder().token(BOT_TOKEN).build()

    # Регистрация команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("schedule", schedule))
    application.add_handler(CommandHandler("my_schedule", my_schedule))
    application.add_handler(CommandHandler("users", list_users))
    application.add_handler(CommandHandler("remove_schedule", remove_schedule_cmd))

    # Запуск бота
    application.run_polling()

if __name__ == "__main__":
    main()
