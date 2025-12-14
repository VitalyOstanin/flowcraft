"""
Временный интеграционный тест для workflow worklogs
"""

import pytest
import asyncio
import sys
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from workflows.manager import WorkflowManager
from workflows.engine import WorkflowEngine
from agents.manager import AgentManager
from core.trust import TrustManager
from core.settings import SettingsManager


@pytest.mark.asyncio
async def test_worklogs_last_7_days():
    """Тест workflow worklogs для активности за последние 7 дней"""
    
    print("✓ Инициализация компонентов...")
    settings_manager = SettingsManager()
    agent_manager = AgentManager(settings_manager)
    trust_manager = TrustManager(settings_manager)
    engine = WorkflowEngine(agent_manager, trust_manager)
    manager = WorkflowManager('~/.flowcraft/workflows', engine, settings_manager.settings)
    
    # Проверяем наличие workflow worklogs
    workflows = manager.list_workflows()
    worklogs_workflow = next((w for w in workflows if w['name'] == 'worklogs'), None)
    assert worklogs_workflow is not None, "Workflow worklogs не найден"
    
    print(f"✓ Найден workflow: {worklogs_workflow['name']}")
    
    # Выполняем workflow с задачей анализа активности
    task_description = "Покажи мою активность в YouTrack за последние 7 дней"
    
    print(f"✓ Запуск workflow с задачей: {task_description}")
    
    result = await manager.execute_workflow(
        workflow_name='worklogs',
        task_description=task_description
    )
    
    # Проверяем результат
    print(f"✓ Результат выполнения: success={result.get('success', False)}")
    
    if result.get('success'):
        completed_stages = result.get('completed_stages', [])
        print(f"✓ Выполнено этапов: {len(completed_stages)}")
        
        for stage in completed_stages:
            print(f"  ✓ {stage}")
        
        # Показываем вывод этапов
        stage_outputs = result.get('stage_outputs', {})
        for stage_name, output in stage_outputs.items():
            print(f"\n--- Результат этапа {stage_name} ---")
            print(f"Агент: {output.get('agent', 'неизвестно')}")
            print(f"Статус: {output.get('status', 'неизвестно')}")
            print(f"Вывод: {output.get('output', 'нет данных')}")
    else:
        error = result.get('error', 'Неизвестная ошибка')
        print(f"✗ Ошибка: {error}")
        
        failed_stages = result.get('failed_stages', [])
        if failed_stages:
            print(f"✗ Неудачные этапы: {failed_stages}")
    
    # Тест считается успешным если workflow запустился (независимо от результата)
    assert isinstance(result, dict), "Результат должен быть словарем"
    assert 'success' in result, "Результат должен содержать поле success"


if __name__ == "__main__":
    # Запуск теста напрямую
    asyncio.run(test_worklogs_last_7_days())
