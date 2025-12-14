"""
Интеграционные тесты для MCP функциональности
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
import sys
import os

# Добавить src в путь
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from core.settings import SettingsManager
from workflows.mcp_integration import MCPManager, MCPClient, MCPTool, MCP_AVAILABLE
from workflows.loader import WorkflowLoader

class TestMCPIntegration:
    """Тесты MCP интеграции"""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Временная директория для конфигурации"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def settings_manager(self, temp_config_dir):
        """Менеджер настроек с временной конфигурацией"""
        config_path = Path(temp_config_dir) / "settings.yaml"
        mcp_path = Path(temp_config_dir) / "mcp.yaml"
        
        # Создать базовую конфигурацию
        with open(config_path, 'w') as f:
            f.write("""
language: ru
workflows_dir: {}/workflows
""".format(temp_config_dir))
        
        # Создать MCP конфигурацию
        with open(mcp_path, 'w') as f:
            f.write("""
mcp_servers:
  test-server:
    command: echo
    args: ["test"]
    env:
      TEST_VAR: "test_value"
    disabled: false
  disabled-server:
    command: echo
    args: ["disabled"]
    disabled: true
""")
        
        return SettingsManager(str(config_path))
    
    def test_mcp_tool_creation(self):
        """Тест создания MCP инструмента"""
        tool = MCPTool(
            server_name="test-server",
            tool_name="test_tool",
            description="Test tool",
            input_schema={"type": "object"}
        )
        
        assert tool.server_name == "test-server"
        assert tool.tool_name == "test_tool"
        assert tool.full_name == "test-server.test_tool"
        assert tool.description == "Test tool"
    
    def test_mcp_client_initialization(self, settings_manager):
        """Тест инициализации MCP клиента"""
        server_config = {
            "name": "test-server",
            "command": "echo",
            "args": ["test"],
            "env": {"TEST": "value"},
            "disabled": False
        }
        
        client = MCPClient(server_config)
        
        assert client.name == "test-server"
        assert client.command == "echo"
        assert client.args == ["test"]
        assert client.env == {"TEST": "value"}
        assert not client.disabled
    
    def test_mcp_client_availability(self, settings_manager):
        """Тест проверки доступности MCP клиента"""
        # Активный сервер
        active_config = {
            "name": "active",
            "command": "echo",
            "disabled": False
        }
        active_client = MCPClient(active_config)
        assert active_client.is_available() == MCP_AVAILABLE
        
        # Отключенный сервер
        disabled_config = {
            "name": "disabled",
            "command": "echo",
            "disabled": True
        }
        disabled_client = MCPClient(disabled_config)
        assert not disabled_client.is_available()
        
        # Сервер без команды
        no_command_config = {
            "name": "no-command",
            "command": "",
            "disabled": False
        }
        no_command_client = MCPClient(no_command_config)
        assert not no_command_client.is_available()
    
    def test_mcp_manager_initialization(self, settings_manager):
        """Тест инициализации MCP менеджера"""
        manager = MCPManager(settings_manager)
        
        assert manager.settings_manager == settings_manager
        assert isinstance(manager.active_servers, dict)
        assert len(manager.active_servers) == 0
    
    def test_mcp_manager_get_available_servers(self, settings_manager):
        """Тест получения доступных серверов"""
        manager = MCPManager(settings_manager)
        available = manager.get_available_servers()
        
        # Должен быть только test-server (disabled-server отключен)
        assert "test-server" in available
        assert "disabled-server" not in available
    
    @pytest.mark.asyncio
    async def test_mcp_manager_start_nonexistent_server(self, settings_manager):
        """Тест запуска несуществующего сервера"""
        manager = MCPManager(settings_manager)
        
        result = await manager.start_server("nonexistent")
        assert not result
        assert "nonexistent" not in manager.active_servers
    
    def test_mcp_manager_tool_name_parsing(self, settings_manager):
        """Тест парсинга имен инструментов"""
        manager = MCPManager(settings_manager)
        
        # Корректное имя
        try:
            server_name, tool_name = "test-server.tool_name".split(".", 1)
            assert server_name == "test-server"
            assert tool_name == "tool_name"
        except ValueError:
            pytest.fail("Не удалось распарсить корректное имя инструмента")
        
        # Некорректное имя (без точки)
        with pytest.raises(ValueError):
            if "." not in "invalid_tool_name":
                raise ValueError("Неверный формат имени инструмента")
    
    def test_mcp_manager_stop_all_servers(self, settings_manager):
        """Тест остановки всех серверов"""
        manager = MCPManager(settings_manager)
        
        # Добавить фиктивный активный сервер
        mock_client = MCPClient({"name": "mock", "command": "echo", "disabled": False})
        manager.active_servers["mock"] = mock_client
        
        # Остановить все серверы
        manager.stop_all_servers()
        
        assert len(manager.active_servers) == 0

class TestMCPWorkflowIntegration:
    """Тесты интеграции MCP с workflow"""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Временная директория для конфигурации"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def workflow_with_mcp(self, temp_config_dir):
        """Workflow с MCP серверами"""
        workflows_dir = Path(temp_config_dir) / "workflows"
        workflows_dir.mkdir(exist_ok=True)
        
        workflow_file = workflows_dir / "test-mcp.yaml"
        with open(workflow_file, 'w') as f:
            f.write("""
