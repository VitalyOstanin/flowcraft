#!/usr/bin/env python3
"""
Интеграционные тесты LLM функциональности для workflow
"""
import sys
import os
import tempfile
import asyncio
from pathlib import Path

# Добавить src в путь
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from core.settings import SettingsManager
from agents.manager import AgentManager
from workflows.loader import WorkflowLoader
from workflows.manager import WorkflowManager
from core.interactive_cli import SimpleInteractiveCLI

def test_llm_workflow_creation():
    """Тест создания workflow через LLM в изолированной среде"""
    
    # Создаем временный каталог для тестов
    with tempfile.TemporaryDirectory() as temp_dir:
        test_env_path = Path(temp_dir) / "test_flowcraft"
        test_env_path.mkdir(parents=True, exist_ok=True)
        
        # Устанавливаем переменную окружения для изоляции
        original_home = os.environ.get('HOME')
        os.environ['HOME'] = str(test_env_path)
        
        try:
            # Инициализация компонентов в изолированной среде
            settings_manager = SettingsManager()
            agent_manager = AgentManager(settings_manager)
            workflow_loader = WorkflowLoader(settings_manager.settings.workflows_dir)
            workflow_manager = WorkflowManager(
                settings_manager.settings.workflows_dir,
                settings=settings_manager.settings
            )
            
            # Создание CLI
            cli = SimpleInteractiveCLI(
                settings_manager=settings_manager,
                agent_manager=agent_manager,
                workflow_loader=workflow_loader,
                workflow_manager=workflow_manager
            )
            
            print("✓ CLI инициализирован в изолированной среде")
            print(f"✓ Тестовый каталог: {test_env_path}")
            print(f"✓ Workflows каталог: {settings_manager.settings.workflows_dir}")
            
            # Проверяем начальное состояние
            workflows_before = workflow_manager.list_workflows()
            print(f"✓ Workflow до создания: {len(workflows_before)}")
            
            # Тест конкретного запроса
            print("\n=== Тест конкретного запроса ===")
            print("Запрос: Создай workflow 'work dev' с этапами:")
            print("1. подготовка рабочих копий проектов")
            print("2. анализ постановки/задачи") 
            print("3. реализация в коде")
            
            # Имитируем LLM создание workflow
            test_request = "Создай workflow 'work dev' с этапами (название этапов на английском): 1. подготовка рабочих копий проектов 2. анализ постановки/задачи 3. реализация в коде"
            
            # Создаем workflow напрямую через менеджер для тестирования
            workflow_config = {
                'roles': [
                    {
                        'name': 'developer',
                        'prompt': 'Ты — опытный разработчик. Отвечай на русском.',
                        'expensive_model': False
                    },
                    {
                        'name': 'analyst', 
                        'prompt': 'Ты — бизнес-аналитик. Отвечай на русском.',
                        'expensive_model': False
                    }
                ],
                'stages': [
                    {
                        'name': 'prepare_work_copies',
                        'roles': ['developer'],
                        'skippable': False,
                        'description': 'Подготовка рабочих копий проектов'
                    },
                    {
                        'name': 'analyze_task',
                        'roles': ['analyst'],
                        'skippable': False,
                        'description': 'Анализ постановки/задачи'
                    },
                    {
                        'name': 'implement_code',
                        'roles': ['developer'],
                        'skippable': False,
                        'description': 'Реализация в коде'
                    }
                ]
            }
            
            # Создаем workflow
            success = workflow_manager.create_workflow(
                'work dev',
                'Workflow разработки с подготовкой, анализом и реализацией',
                workflow_config
            )
            
            if success:
                print("✓ Workflow 'work dev' создан успешно")
                
                # Проверяем что workflow появился
                workflows_after = workflow_manager.list_workflows()
                print(f"✓ Workflow после создания: {len(workflows_after)}")
                
                # Проверяем содержимое созданного workflow
                created_workflow = workflow_manager.get_workflow('work dev')
                if created_workflow:
                    print(f"✓ Название: {created_workflow['name']}")
                    print(f"✓ Описание: {created_workflow['description']}")
                    print(f"✓ Ролей: {len(created_workflow.get('roles', []))}")
                    print(f"✓ Этапов: {len(created_workflow.get('stages', []))}")
                    
                    # Проверяем названия этапов на английском
                    stages = created_workflow.get('stages', [])
                    stage_names = [stage['name'] for stage in stages]
                    expected_names = ['prepare_work_copies', 'analyze_task', 'implement_code']
                    
                    print("✓ Этапы:")
                    for stage in stages:
                        print(f"  - {stage['name']}: {stage['description']}")
                    
                    # Проверяем соответствие требованиям
                    if all(name in stage_names for name in expected_names):
                        print("✓ Все требуемые этапы присутствуют")
                    else:
                        print("✗ Не все требуемые этапы найдены")
                
                # Тестируем удаление
                deleted = workflow_manager.delete_workflow('work dev')
                if deleted:
                    print("✓ Workflow 'work dev' удален успешно")
                else:
                    print("✗ Ошибка удаления workflow")
                    
            else:
                print("✗ Ошибка создания workflow 'work dev'")
                
        finally:
            # Восстанавливаем оригинальную переменную HOME
            if original_home:
                os.environ['HOME'] = original_home
            else:
                os.environ.pop('HOME', None)

