#!/usr/bin/env python3
"""
Демонстрационный тест LLM системы FlowCraft.
Показывает работу автоматического выбора модели.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.settings import SettingsManager, Settings, LLMConfig
from src.llm.integration import LLMIntegration
from unittest.mock import MagicMock


def demo_llm_integration():
    """Демонстрация работы LLM интеграции."""
    print("Демонстрация LLM системы FlowCraft")
    print("=" * 50)
    
    # Создаем мок настроек
    mock_settings = Settings(
        language="ru",
        llm=LLMConfig(
            cheap_model="qwen-code",
            expensive_model="kiro-cli",
            expensive_stages=["security_review", "architecture_design"]
        ),
        mcp_servers=[],
        trust_rules={},
        workflows_dir="~/.flowcraft/workflows",
        agents={}
    )
    
    mock_settings_manager = MagicMock()
    mock_settings_manager.settings = mock_settings
    
    # Создаем интеграцию
    try:
        integration = LLMIntegration(mock_settings_manager)
        print("✓ LLM интеграция создана успешно")
    except Exception as e:
        print(f"✗ Ошибка создания интеграции: {e}")
        return
    
    # Тестируем выбор модели для разных сценариев
    test_cases = [
        {
            "name": "Простой вопрос",
            "messages": [{"role": "user", "content": "Привет, как дела?"}],
            "stage": None,
            "expected_type": "cheap"
        },
        {
            "name": "Вопрос по архитектуре",
            "messages": [{"role": "user", "content": "Спроектируй архитектуру микросервисов"}],
            "stage": None,
            "expected_type": "expensive"  # Сложная задача по ключевым словам
        },
        {
            "name": "Этап security_review",
            "messages": [{"role": "user", "content": "Проверь код"}],
            "stage": "security_review",
            "expected_type": "expensive"  # Дорогой этап
        },
        {
            "name": "Принудительно дорогая модель",
            "messages": [{"role": "user", "content": "Простой вопрос"}],
            "stage": None,
            "force_expensive": True,
            "expected_type": "expensive"
        }
    ]
    
    print("\nТестирование выбора модели:")
    print("-" * 50)
    
    for i, test_case in enumerate(test_cases, 1):
        try:
            model_info = integration.get_current_model_info(
                messages=test_case["messages"],
                stage=test_case.get("stage"),
                force_expensive=test_case.get("force_expensive", False)
            )
            
            expected = test_case["expected_type"]
            actual = model_info["type"]
            status = "✓" if actual == expected else "✗"
            
            print(f"{i}. {test_case['name']}")
            print(f"   Провайдер: {model_info['provider']}")
            print(f"   Тип: {actual} (ожидался: {expected}) {status}")
            print(f"   Этап: {model_info.get('stage', 'не указан')}")
            print()
            
        except Exception as e:
            print(f"{i}. {test_case['name']} - ✗ Ошибка: {e}")
            print()
    
    print("Демонстрация завершена!")
    print("\nОсновные возможности LLM системы:")
    print("• Автоматический выбор между дешевой и дорогой моделью")
    print("• Анализ сложности задач по ключевым словам")
    print("• Выбор модели на основе этапа workflow")
    print("• Принудительное использование дорогой модели")
    print("• Поддержка qwen-code и kiro-cli провайдеров")


if __name__ == "__main__":
    demo_llm_integration()