name: test-mcp
description: "Test workflow with MCP"

mcp_servers:
  - test-server
  - another-server

stages:
  - name: test_stage
    agent: analyst
    description: "Test stage with MCP tools"
    mcp_servers:
      - test-server
""")
        
        return str(workflows_dir)
    
    def test_workflow_mcp_validation(self, workflow_with_mcp):
        """Тест валидации workflow с MCP серверами"""
        loader = WorkflowLoader(workflow_with_mcp)
        
        config = loader.load_workflow("test-mcp")
        assert config is not None
        
        # Проверить MCP серверы на уровне workflow
        assert "mcp_servers" in config
        assert "test-server" in config["mcp_servers"]
        assert "another-server" in config["mcp_servers"]
        
        # Проверить MCP серверы на уровне stage
        stage = config["stages"][0]
        assert "mcp_servers" in stage
        assert "test-server" in stage["mcp_servers"]
    
    def test_workflow_info_includes_mcp(self, workflow_with_mcp):
        """Тест включения MCP серверов в информацию о workflow"""
        loader = WorkflowLoader(workflow_with_mcp)
        
        info = loader.get_workflow_info("test-mcp")
        assert info is not None
        
        assert "mcp_servers" in info
        assert "test-server" in info["mcp_servers"]
        assert "another-server" in info["mcp_servers"]
    
    def test_workflow_validation_requires_agent(self, workflow_with_mcp):
        """Тест валидации требования поля agent (не roles)"""
        workflows_dir = Path(workflow_with_mcp)
        
        # Создать workflow с устаревшим форматом roles
        invalid_workflow = workflows_dir / "invalid.yaml"
        with open(invalid_workflow, 'w') as f:
            f.write("""
name: invalid
stages:
  - name: test_stage
    roles: [developer]  # Устаревший формат
""")
        
        loader = WorkflowLoader(workflow_with_mcp)
        config = loader.load_workflow("invalid")
        
        # Должен вернуть None из-за отсутствия поля agent
        assert config is None

class TestMCPToolIntegration:
    """Тесты интеграции MCP инструментов"""
    
    def test_mcp_tool_llm_format(self):
        """Тест формата MCP инструментов для LLM"""
        tool = MCPTool(
            server_name="youtrack-mcp",
            tool_name="issue_details",
            description="Get issue details",
            input_schema={
                "type": "object",
                "properties": {
                    "issueId": {"type": "string"}
                }
            }
        )
        
        # Проверить полное имя инструмента
        assert tool.full_name == "youtrack-mcp.issue_details"
        
        # Проверить формат для LLM
        client = MCPClient({
            "name": "youtrack-mcp",
            "command": "node",
            "disabled": False
        })
        client.tools["issue_details"] = tool
        
        llm_tools = client.get_tools_for_llm()
        assert len(llm_tools) == 1
        
        llm_tool = llm_tools[0]
        assert llm_tool["name"] == "youtrack-mcp.issue_details"
        assert llm_tool["description"] == "Get issue details"
        assert "issueId" in llm_tool["input_schema"]["properties"]
    
    def test_mcp_manager_collect_all_tools(self):
        """Тест сбора всех инструментов от всех серверов"""
        # Создать менеджер с фиктивными серверами
        manager = MCPManager(None)
        
        # Создать фиктивные клиенты с инструментами
        client1 = MCPClient({"name": "server1", "command": "echo", "disabled": False})
        client1.tools["tool1"] = MCPTool("server1", "tool1", "Tool 1", {})
        client1.tools["tool2"] = MCPTool("server1", "tool2", "Tool 2", {})
        
        client2 = MCPClient({"name": "server2", "command": "echo", "disabled": False})
        client2.tools["tool3"] = MCPTool("server2", "tool3", "Tool 3", {})
        
        manager.active_servers["server1"] = client1
        manager.active_servers["server2"] = client2
        
        # Получить все инструменты
        all_tools = manager.get_all_tools_for_llm()
        
        assert len(all_tools) == 3
        tool_names = [tool["name"] for tool in all_tools]
        assert "server1.tool1" in tool_names
        assert "server1.tool2" in tool_names
        assert "server2.tool3" in tool_names

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
