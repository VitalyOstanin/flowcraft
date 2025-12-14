"""
Тесты для менеджера этапов workflow
"""

import pytest
import tempfile
import os
from pathlib import Path
import yaml

from src.workflows.stage_manager import StageManager, StageCommandProcessor, WorkflowStage
from src.core.settings import Settings, LLMConfig


@pytest.fixture
def temp_workflows_dir():
    """Временная директория для workflow"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def settings(temp_workflows_dir):
    """Настройки для тестов"""
    return Settings(
        language="ru",
        llm=LLMConfig(
            cheap_model="test",
            expensive_model="test",
            expensive_stages=[]
        ),
        workflows_dir=temp_workflows_dir,
        mcp_servers=[],
        trust_rules={},
        agents={}
    )


@pytest.fixture
def stage_manager(settings):
    """Менеджер этапов для тестов"""
    return StageManager(settings)


@pytest.fixture
def sample_workflow(temp_workflows_dir):
    """Создать тестовый workflow"""
    workflow_data = {
        "name": "test-workflow",
        "description": "Test workflow",
        "stages": [
            {
                "name": "stage1",
                "description": "First stage",
                "roles": ["developer"],
                "skippable": False,
                "enabled": True
            },
            {
                "name": "stage2", 
                "description": "Second stage",
                "roles": ["tester"],
                "skippable": True,
                "enabled": False
            }
        ]
    }
    
    workflow_path = Path(temp_workflows_dir) / "test-workflow.yaml"
    with open(workflow_path, 'w', encoding='utf-8') as f:
        yaml.dump(workflow_data, f, default_flow_style=False, allow_unicode=True)
    
    return "test-workflow"


class TestStageManager:
    """Тесты StageManager"""
    
    def test_list_stages(self, stage_manager, sample_workflow):
        """Тест получения списка этапов"""
        stages = stage_manager.list_stages(sample_workflow)
        
        assert len(stages) == 2
        assert stages[0].name == "stage1"
        assert stages[0].enabled == True
        assert stages[1].name == "stage2"
        assert stages[1].enabled == False
    
    def test_get_stage(self, stage_manager, sample_workflow):
        """Тест получения этапа по имени"""
        stage = stage_manager.get_stage(sample_workflow, "stage1")
        
        assert stage is not None
        assert stage.name == "stage1"
        assert stage.description == "First stage"
        assert stage.roles == ["developer"]
        
        # Несуществующий этап
        stage = stage_manager.get_stage(sample_workflow, "nonexistent")
        assert stage is None
    
    def test_create_stage(self, stage_manager, sample_workflow):
        """Тест создания нового этапа"""
        new_stage = WorkflowStage(
            name="new_stage",
            description="New test stage",
            roles=["reviewer"],
            skippable=True
        )
        
        result = stage_manager.create_stage(sample_workflow, new_stage)
        assert result == True
        
        # Проверить, что этап создан
        stages = stage_manager.list_stages(sample_workflow)
        assert len(stages) == 3
        
        created_stage = stage_manager.get_stage(sample_workflow, "new_stage")
        assert created_stage is not None
        assert created_stage.name == "new_stage"
        assert created_stage.roles == ["reviewer"]
    
    def test_create_duplicate_stage(self, stage_manager, sample_workflow):
        """Тест создания дублирующего этапа"""
        duplicate_stage = WorkflowStage(
            name="stage1",  # Уже существует
            description="Duplicate stage",
            roles=["developer"]
        )
        
        with pytest.raises(ValueError, match="уже существует"):
            stage_manager.create_stage(sample_workflow, duplicate_stage)
    
    def test_update_stage(self, stage_manager, sample_workflow):
        """Тест обновления этапа"""
        updates = {
            "description": "Updated description",
            "skippable": True
        }
        
        result = stage_manager.update_stage(sample_workflow, "stage1", updates)
        assert result == True
        
        # Проверить обновления
        updated_stage = stage_manager.get_stage(sample_workflow, "stage1")
        assert updated_stage.description == "Updated description"
        assert updated_stage.skippable == True
        assert updated_stage.roles == ["developer"]  # Не изменилось
    
    def test_update_nonexistent_stage(self, stage_manager, sample_workflow):
        """Тест обновления несуществующего этапа"""
        with pytest.raises(ValueError, match="не найден"):
            stage_manager.update_stage(sample_workflow, "nonexistent", {"description": "test"})
    
    def test_delete_stage(self, stage_manager, sample_workflow):
        """Тест удаления этапа"""
        result = stage_manager.delete_stage(sample_workflow, "stage1")
        assert result == True
        
        # Проверить, что этап удален
        stages = stage_manager.list_stages(sample_workflow)
        assert len(stages) == 1
        assert stages[0].name == "stage2"
        
        stage = stage_manager.get_stage(sample_workflow, "stage1")
        assert stage is None
    
    def test_delete_nonexistent_stage(self, stage_manager, sample_workflow):
        """Тест удаления несуществующего этапа"""
        with pytest.raises(ValueError, match="не найден"):
            stage_manager.delete_stage(sample_workflow, "nonexistent")
    
    def test_enable_disable_stage(self, stage_manager, sample_workflow):
        """Тест включения/отключения этапа"""
        # Отключить включенный этап
        result = stage_manager.disable_stage(sample_workflow, "stage1")
        assert result == True
        
        stage = stage_manager.get_stage(sample_workflow, "stage1")
        assert stage.enabled == False
        
        # Включить отключенный этап
        result = stage_manager.enable_stage(sample_workflow, "stage1")
        assert result == True
        
        stage = stage_manager.get_stage(sample_workflow, "stage1")
        assert stage.enabled == True
    
    def test_get_enabled_stages(self, stage_manager, sample_workflow):
        """Тест получения только включенных этапов"""
        enabled_stages = stage_manager.get_enabled_stages(sample_workflow)
        
        assert len(enabled_stages) == 1
        assert enabled_stages[0].name == "stage1"


class TestStageCommandProcessor:
    """Тесты StageCommandProcessor"""
    
    def test_list_stages_command(self, stage_manager, sample_workflow):
        """Тест команды list_stages"""
        processor = StageCommandProcessor(stage_manager)
        
        result = processor.process_command("list_stages", sample_workflow)
        
        assert result["success"] == True
        assert len(result["data"]) == 2
        assert result["data"][0]["name"] == "stage1"
    
    def test_create_stage_command(self, stage_manager, sample_workflow):
        """Тест команды create_stage"""
        processor = StageCommandProcessor(stage_manager)
        
        command = "create_stage name='test_stage' description='Test stage' roles=['developer','tester'] skippable=true"
        result = processor.process_command(command, sample_workflow)
        
        assert result["success"] == True
        assert "создан" in result["message"]
        
        # Проверить, что этап создан
        stage = stage_manager.get_stage(sample_workflow, "test_stage")
        assert stage is not None
        assert stage.roles == ["developer", "tester"]
        assert stage.skippable == True
    
    def test_update_stage_command(self, stage_manager, sample_workflow):
        """Тест команды update_stage"""
        processor = StageCommandProcessor(stage_manager)
        
        command = "update_stage name='stage1' description='Updated via command' skippable=true"
        result = processor.process_command(command, sample_workflow)
        
        assert result["success"] == True
        assert "обновлен" in result["message"]
        
        # Проверить обновления
        stage = stage_manager.get_stage(sample_workflow, "stage1")
        assert stage.description == "Updated via command"
        assert stage.skippable == True
    
    def test_delete_stage_command(self, stage_manager, sample_workflow):
        """Тест команды delete_stage"""
        processor = StageCommandProcessor(stage_manager)
        
        command = "delete_stage name='stage1'"
        result = processor.process_command(command, sample_workflow)
        
        assert result["success"] == True
        assert "удален" in result["message"]
        
        # Проверить удаление
        stage = stage_manager.get_stage(sample_workflow, "stage1")
        assert stage is None
    
    def test_enable_disable_commands(self, stage_manager, sample_workflow):
        """Тест команд enable_stage и disable_stage"""
        processor = StageCommandProcessor(stage_manager)
        
        # Отключить этап
        result = processor.process_command("disable_stage name='stage1'", sample_workflow)
        assert result["success"] == True
        
        stage = stage_manager.get_stage(sample_workflow, "stage1")
        assert stage.enabled == False
        
        # Включить этап
        result = processor.process_command("enable_stage name='stage1'", sample_workflow)
        assert result["success"] == True
        
        stage = stage_manager.get_stage(sample_workflow, "stage1")
        assert stage.enabled == True
    
    def test_invalid_command(self, stage_manager, sample_workflow):
        """Тест неверной команды"""
        processor = StageCommandProcessor(stage_manager)
        
        result = processor.process_command("invalid_command", sample_workflow)
        
        assert result["success"] == False
        assert "Неизвестная команда" in result["message"]
    
    def test_command_with_confirmation(self, stage_manager, sample_workflow):
        """Тест команды с подтверждением"""
        processor = StageCommandProcessor(stage_manager)
        
        # Подтверждение отклонено
        def deny_callback(message):
            return False
        
        result = processor.process_command("list_stages", sample_workflow, deny_callback)
        assert result["success"] == False
        assert "отменена" in result["message"]
        
        # Подтверждение принято
        def accept_callback(message):
            return True
        
        result = processor.process_command("list_stages", sample_workflow, accept_callback)
        assert result["success"] == True
