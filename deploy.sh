#!/bin/bash

# Скрипт для деплоя WebRTC сигнального сервера

set -e

echo "🚀 Начало деплоя WebRTC Signal Server..."

# Проверка наличия Docker и Docker Compose
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен. Установите Docker и попробуйте снова."
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose не установлен. Установите Docker Compose и попробуйте снова."
    exit 1
fi

# Создание .env файла, если его нет
if [ ! -f .env ]; then
    echo "📝 Создание .env файла из примера..."
    cp .env.example .env
    echo "⚠️  Отредактируйте .env файл перед запуском!"
fi

# Создание директории для SSL сертификатов
if [ ! -d ssl ]; then
    echo "📁 Создание директории для SSL сертификатов..."
    mkdir -p ssl
    echo "⚠️  Для HTTPS поместите сертификаты в директорию ssl/"
fi

# Сборка и запуск контейнеров
echo "🔨 Сборка Docker образов..."
docker-compose build

echo "🚀 Запуск контейнеров..."
docker-compose up -d

echo "⏳ Ожидание запуска сервисов..."
sleep 5

# Проверка статуса
echo "📊 Статус контейнеров:"
docker-compose ps

echo ""
echo "✅ Деплой завершен!"
echo ""
echo "📋 Полезные команды:"
echo "  - Просмотр логов: docker-compose logs -f"
echo "  - Остановка: docker-compose down"
echo "  - Перезапуск: docker-compose restart"
echo "  - Обновление: docker-compose pull && docker-compose up -d"
echo ""
echo "🌐 Сервер доступен по адресу:"
echo "  - HTTP: http://localhost:${HTTP_PORT:-80}"
echo "  - WebSocket: ws://localhost:${HTTP_PORT:-80}/ws"
