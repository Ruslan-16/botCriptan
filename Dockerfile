# Используем базовый образ Python 3.10
FROM python:3.10-slim

# Устанавливаем рабочую директорию
WORKDIR /bot

# Копируем все файлы проекта в контейнер
COPY . .

# Устанавливаем зависимости из requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Указываем переменные окружения
ENV TG_BOT_TOKEN=7602913247:AAFFy0De4_DSBg_c0V_wiK1TECMtAgMZJA8
ENV CMC_API_KEY=c923b3dc-cd07-4216-8edc-9d73beb665cc
ENV WEBHOOK_URL=https://ruslan-16-botcriptan-dd61.twc1.net/webhook


# Запускаем бота
CMD ["python", "main.py"]


