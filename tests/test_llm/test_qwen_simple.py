#!/usr/bin/env python3
"""Простой тест для проверки работы qwen3-coder-plus."""

import asyncio
import sys
from pathlib import Path

# Добавить src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from llm.qwen_code import QwenCodeProvider
from llm.base import LLMMessage


async def main():
    """Простой тест провайдера."""
    print("Тестирование qwen3-coder-plus провайдера...")
    
    # Проверить наличие credentials
    oauth_path = Path.home() / ".qwen" / "oauth_creds.json"
    if not oauth_path.exists():
        print(f"✗ Файл credentials не найден: {oauth_path}")
        print("Установите qwen-code CLI и выполните аутентификацию:")
        print("npm install -g @qwen-code/qwen-code@latest")
        return
    
    try:
        provider = QwenCodeProvider(model_name="qwen3-coder-plus")
        
        messages = [
            LLMMessage(role="system", content="Ты помощник программиста."),
            LLMMessage(role="user", content="Привет! Как дела?")
        ]
        
        print("Отправляем тестовый запрос...")
        response = await provider.chat_completion(messages, temperature=0.3, max_tokens=100)
        
        print("✓ Успешно!")
        print(f"Ответ: {response.content}")
        
        if response.usage:
            print(f"Использование токенов: {response.usage}")
        
    except Exception as e:
        print(f"✗ Ошибка: {e}")
        print("Проверьте настройки OAuth credentials")


if __name__ == "__main__":
    asyncio.run(main())
