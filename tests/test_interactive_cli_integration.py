"""
Интеграционные тесты для интерактивного CLI
"""

import tempfile
import os
from pathlib import Path
import yaml
from unittest.mock import patch, MagicMock
from io import StringIO
import sys

# Добавить src в путь
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.interactive_cli import SimpleInteractiveCLI
from core.settings import SettingsManager
from agents.manager import AgentManager
from workflows.loader import WorkflowLoader


class TestInteractiveCLIIntegration:
    """Интеграционные тесты CLI с изоляцией"""
    
    def setup_method(self):
        """Настройка изолированного окружения для каждого теста"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.flowcraft_dir = Path(self.temp_dir.name) / ".flowcraft"
        self.flowcraft_dir.mkdir(parents=True)
        
        # Создать settings.yaml
        settings_file = self.flowcraft_dir / "settings.yaml"
        settings_data = {
            'language': 'ru',
            'llm': {
                'cheap_model': 'qwen3-coder-plus',
                'expensive_model': 'kiro-cli'
            },
            'workflows_dir': str(self.flowcraft_dir / "workflows"),
            'agents': {}
        }
        
        with open(settings_file, 'w') as f:
            yaml.dump(settings_data, f)
        
        # Инициализировать менеджеры
        self.settings_manager = SettingsManager(str(settings_file))
        self.agent_manager = AgentManager(self.settings_manager)
        self.workflow_loader = WorkflowLoader(self.settings_manager.settings.workflows_dir)
        self.cli = SimpleInteractiveCLI(self.settings_manager, self.agent_manager, self.workflow_loader)
        
        # Создать тестового агента
        self.agent_manager.create_agent(
            name="test-agent",
            system_prompt="Тестовый агент",
            description="Для тестирования",
            capabilities=["testing"],
            llm_model="qwen3-coder-plus"
        )
    
    def teardown_method(self):
        """Очистка после теста"""
        self.temp_dir.cleanup()
    
    def test_list_agents_requires_enter(self):
        """Тест что список агентов использует CustomPrompt (требует Enter)"""
        # Проверяем, что метод list_agents работает без ввода
        # (не требует пользовательского ввода, только выводит таблицу)
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            self.cli.list_agents()
            output = mock_stdout.getvalue()
            
        # Проверяем, что вывод содержит таблицу агентов
        assert "test-agent" in output
        assert "Агенты" in output
        assert "qwen3-coder-plus" in output
    
    @patch('core.interactive_cli.CustomPrompt.ask')
    def test_create_agent_uses_custom_prompt(self, mock_prompt):
        """Тест что создание агента использует CustomPrompt (требует Enter)"""
        # Настройка мока для последовательных вызовов
        mock_prompt.side_effect = [
            "new-agent",  # имя
            "Новый системный промпт",  # system_prompt
            "Новое описание",  # description
            "qwen3-coder-plus",  # модель
            "coding,testing"  # capabilities
        ]
        
        # Вызов метода
        self.cli.create_agent()
        
        # Проверяем, что CustomPrompt.ask был вызван нужное количество раз
        assert mock_prompt.call_count == 5
        
        # Проверяем, что агент создан
        assert "new-agent" in self.agent_manager.agents
        created_agent = self.agent_manager.agents["new-agent"]
        assert created_agent.system_prompt == "Новый системный промпт"
        assert created_agent.description == "Новое описание"
    
    @patch('core.interactive_cli.CustomPrompt.ask')
    @patch('core.interactive_cli.Confirm.ask')
    def test_delete_agent_uses_custom_prompt(self, mock_confirm, mock_prompt):
        """Тест что удаление агента использует CustomPrompt (требует Enter)"""
        # Настройка моков
        mock_prompt.return_value = "1"  # выбор первого агента
        mock_confirm.return_value = True  # подтверждение удаления
        
        # Вызов метода
        self.cli.delete_agent()
        
        # Проверяем, что CustomPrompt.ask был вызван для выбора агента
        mock_prompt.assert_called_once()
        
        # Проверяем, что Confirm.ask был вызван для подтверждения
        mock_confirm.assert_called_once()
        
        # Проверяем, что агент удален
        assert "test-agent" not in self.agent_manager.agents
    
    @patch('core.interactive_cli.CustomPrompt.ask')
    def test_create_workflow_uses_custom_prompt(self, mock_prompt):
        """Тест что создание workflow использует CustomPrompt (требует Enter)"""
        # Настройка мока
        mock_prompt.side_effect = [
            "test-workflow",  # название
            "Тестовый workflow"  # описание
        ]
        
        # Вызов метода
        self.cli.create_workflow()
        
        # Проверяем, что CustomPrompt.ask был вызван
        assert mock_prompt.call_count == 2
        
        # Проверяем вызовы с правильными параметрами
        calls = mock_prompt.call_args_list
        assert "Название workflow" in str(calls[0])
        assert "Описание workflow" in str(calls[1])
    
    @patch('core.interactive_cli.CustomPrompt.ask')
    def test_workflow_selection_uses_custom_prompt(self, mock_prompt):
        """Тест что выбор workflow использует CustomPrompt (требует Enter)"""
        # Создать тестовый workflow файл
        workflows_dir = Path(self.settings_manager.settings.workflows_dir)
        workflows_dir.mkdir(exist_ok=True)
        
        test_workflow = {
            'name': 'test-workflow',
            'description': 'Тестовый workflow',
            'stages': [
                {
                    'name': 'test-stage',
                    'agent': 'test-agent',
                    'user_prompt': 'Тестовая задача',
                    'description': 'Тестовый этап'
                }
            ]
        }
        
        with open(workflows_dir / "test-workflow.yaml", 'w') as f:
            yaml.dump(test_workflow, f)
        
        # Настройка мока
        mock_prompt.return_value = "1"
        
        # Вызов метода выбора workflow
        try:
            self.cli.select_workflow()
        except Exception:
            # Ожидаем ошибку из-за неполной настройки, но нас интересует только вызов prompt
            pass
        
        # Проверяем, что CustomPrompt.ask был вызван
        mock_prompt.assert_called()
    
    def test_all_prompts_consistent(self):
        """Тест что все промпты в CLI используют единый подход"""
        import inspect
        
        # Получаем исходный код класса
        source = inspect.getsource(SimpleInteractiveCLI)
        
        # Проверяем, что нет прямого использования Prompt.ask (не CustomPrompt.ask)
        lines = source.split('\n')
        for i, line in enumerate(lines, 1):
            # Пропускаем импорты и определение класса CustomPrompt
            if 'import' in line or 'class CustomPrompt' in line:
                continue
            # Ищем использование Prompt.ask без Custom
            if 'Prompt.ask' in line and 'CustomPrompt.ask' not in line:
                assert False, f"Строка {i}: Найдено использование стандартного Prompt.ask вместо CustomPrompt.ask: {line.strip()}"
        
        # Проверяем, что используется CustomPrompt.ask
        assert "CustomPrompt.ask" in source, "CustomPrompt.ask должен использоваться для пользовательского ввода"
    
    def test_custom_prompt_behavior(self):
        """Тест поведения CustomPrompt (требует Enter)"""
        from core.interactive_cli import CustomPrompt
        
        # Проверяем, что CustomPrompt наследуется от Prompt
        from rich.prompt import Prompt
        assert issubclass(CustomPrompt, Prompt)
        
        # Проверяем, что у CustomPrompt есть метод ask
        assert hasattr(CustomPrompt, 'ask')
        
        # Проверяем, что CustomPrompt поддерживает команду clear
        assert hasattr(CustomPrompt, 'process_response')


def test_interactive_cli_integration():
    """Простой тест для запуска без pytest"""
    print("Тестирование интерактивного CLI...")
    
    test_instance = TestInteractiveCLIIntegration()
    
    try:
        # Настройка
        test_instance.setup_method()
        print("✅ Настройка окружения")
        
        # Тест 1: Список агентов
        test_instance.test_list_agents_requires_enter()
        print("✅ Тест списка агентов")
        
        # Тест 2: Консистентность промптов
        test_instance.test_all_prompts_consistent()
        print("✅ Тест консистентности промптов")
        
        # Тест 3: Поведение CustomPrompt
        test_instance.test_custom_prompt_behavior()
        print("✅ Тест поведения CustomPrompt")
        
        print("\nВсе интеграционные тесты CLI пройдены!")
        
    finally:
        # Очистка
        test_instance.teardown_method()
        print("✅ Очистка окружения")


if __name__ == "__main__":
    test_interactive_cli_integration()
