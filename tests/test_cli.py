#!/usr/bin/env python3
"""
Простой тест для проверки работоспособности FlowCraft
"""

import sys
from pathlib import Path

# Добавить src в путь для импортов
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rich.console import Console
from core.settings import SettingsManager
from agents.manager import AgentManager
from workflows.loader import WorkflowLoader

console = Console()

def test_basic_functionality():
    """Тест базовой функциональности"""
    console.print("Тестирование FlowCraft...", style="blue")
    
    try:
        # Тест настроек
        console.print("1. Тестирование настроек...", style="yellow")
        settings_manager = SettingsManager("test_settings.yaml")
        console.print("   Настройки загружены", style="green")
        
        # Тест менеджера агентов
        console.print("2. Тестирование менеджера агентов...", style="yellow")
        agent_manager = AgentManager(settings_manager)
        
        # Создание тестового агента
        agent = agent_manager.create_agent(
            name="test_agent",
            system_prompt="Ты тестовый разработчик",
            description="Тестовый агент",
            capabilities=["coding"],
            llm_model="qwen3-coder-plus"
        )
        console.print(f"   Агент создан: {agent.name}", style="green")
        
        # Список агентов
        agents = agent_manager.list_agents()
        console.print(f"   Всего агентов: {len(agents)}", style="green")
        
        # Удаление тестового агента
        agent_manager.delete_agent("test_agent")
        console.print("   Тестовый агент удален", style="green")
        
        # Тест загрузчика workflow
        console.print("3. Тестирование загрузчика workflow...", style="yellow")
        workflow_loader = WorkflowLoader(settings_manager.settings.workflows_dir)
        
        workflows = workflow_loader.list_workflows()
        console.print(f"   Найдено workflow: {len(workflows)}", style="green")
        
        if workflows:
            for workflow_name in workflows:
                info = workflow_loader.get_workflow_info(workflow_name)
                if info:
                    console.print(f"   - {workflow_name}: {info['description']}", style="cyan")
        
        console.print("Все тесты пройдены успешно!", style="bold green")
        
        # Очистка
        test_settings_file = Path("test_settings.yaml")
        if test_settings_file.exists():
            test_settings_file.unlink()
        
    except Exception as e:
        console.print(f"Ошибка в тестах: {e}", style="red")
        import traceback
        console.print(traceback.format_exc())
        assert False, "Тест не должен был завершиться с ошибкой"
    
    assert True  # Тест прошел успешно

if __name__ == "__main__":
    success = test_basic_functionality()
    sys.exit(0 if success else 1)
