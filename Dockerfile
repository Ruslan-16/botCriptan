# Базовый образ Python
FROM python:3.9-slim

# Устанавливаем рабочую директорию в контейнере
WORKDIR /app

# Копируем все файлы проекта в контейнер
COPY . .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем переменные окружения для токенов
ENV TG_BOT_TOKEN="7602913247:AAFFy0De4_DSBg_c0V_wiK1TECMtAgMZJA8"
ENV CMC_API_KEY="c923b3dc-cd07-4216-8edc-9d73beb665cc"

# Запускаем приложение
CMD ["python", "bot.py"]
