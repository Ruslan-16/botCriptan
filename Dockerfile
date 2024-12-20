# Используем базовый образ Python 3.10
# Используем базовый образ Python 3.10
FROM python:3.10-slim

# Устанавливаем рабочую директорию
WORKDIR /bot

# Копируем файлы проекта в контейнер
COPY . .

# Устанавливаем зависимости из requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Указываем порт, на котором приложение будет работать
EXPOSE 8443

# Запускаем приложение
CMD ["python", "bot.py"]


