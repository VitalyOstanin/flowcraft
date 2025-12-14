"""
Тесты для менеджера workflow
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from workflows.manager import WorkflowManager

class TestWorkflowManager:
    
    @pytest.fixture
    def temp_dir(self):
        """Временная директория для тестов"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def workflow_manager(self, temp_dir):
        """Менеджер workflow для тестов"""
        return WorkflowManager(temp_dir)
    
    @pytest.fixture
    def sample_workflow(self, temp_dir):
        """Создать тестовый workflow"""
        workflow_config = {
            'name': 'test-workflow',
            'description': 'Тестовый workflow',
            'roles': [
                {'name': 'developer', 'prompt': 'Ты разработчик'}
            ],
            'stages': [
                {'name': 'analyze', 'roles': ['developer']}
            ]
        }
        
        workflow_file = Path(temp_dir) / "test-workflow.yaml"
        with open(workflow_file, 'w', encoding='utf-8') as f:
            yaml.dump(workflow_config, f, allow_unicode=True)
        
        return workflow_config
    
    def test_list_empty_workflows(self, workflow_manager):
        """Тест списка пустых workflow"""
        workflows = workflow_manager.list_workflows()
        assert workflows == []
    
    def test_list_workflows(self, workflow_manager, sample_workflow):
        """Тест списка workflow"""
        workflows = workflow_manager.list_workflows()
        assert len(workflows) == 1
        assert workflows[0]['name'] == 'test-workflow'
        assert workflows[0]['description'] == 'Тестовый workflow'
    
    def test_create_workflow(self, workflow_manager):
        """Тест создания workflow"""
        config = {
            'roles': [{'name': 'dev', 'prompt': 'test'}],
            'stages': [{'name': 'stage1', 'roles': ['dev']}]
        }
        
        result = workflow_manager.create_workflow('new-workflow', 'Новый workflow', config)
        assert result is True
        
        workflows = workflow_manager.list_workflows()
        assert len(workflows) == 1
        assert workflows[0]['name'] == 'new-workflow'
    
    def test_create_duplicate_workflow(self, workflow_manager, sample_workflow):
        """Тест создания дублирующего workflow"""
        config = {'roles': [], 'stages': []}
        result = workflow_manager.create_workflow('test-workflow', 'Дубликат', config)
        assert result is False
    
    def test_delete_workflow(self, workflow_manager, sample_workflow):
        """Тест удаления workflow"""
        result = workflow_manager.delete_workflow('test-workflow')
        assert result is True
        
        workflows = workflow_manager.list_workflows()
        assert len(workflows) == 0
    
    def test_delete_nonexistent_workflow(self, workflow_manager):
        """Тест удаления несуществующего workflow"""
        result = workflow_manager.delete_workflow('nonexistent')
        assert result is False
    
    def test_get_workflow(self, workflow_manager, sample_workflow):
        """Тест получения конфигурации workflow"""
        config = workflow_manager.get_workflow('test-workflow')
        assert config is not None
        assert config['name'] == 'test-workflow'
        assert config['description'] == 'Тестовый workflow'
    
    def test_get_nonexistent_workflow(self, workflow_manager):
        """Тест получения несуществующего workflow"""
        config = workflow_manager.get_workflow('nonexistent')
        assert config is None
    
    def test_select_workflow_by_description_success(self, workflow_manager, sample_workflow):
        """Тест успешного выбора workflow через LLM"""
        # Мок LLM провайдера
        mock_llm = Mock()
        mock_llm.generate.return_value = "test-workflow"
        
        selected = workflow_manager.select_workflow_by_description("исправить баг", mock_llm)
        assert selected == "test-workflow"
        
        # Проверить что LLM был вызван
        mock_llm.generate.assert_called_once()
    
    def test_select_workflow_by_description_not_found(self, workflow_manager, sample_workflow):
        """Тест выбора workflow когда LLM возвращает несуществующий"""
        mock_llm = Mock()
        mock_llm.generate.return_value = "nonexistent-workflow"
        
        selected = workflow_manager.select_workflow_by_description("что-то", mock_llm)
        assert selected is None
    
    def test_select_workflow_by_description_llm_error(self, workflow_manager, sample_workflow):
        """Тест выбора workflow при ошибке LLM"""
        mock_llm = Mock()
        mock_llm.generate.side_effect = Exception("LLM error")
        
        selected = workflow_manager.select_workflow_by_description("что-то", mock_llm)
        assert selected is None
    
    def test_select_workflow_no_workflows(self, workflow_manager):
        """Тест выбора workflow когда нет доступных"""
        mock_llm = Mock()
        
        selected = workflow_manager.select_workflow_by_description("что-то", mock_llm)
        assert selected is None
        
        # LLM не должен вызываться
        mock_llm.generate.assert_not_called()

if __name__ == '__main__':
    pytest.main([__file__])
