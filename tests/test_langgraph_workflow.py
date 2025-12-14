"""
Тесты для LangGraph workflow системы.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from pathlib import Path

from src.workflows.state import WorkflowState, AgentState, create_initial_state
from src.workflows.nodes import StartNode, EndNode, AgentNode
from src.workflows.engine import WorkflowEngine
from src.workflows.subgraphs.common import CodeAnalysisSubgraph
from src.workflows.subgraphs.registry import SubgraphRegistry


class TestWorkflowState:
    """Тесты состояния workflow."""
    
    def test_create_initial_state(self):
        """Тест создания начального состояния."""
        
        state = create_initial_state(
            task_description="Тестовая задача",
            workflow_name="test_workflow"
        )
        
        assert state["context"]["task_description"] == "Тестовая задача"
        assert state["context"]["metadata"]["workflow_name"] == "test_workflow"
        assert state["current_node"] == "start"
        assert not state["finished"]
        assert len(state["messages"]) == 1
    
    def test_workflow_context(self):
        """Тест контекста workflow."""
        
        context = {
            "task_description": "Тест",
            "current_stage": "test_stage",
            "completed_stages": [],
            "stage_outputs": {}
        }
        
        assert context["task_description"] == "Тест"
        assert context["current_stage"] == "test_stage"
        assert context["completed_stages"] == []
        assert context["stage_outputs"] == {}
    
    def test_agent_state(self):
        """Тест состояния агента."""
        
        agent = AgentState(
            name="test_agent",
            role="developer",
            capabilities=["coding", "testing"]
        )
        
        assert agent.name == "test_agent"
        assert agent.role == "developer"
        assert agent.capabilities == ["coding", "testing"]
        assert agent.llm_model == "qwen3-coder-plus"


class TestWorkflowNodes:
    """Тесты узлов workflow."""
    
    @pytest.mark.asyncio
    async def test_start_node(self):
        """Тест стартового узла."""
        
        node = StartNode()
        state = create_initial_state("Тест", "test_workflow")
        
        result = await node.execute(state)
        
        assert result["current_node"] == "start"
        assert len(result["messages"]) == 2  # Исходное + системное сообщение
    
    @pytest.mark.asyncio
    async def test_end_node(self):
        """Тест финального узла."""
        
        node = EndNode()
        state = create_initial_state("Тест", "test_workflow")
        
        result = await node.execute(state)
        
        assert result["current_node"] == "end"
        assert result["finished"]
        assert result["result"] is not None
        assert result["result"]["success"]
    
    @pytest.mark.asyncio
    async def test_agent_node(self):
        """Тест узла агента."""
        
        # Мокаем AgentManager
        mock_agent_manager = Mock()
        
        stage_config = {
            "description": "Тестовый stage",
            "roles": [{"name": "developer", "prompt": "Ты разработчик"}]
        }
        
        node = AgentNode(
            name="test_stage",
            agent_role="developer",
            stage_config=stage_config,
            agent_manager=mock_agent_manager
        )
        
        state = create_initial_state("Тест", "test_workflow")
        
        result = await node.execute(state)
        
        assert result["current_node"] == "test_stage"
        # Проверяем, что результат добавлен в stage_outputs
        assert "test_stage" in result["context"]["stage_outputs"]


class TestSubgraphs:
    """Тесты подграфов."""
    
    def test_code_analysis_subgraph(self):
        """Тест подграфа анализа кода."""
        
        subgraph = CodeAnalysisSubgraph()
        
        assert subgraph.name == "code_analysis"
        assert "Анализ кода" in subgraph.description
        
        # Проверяем узлы
        nodes = subgraph.define_nodes()
        assert "analyze_structure" in nodes
        assert "check_quality" in nodes
        assert "identify_issues" in nodes
        
        # Проверяем связи
        edges = subgraph.define_edges()
        assert ("analyze_structure", "check_quality") in edges
        assert ("check_quality", "identify_issues") in edges
        
        # Проверяем требования
        requirements = subgraph.get_input_requirements()
        assert "code_path" in requirements
        assert "project_type" in requirements
        
        # Проверяем выходы
        outputs = subgraph.get_output_keys()
        assert "structure_analysis" in outputs
        assert "quality_report" in outputs
        assert "identified_issues" in outputs
    
    def test_subgraph_validation(self):
        """Тест валидации подграфа."""
        
        subgraph = CodeAnalysisSubgraph()
        
        # Создаем состояние с необходимыми входными данными
        state = create_initial_state("Тест", "test_workflow")
        state["context"]["stage_outputs"]["code_path"] = "/test/path"
        state["context"]["stage_outputs"]["project_type"] = "python"
        
        assert subgraph.validate_inputs(state)
        
        # Тест без необходимых данных
        empty_state = create_initial_state("Тест", "test_workflow")
        assert not subgraph.validate_inputs(empty_state)


class TestSubgraphRegistry:
    """Тесты реестра подграфов."""
    
    def test_registry_creation(self, tmp_path):
        """Тест создания реестра."""
        
        registry = SubgraphRegistry(str(tmp_path))
        
        assert registry.registry_dir == tmp_path
        assert registry.registry_dir.exists()
    
    def test_subgraph_registration(self, tmp_path):
        """Тест регистрации подграфа."""
        
        registry = SubgraphRegistry(str(tmp_path))
        subgraph = CodeAnalysisSubgraph()
        
        registry.register_subgraph(subgraph)
        
        assert subgraph.name in registry.list_subgraphs()
        assert registry.get_subgraph(subgraph.name) == subgraph
    
    def test_subgraph_search(self, tmp_path):
        """Тест поиска подграфов."""
        
        registry = SubgraphRegistry(str(tmp_path))
        subgraph = CodeAnalysisSubgraph()
        registry.register_subgraph(subgraph)
        
        # Поиск по входным требованиям
        results = registry.search_subgraphs(input_requirements=["code_path"])
        assert len(results) == 1
        assert results[0].name == subgraph.name
        
        # Поиск по выходным ключам
        results = registry.search_subgraphs(output_keys=["quality_report"])
        assert len(results) == 1
        assert results[0].name == subgraph.name
        
        # Поиск по ключевым словам
        results = registry.search_subgraphs(description_keywords=["анализ"])
        assert len(results) == 1
        assert results[0].name == subgraph.name


class TestWorkflowEngine:
    """Тесты движка workflow."""
    
    def test_engine_creation(self):
        """Тест создания движка."""
        
        mock_agent_manager = Mock()
        mock_trust_manager = Mock()
        
        engine = WorkflowEngine(
            agent_manager=mock_agent_manager,
            trust_manager=mock_trust_manager
        )
        
        assert engine.agent_manager == mock_agent_manager
        assert engine.trust_manager == mock_trust_manager
        assert engine.checkpointer is not None
    
    @pytest.mark.asyncio
    async def test_simple_workflow_execution(self):
        """Тест выполнения простого workflow."""
        
        mock_agent_manager = Mock()
        mock_trust_manager = Mock()
        
        engine = WorkflowEngine(
            agent_manager=mock_agent_manager,
            trust_manager=mock_trust_manager
        )
        
        # Простая конфигурация workflow
        workflow_config = {
            "name": "test_workflow",
            "description": "Тестовый workflow",
            "stages": []  # Пустой workflow (только start -> end)
        }
        
        result = await engine.execute_workflow(
            workflow_config=workflow_config,
            task_description="Тестовая задача"
        )
        
        assert result["success"]
        assert result["completed_stages"] == []
        assert result["failed_stages"] == []


class TestWorkflowIntegration:
    """Интеграционные тесты workflow системы."""
    
    @pytest.mark.asyncio
    async def test_full_workflow_cycle(self, tmp_path):
        """Тест полного цикла workflow."""
        
        # Создаем временную директорию для workflow
        workflows_dir = tmp_path / "workflows"
        workflows_dir.mkdir()
        
        # Создаем тестовый workflow файл
        workflow_file = workflows_dir / "test.yaml"
        workflow_content = """
name: test
description: "Тестовый workflow"
stages:
  - name: test_stage
    roles: [developer]
    description: "Тестовый этап"
"""
        workflow_file.write_text(workflow_content)
        
        # Инициализируем компоненты
        mock_agent_manager = Mock()
        mock_trust_manager = Mock()
        
        from src.workflows.manager import WorkflowManager
        
        engine = WorkflowEngine(
            agent_manager=mock_agent_manager,
            trust_manager=mock_trust_manager
        )
        
        manager = WorkflowManager(
            workflows_dir=str(workflows_dir),
            workflow_engine=engine
        )
        
        # Проверяем загрузку workflow
        workflows = manager.list_workflows()
        assert len(workflows) == 1
        assert workflows[0]["name"] == "test"
        
        # Проверяем получение конфигурации
        config = manager.get_workflow("test")
        assert config is not None
        assert config["name"] == "test"
        
        # Тест валидации
        assert manager._validate_workflow_config(config)


if __name__ == "__main__":
    pytest.main([__file__])
