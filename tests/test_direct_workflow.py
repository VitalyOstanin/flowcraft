#!/usr/bin/env python3

import asyncio
import sys
import os
import pytest

# Добавляем src в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

@pytest.mark.asyncio
async def test_direct_workflow():
    """Прямой тест workflow через WorkflowManager."""
    
    from workflows.manager import WorkflowManager
    from core.settings import Settings
    
    print("Инициализация...")
    settings = Settings()
    
    # Создаем минимальный workflow manager без полной инициализации
    workflow_manager = WorkflowManager.__new__(WorkflowManager)
    workflow_manager.settings = settings
    workflow_manager.workflows_dir = settings.workflows_dir
    
    # Загружаем workflows
    from workflows.loader import WorkflowLoader
    loader = WorkflowLoader(settings.workflows_dir)
    workflow_names = loader.list_workflows()
    
    print(f"Найдено workflows: {workflow_names}")
    
    # Загружаем default workflow
    if 'default' not in workflow_names:
        print("Default workflow не найден!")
        return
    
    default_workflow = loader.load_workflow('default')
    if not default_workflow:
        print("Не удалось загрузить default workflow!")
        return
    
    print("Тестирование default workflow...")
    print(f"Конфигурация: {default_workflow}")
    
    # Создаем простой engine для тестирования
    from workflows.engine import WorkflowEngine
    from agents.manager import AgentManager
    from core.trust import TrustManager
    
    # Создаем заглушки для менеджеров
    class MockAgentManager:
        def __init__(self):
            pass
    
    class MockTrustManager:
        def __init__(self):
            pass
    
    agent_manager = MockAgentManager()
    trust_manager = MockTrustManager()
    
    engine = WorkflowEngine(agent_manager, trust_manager)
    
    try:
        result = await engine.execute_workflow(
            default_workflow,
            "тестовая задача для проверки workflow"
        )
        print(f"Результат выполнения: {result}")
    except Exception as e:
        print(f"Ошибка при выполнении: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_direct_workflow())
