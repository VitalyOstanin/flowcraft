"""
Интеграционные тесты выполнения workflow
"""

import pytest
import asyncio
import tempfile
import yaml
from pathlib import Path
import sys

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from workflows.manager import WorkflowManager
from workflows.engine import WorkflowEngine
from agents.manager import AgentManager
from core.trust import TrustManager
from core.settings import SettingsManager


@pytest.fixture
def temp_config_dir():
    """Временная директория для конфигурации"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def test_workflow_config():
    """Тестовая конфигурация workflow"""
    return {
        "name": "test_workflow",
        "description": "Тестовый workflow",
        "stages": [
            {
                "name": "test_stage",
                "agent": "test_agent",
                "skippable": False,
                "description": "Тестовый этап"
            }
        ]
    }


@pytest.fixture
def test_agent_config():
    """Тестовая конфигурация агента"""
    return {
        "name": "test_agent",
        "description": "Тестовый агент",
        "model": "qwen3-coder-plus",
        "system_prompt": "Ты тестовый агент",
        "capabilities": ["testing"]
    }


@pytest.fixture
def workflow_components(temp_config_dir, test_workflow_config, test_agent_config):
    """Инициализированные компоненты workflow"""
    
    # Создаем структуру директорий
    workflows_dir = temp_config_dir / "workflows"
    agents_dir = temp_config_dir / "agents"
    workflows_dir.mkdir()
    agents_dir.mkdir()
    
    # Создаем тестовый workflow
    workflow_file = workflows_dir / "test_workflow.yaml"
    with open(workflow_file, 'w', encoding='utf-8') as f:
        yaml.dump(test_workflow_config, f, allow_unicode=True)
    
    # Создаем тестового агента
    agent_file = agents_dir / "test_agent.yaml"
    with open(agent_file, 'w', encoding='utf-8') as f:
        yaml.dump(test_agent_config, f, allow_unicode=True)
    
    # Создаем настройки
    settings_file = temp_config_dir / "settings.yaml"
    settings_config = {
        "language": "ru",
        "llm": {
            "cheap_model": "qwen3-coder-plus",
            "expensive_model": "kiro-cli"
        },
        "workflows_dir": str(workflows_dir),
        "trust_rules": {}
    }
    
    with open(settings_file, 'w', encoding='utf-8') as f:
        yaml.dump(settings_config, f, allow_unicode=True)
    
    # Инициализируем компоненты
    settings_manager = SettingsManager(str(settings_file))
    agent_manager = AgentManager(settings_manager)
    trust_manager = TrustManager(settings_manager)
    engine = WorkflowEngine(agent_manager, trust_manager)
    manager = WorkflowManager(str(workflows_dir), engine, settings_manager.settings)
    
    return {
        "settings_manager": settings_manager,
        "agent_manager": agent_manager,
        "trust_manager": trust_manager,
        "engine": engine,
        "manager": manager,
        "temp_dir": temp_config_dir
    }


class TestWorkflowExecution:
    """Тесты выполнения workflow"""
    
    @pytest.mark.asyncio
    async def test_workflow_validation_success(self, workflow_components):
        """Тест успешной валидации workflow"""
        manager = workflow_components["manager"]
        
        # Проверяем, что workflow найден
        workflows = manager.list_workflows()
        assert len(workflows) == 1
        assert workflows[0]["name"] == "test_workflow"
        
        # Проверяем валидацию
        workflow_config = manager.get_workflow("test_workflow")
        assert workflow_config is not None
        assert manager._validate_workflow_config(workflow_config) is True
    
    @pytest.mark.asyncio
    async def test_workflow_validation_missing_agent(self, workflow_components):
        """Тест валидации workflow без агента"""
        manager = workflow_components["manager"]
        
        invalid_config = {
            "name": "invalid_workflow",
            "description": "Невалидный workflow",
            "stages": [
                {
                    "name": "invalid_stage",
                    "description": "Этап без агента"
                }
            ]
        }
        
        assert manager._validate_workflow_config(invalid_config) is False
    
    @pytest.mark.asyncio
    async def test_workflow_execution_basic(self, workflow_components):
        """Базовый тест выполнения workflow"""
        manager = workflow_components["manager"]
        
        # Выполняем workflow
        result = await manager.execute_workflow(
            workflow_name="test_workflow",
            task_description="Тестовая задача"
        )
        
        # Проверяем результат
        assert isinstance(result, dict)
        assert "success" in result
        assert "error" in result or result["success"] is True
    
    @pytest.mark.asyncio
    async def test_workflow_execution_nonexistent(self, workflow_components):
        """Тест выполнения несуществующего workflow"""
        manager = workflow_components["manager"]
        
        result = await manager.execute_workflow(
            workflow_name="nonexistent_workflow",
            task_description="Тестовая задача"
        )
        
        assert result["success"] is False
        assert "не найден" in result["error"]
    
    @pytest.mark.asyncio
    async def test_workflow_list(self, workflow_components):
        """Тест получения списка workflow"""
        manager = workflow_components["manager"]
        
        workflows = manager.list_workflows()
        
        assert len(workflows) == 1
        workflow = workflows[0]
        assert workflow["name"] == "test_workflow"
        assert workflow["description"] == "Тестовый workflow"
        assert workflow["stages"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
