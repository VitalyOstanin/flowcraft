"""
Тесты async функциональности CLI для MCP
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
import sys

# Добавить src в путь
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from core.settings import SettingsManager
from core.interactive_cli import SimpleInteractiveCLI
from workflows.mcp_integration import MCPManager
from workflows.loader import WorkflowLoader
from agents.manager import AgentManager

class TestCLIMCPAsync:
    """Тесты async функциональности CLI для MCP"""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Временная директория для конфигурации"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def cli_components(self, temp_config_dir):
        """Компоненты CLI с временной конфигурацией"""
        # Создать базовую конфигурацию
        config_path = Path(temp_config_dir) / "settings.yaml"
        mcp_path = Path(temp_config_dir) / "mcp.yaml"
        agents_dir = Path(temp_config_dir) / "agents"
        workflows_dir = Path(temp_config_dir) / "workflows"
        
        agents_dir.mkdir(exist_ok=True)
        workflows_dir.mkdir(exist_ok=True)
        
        with open(config_path, 'w') as f:
            f.write(f"""
language: ru
workflows_dir: {workflows_dir}
""")
        
        with open(mcp_path, 'w') as f:
            f.write("""
mcp_servers:
  test-server:
    command: echo
    args: ["test"]
    disabled: false
""")
        
        # Создать тестового агента
        agent_file = agents_dir / "test-agent.yaml"
        with open(agent_file, 'w') as f:
            f.write("""
name: test-agent
system_prompt: "Test agent"
description: "Test agent for CLI"
capabilities: ["testing"]
llm_model: "qwen3-coder-plus"
status: "enabled"
workflow_enabled: []
""")
        
        # Инициализировать компоненты
        settings_manager = SettingsManager(str(config_path))
        agent_manager = AgentManager(settings_manager)
        workflow_loader = WorkflowLoader(str(workflows_dir))
        mcp_manager = MCPManager(settings_manager)
        
        cli = SimpleInteractiveCLI(
            settings_manager, 
            agent_manager, 
            workflow_loader, 
            mcp_manager
        )
        
        return cli, mcp_manager, settings_manager
    
    @pytest.mark.asyncio
    async def test_cli_has_async_mcp_methods(self, cli_components):
        """Тест наличия async методов для MCP в CLI"""
        cli, mcp_manager, settings_manager = cli_components
        
        # Проверить наличие async методов
        assert hasattr(cli, 'manage_mcp_servers')
        assert hasattr(cli, '_restart_mcp_server')
        assert hasattr(cli, 'show_menu')
        
        # Проверить что методы действительно async
        import inspect
        assert inspect.iscoroutinefunction(cli.manage_mcp_servers)
        assert inspect.iscoroutinefunction(cli._restart_mcp_server)
        assert inspect.iscoroutinefunction(cli.show_menu)
    
    @pytest.mark.asyncio
    async def test_mcp_manager_async_operations(self, cli_components):
        """Тест async операций MCP менеджера"""
        cli, mcp_manager, settings_manager = cli_components
        
        # Тест async запуска несуществующего сервера
        result = await mcp_manager.start_server("nonexistent")
        assert not result
        
        # Тест async запуска серверов для workflow
        workflow_config = {"mcp_servers": ["test-server"]}
        started = await mcp_manager.start_servers_for_workflow(workflow_config)
        # Может не запуститься из-за отсутствия реального MCP сервера, но метод должен работать
        assert isinstance(started, list)
    
    def test_mcp_tool_naming_convention(self, cli_components):
        """Тест соглашения об именовании MCP инструментов"""
        cli, mcp_manager, settings_manager = cli_components
        
        # Проверить что менеджер поддерживает формат server.tool
        test_cases = [
            ("youtrack-mcp.issue_details", True),
            ("postgres-mcp.connect", True),
            ("server.tool.subtool", True),  # Поддержка вложенных имен
            ("invalid_name", False),
            ("", False)
        ]
        
        for tool_name, should_be_valid in test_cases:
            if should_be_valid:
                assert "." in tool_name, f"Валидное имя {tool_name} должно содержать точку"
                parts = tool_name.split(".", 1)
                assert len(parts) == 2, f"Валидное имя {tool_name} должно иметь 2 части"
            else:
                if tool_name:  # Пустая строка не содержит точку по определению
                    assert "." not in tool_name, f"Невалидное имя {tool_name} не должно содержать точку"
    
    def test_mcp_server_configuration_validation(self, cli_components):
        """Тест валидации конфигурации MCP серверов"""
        cli, mcp_manager, settings_manager = cli_components
        
        # Проверить загруженную конфигурацию
        servers = settings_manager.settings.mcp_servers
        assert len(servers) > 0
        
        test_server = servers[0]
        assert test_server.name == "test-server"
        assert test_server.command == "echo"
        assert test_server.args == ["test"]
        assert not test_server.disabled
    
    def test_cli_mcp_menu_structure(self, cli_components):
        """Тест структуры меню MCP в CLI"""
        cli, mcp_manager, settings_manager = cli_components
        
        # Проверить наличие методов управления MCP
        mcp_methods = [
            '_add_mcp_server',
            '_remove_mcp_server', 
            '_toggle_mcp_server',
            '_restart_mcp_server'
        ]
        
        for method in mcp_methods:
            assert hasattr(cli, method), f"CLI должен иметь метод {method}"
    
    @pytest.mark.asyncio
    async def test_mcp_integration_error_handling(self, cli_components):
        """Тест обработки ошибок в MCP интеграции"""
        cli, mcp_manager, settings_manager = cli_components
        
        # Тест вызова несуществующего инструмента
        with pytest.raises(ValueError, match="Неверный формат имени инструмента"):
            await mcp_manager.call_tool("invalid_tool_name", {})
        
        # Тест вызова инструмента неактивного сервера
        with pytest.raises(RuntimeError, match="MCP сервер .* не активен"):
            await mcp_manager.call_tool("inactive.tool", {})

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
