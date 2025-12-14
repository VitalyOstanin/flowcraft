#!/usr/bin/env python3
"""
Простой тест для проверки функции очистки экрана
"""

import sys
import os
sys.path.insert(0, 'src')

from core.interactive_cli import SimpleInteractiveCLI
from rich.console import Console

console = Console()

def test_clear_screen():
    """Тест функции очистки экрана"""
    
    # Создаем mock объекты
    class MockSettings:
        def __init__(self):
            self.workflows_dir = "test"
    
    class MockSettingsManager:
        def __init__(self):
            self.settings = MockSettings()
    
    class MockAgentManager:
        def __init__(self):
            self.agents = {}
    
    class MockWorkflowLoader:
        pass
    
    # Создаем CLI
    cli = SimpleInteractiveCLI(
        settings_manager=MockSettingsManager(),
        agent_manager=MockAgentManager(),
        workflow_loader=MockWorkflowLoader()
    )
    
    # Тестируем очистку экрана
    console.print("Тест очистки экрана...")
    console.print("Много текста для демонстрации...")
    for i in range(10):
        console.print(f"Строка {i}")
    
    console.print("\nСейчас будет очистка экрана...")
    # input("Нажмите Enter для продолжения...")  # Убрано для автотестов
    
    # Очищаем экран
    cli.clear_screen()
    
    console.print("Экран очищен!", style="green")
    console.print("Тест завершен успешно", style="bold green")

if __name__ == "__main__":
    test_clear_screen()
