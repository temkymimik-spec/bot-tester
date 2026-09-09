#!/usr/bin/env bash
# Запуск бота (для BotHost/другого хостинга)
# 1) Установите зависимости: pip install -r requirements.txt
# 2) Скопируйте .env.example в .env и заполните BOT_TOKEN/ADMIN_IDS/DATABASE_URL
# 3) Выполните: ./start.sh
set -e
cd "$(dirname "$0")"

# Python из venv, если есть
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Проверим, есть ли .env
if [ ! -f ".env" ]; then
    echo "⚠️  Нет файла .env. Создаю из примера..."
    cp .env.example .env
    echo "Заполните .env перед запуском!"
    exit 1
fi

# Ставим зависимости
pip install -q -r requirements.txt

echo "Запускаю бота..."
python bot.py