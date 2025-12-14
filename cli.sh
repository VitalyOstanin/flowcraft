#!/bin/bash
cd "$(dirname "$0")"

# Проверяем наличие uv
if ! command -v uv &> /dev/null; then
    echo "Ошибка: uv не установлен. Установите uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Запускаем через uv с зависимостями проекта
uv run python cli.py "$@"