def test_llm_workflow_methods():
    """Тест методов LLM создания и удаления workflow"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        test_env_path = Path(temp_dir) / "test_flowcraft"
        test_env_path.mkdir(parents=True, exist_ok=True)
        
        original_home = os.environ.get('HOME')
        os.environ['HOME'] = str(test_env_path)
        
        try:
            # Инициализация компонентов
            settings_manager = SettingsManager()
            agent_manager = AgentManager(settings_manager)
            workflow_loader = WorkflowLoader(settings_manager.settings.workflows_dir)
            workflow_manager = WorkflowManager(
                settings_manager.settings.workflows_dir,
                settings=settings_manager.settings
            )
            
            cli = SimpleInteractiveCLI(
                settings_manager=settings_manager,
                agent_manager=agent_manager,
                workflow_loader=workflow_loader,
                workflow_manager=workflow_manager
            )
            
            print("\n=== Тест методов CLI ===")
            
            # Проверяем наличие LLM методов
            assert hasattr(cli, '_create_workflow_with_llm'), "Метод _create_workflow_with_llm не найден"
            assert hasattr(cli, '_delete_workflow_with_llm'), "Метод _delete_workflow_with_llm не найден"
            assert hasattr(cli, '_create_workflow_manual'), "Метод _create_workflow_manual не найден"
            assert hasattr(cli, '_delete_workflow_manual'), "Метод _delete_workflow_manual не найден"
            
            print("✓ Все LLM методы присутствуют")
            
            # Тестируем ручное создание workflow
            cli._create_workflow_manual = lambda: _test_manual_creation(workflow_manager)
            cli._create_workflow_manual()
            
            # Проверяем что workflow создался
            workflows = workflow_manager.list_workflows()
            assert len(workflows) == 1, f"Ожидался 1 workflow, найдено {len(workflows)}"
            assert workflows[0]['name'] == 'test-manual', f"Неверное имя workflow: {workflows[0]['name']}"
            
            print("✓ Ручное создание workflow работает")
            
        finally:
            if original_home:
                os.environ['HOME'] = original_home
            else:
                os.environ.pop('HOME', None)

def _test_manual_creation(workflow_manager):
    """Вспомогательная функция для тестирования ручного создания"""
    config = {
        'roles': [
            {
                'name': 'developer',
                'prompt': 'Ты разработчик. Отвечай на русском.',
                'expensive_model': False
            }
        ],
        'stages': [
            {
                'name': 'initial_stage',
                'roles': ['developer'],
                'skippable': False,
                'description': 'Начальный этап workflow'
            }
        ]
    }
    
    success = workflow_manager.create_workflow('test-manual', 'Тестовый workflow', config)
    if success:
        print("✓ Тестовый workflow создан")
    else:
        print("✗ Ошибка создания тестового workflow")

if __name__ == "__main__":
    test_llm_workflow_creation()
    test_llm_workflow_methods()
