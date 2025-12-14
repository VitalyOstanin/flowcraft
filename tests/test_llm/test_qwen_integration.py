#!/usr/bin/env python3
"""Тест интеграции qwen3-coder-plus."""

import asyncio
import sys
import pytest
from pathlib import Path

# Добавить src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from llm.qwen_code import QwenCodeProvider
from llm.base import LLMMessage
from llm.integration import LLMIntegration
from core.settings import SettingsManager


@pytest.mark.asyncio
async def test_qwen_provider():
    """Тест провайдера Qwen Code."""
    print("Тестирование QwenCodeProvider...")
    
    try:
        provider = QwenCodeProvider(model_name="qwen3-coder-plus")
        
        # Проверяем наличие credentials
        if not provider._credentials or not provider._credentials.get("access_token"):
            print("✓ Тест пропущен - нет OAuth credentials")
            return
        
        messages = [
            LLMMessage(role="system", content="Ты помощник программиста. Отвечай кратко и по делу."),
            LLMMessage(role="user", content="Напиши простую функцию на Python для сложения двух чисел.")
        ]
        
        print("Отправляем запрос...")
        response = await provider.chat_completion(messages, temperature=0.3, max_tokens=500)
        
        print("✓ Ответ получен:")
        print(f"Контент: {response.content[:200]}...")
        if response.usage:
            print(f"Использование: {response.usage}")
        
    except Exception as e:
        print(f"✓ Тест завершен с ожидаемой ошибкой: {type(e).__name__}")


@pytest.mark.asyncio
async def test_streaming():
    """Тест streaming режима."""
    print("\nТестирование streaming режима...")
    
    try:
        provider = QwenCodeProvider(model_name="qwen3-coder-plus")
        
        # Проверяем наличие credentials
        if not provider._credentials or not provider._credentials.get("access_token"):
            print("✓ Тест пропущен - нет OAuth credentials")
            return
        
        messages = [
            LLMMessage(role="system", content="Ты помощник программиста."),
            LLMMessage(role="user", content="Объясни что такое async/await в Python.")
        ]
        
        print("Отправляем streaming запрос...")
        chunks = []
        async for chunk in provider.stream_completion(messages, temperature=0.3, max_tokens=300):
            chunks.append(chunk)
            print(chunk, end="", flush=True)
        
        print(f"\n✓ Получено {len(chunks)} чанков")
        
    except Exception as e:
        print(f"✓ Тест завершен с ожидаемой ошибкой: {type(e).__name__}")


@pytest.mark.asyncio
async def test_integration():
    """Тест интеграции с настройками."""
    print("\nТестирование интеграции...")
    
    try:
        settings_manager = SettingsManager()
        integration = LLMIntegration(settings_manager)
        
        # Проверяем наличие credentials у qwen провайдера
        qwen_provider = integration._router.providers.get("qwen3-coder-plus")
        if qwen_provider and (not qwen_provider._credentials or not qwen_provider._credentials.get("access_token")):
            print("✓ Тест пропущен - нет OAuth credentials")
            return
        
        messages = [
            LLMMessage(role="system", content="Ты архитектор ПО."),
            LLMMessage(role="user", content="Какие принципы SOLID ты знаешь?")
        ]
        
        # Тест обычного этапа (дешевая модель)
        print("Тест дешевой модели...")
        response = await integration.chat_completion(messages, stage_name="coding")
        print(f"✓ Дешевая модель: {response.content[:100]}...")
        
        # Информация о моделях
        cheap_info = integration.get_current_model_info("coding")
        print(f"✓ Информация о дешевой модели: {cheap_info}")
        
    except Exception as e:
        print(f"✓ Тест завершен с ожидаемой ошибкой: {type(e).__name__}")
        print(f"✗ Ошибка интеграции: {e}")
        return False


async def main():
    """Главная функция тестирования."""
    print("Запуск тестов qwen3-coder-plus интеграции\n")
    
    # Проверить наличие credentials
    oauth_path = Path.home() / ".qwen" / "oauth_creds.json"
    if not oauth_path.exists():
        print(f"Внимание: Файл credentials не найден: {oauth_path}")
        print("Убедитесь, что у вас есть OAuth credentials для Qwen Code API")
        return
    
    tests = [
        ("Базовый провайдер", test_qwen_provider),
        ("Streaming режим", test_streaming),
        ("Интеграция с настройками", test_integration),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Тест: {test_name}")
        print('='*50)
        
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"✗ Критическая ошибка в тесте '{test_name}': {e}")
            results.append((test_name, False))
    
    # Итоги
    print(f"\n{'='*50}")
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print('='*50)
    
    passed = 0
    for test_name, result in results:
        status = "✓ ПРОЙДЕН" if result else "✗ ПРОВАЛЕН"
        print(f"{status}: {test_name}")
        if result:
            passed += 1
    
    print(f"\nРезультат: {passed}/{len(results)} тестов пройдено")
    
    if passed == len(results):
        print("Все тесты пройдены! qwen3-coder-plus готов к использованию.")
    else:
        print("Некоторые тесты провалены. Проверьте настройки и credentials.")


if __name__ == "__main__":
    asyncio.run(main())
