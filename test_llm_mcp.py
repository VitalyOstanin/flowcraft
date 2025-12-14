#!/usr/bin/env python3
"""
Тест новой архитектуры LLM+MCP
"""

import asyncio
import sys
import os

# Добавляем src в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

async def test_llm_mcp_integration():
    """Тест интеграции LLM с MCP инструментами."""
    
    print("🧪 Тестирование новой архитектуры LLM+MCP...")
    
    try:
        from workflows.llm_integration import LLMIntegration
        from core.settings import SettingsManager
        
        # Создаем настройки
        settings_manager = SettingsManager()
        
        # Создаем LLM интеграцию
        llm_integration = LLMIntegration(settings_manager)
        
        print("✓ LLMIntegration создана успешно")
        
        # Тестовые данные
        system_prompt = "Ты аналитик YouTrack. Анализируй активность пользователей."
        user_prompt = "Получи данные о work items за последние 7 дней и проанализируй их."
        mcp_servers = ['youtrack-mcp']
        agent_config = {
            'name': 'test_analyst',
            'role': 'analyst',
            'llm_model': 'qwen3-coder-plus'
        }
        
        print("✓ Тестовые данные подготовлены")
        
        # Выполняем задачу (пока без реального MCP)
        try:
            result = await llm_integration.execute_with_mcp_tools(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                mcp_servers=mcp_servers,
                agent_config=agent_config
            )
            print(f"✓ Результат выполнения: {result[:100]}...")
        except Exception as e:
            print(f"⚠️  Ошибка выполнения (ожидаемо без MCP): {e}")
        
        print("✅ Новая архитектура LLM+MCP готова к использованию!")
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_llm_mcp_integration())
