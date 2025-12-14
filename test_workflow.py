#!/usr/bin/env python3

import asyncio
import sys
import os

# Добавляем src в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from workflows.manager import WorkflowManager
from core.settings import Settings

async def test_default_workflow():
    """Тест default workflow."""
    
    print("Инициализация...")
    settings = Settings()
    workflow_manager = WorkflowManager(settings)
    
    print("Загрузка workflow...")
    workflows = workflow_manager.list_workflows()
    print(f"Найдено workflows: {[w['name'] for w in workflows]}")
    
    if not workflows:
        print("Нет доступных workflows!")
        return
    
    # Находим default workflow
    default_workflow = None
    for w in workflows:
        if w['name'] == 'default':
            default_workflow = w
            break
    
    if not default_workflow:
        print("Default workflow не найден!")
        return
    
    print("Запуск default workflow...")
    try:
        result = await workflow_manager.execute_workflow(
            workflow_name='default',
            task_description='тестовая задача'
        )
        print(f"Результат: {result}")
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_default_workflow())
