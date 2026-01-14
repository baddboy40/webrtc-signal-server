FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей (только для сигнального сервера)
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Копирование requirements и установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения
COPY signal_server.py .

# Создание непривилегированного пользователя
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Открытие порта
EXPOSE 8765

# Запуск сервера
CMD ["python", "signal_server.py"]
