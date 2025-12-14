"""Тесты для системы команд управления."""

import pytest
from unittest.mock import Mock, AsyncMock

from src.core.commands import CommandParser, CommandHandler, Command, CommandType
from src.core.settings import Settings
from src.agents.manager import AgentManager
from src.mcp.manager import MCPManager


class TestCommandParser:
    """Тесты парсера команд."""

    def test_parse_mcp_command(self):
        """Тест парсинга MCP команды."""
        parser = CommandParser()
        
        command = parser.parse("/mcp start server1")
        
        assert command.type == CommandType.MCP
        assert command.action == "start"
        assert command.args == ["server1"]
        assert command.kwargs == {}

    def test_parse_agent_command_with_kwargs(self):
        """Тест парсинга команды агента с параметрами."""
        parser = CommandParser()
        
        command = parser.parse("/agent create test_agent developer description=Test")
        
        assert command.type == CommandType.AGENT
        assert command.action == "create"
        assert command.args == ["test_agent", "developer"]
        assert command.kwargs == {"description": "Test"}

    def test_parse_help_command(self):
        """Тест парсинга команды помощи."""
        parser = CommandParser()
        
        command = parser.parse("/help mcp")
        
        assert command.type == CommandType.HELP
        assert command.action == "mcp"
        assert command.args == []

    def test_parse_unknown_command(self):
        """Тест парсинга неизвестной команды."""
        parser = CommandParser()
        
        command = parser.parse("unknown command")
        
        assert command.type == CommandType.UNKNOWN
        assert command.args == ["unknown command"]


class TestCommandHandler:
    """Тесты обработчика команд."""

    @pytest.fixture
    def mock_settings(self):
        """Мок настроек."""
        return Mock(spec=Settings)

    @pytest.fixture
    def mock_agent_manager(self):
        """Мок менеджера агентов."""
        return Mock(spec=AgentManager)

    @pytest.fixture
    def mock_mcp_manager(self):
        """Мок MCP менеджера."""
        manager = Mock(spec=MCPManager)
        manager.start_server = AsyncMock(return_value=True)
        manager.stop_server = AsyncMock(return_value=True)
        manager.restart_server = AsyncMock(return_value=True)
        manager.list_servers.return_value = []
        return manager

    @pytest.fixture
    def command_handler(self, mock_settings, mock_agent_manager, mock_mcp_manager):
        """Фикстура обработчика команд."""
        return CommandHandler(mock_settings, mock_agent_manager, mock_mcp_manager)

    @pytest.mark.asyncio
    async def test_handle_mcp_list_command(self, command_handler, mock_mcp_manager):
        """Тест команды списка MCP серверов."""
        mock_server = Mock()
        mock_server.name = "test_server"
        mock_server.status.value = "running"
        mock_mcp_manager.list_servers.return_value = [mock_server]
        
        result = await command_handler.handle_command("/mcp list")
        
        assert "test_server" in result
        assert "running" in result

    @pytest.mark.asyncio
    async def test_handle_mcp_start_command(self, command_handler, mock_mcp_manager):
        """Тест команды запуска MCP сервера."""
        result = await command_handler.handle_command("/mcp start test_server")
        
        mock_mcp_manager.start_server.assert_called_once_with("test_server")
        assert "запущен" in result

    @pytest.mark.asyncio
    async def test_handle_agent_list_command(self, command_handler, mock_agent_manager):
        """Тест команды списка агентов."""
        mock_agent = Mock()
        mock_agent.name = "test_agent"
        mock_agent.role = "developer"
        mock_agent.enabled = True
        mock_agent_manager.list_agents.return_value = [mock_agent]
        
        result = await command_handler.handle_command("/agent list")
        
        assert "test_agent" in result
        assert "developer" in result
        assert "активен" in result

    @pytest.mark.asyncio
    async def test_handle_agent_create_command(self, command_handler, mock_agent_manager):
        """Тест команды создания агента."""
        mock_agent_manager.create_agent.return_value = True
        
        result = await command_handler.handle_command("/agent create test_agent developer")
        
        mock_agent_manager.create_agent.assert_called_once_with(
            name="test_agent",
            role="developer",
            description="Агент test_agent"
        )
        assert "создан" in result

    @pytest.mark.asyncio
    async def test_handle_help_command(self, command_handler):
        """Тест команды помощи."""
        result = await command_handler.handle_command("/help")
        
        assert "Доступные команды" in result
        assert "/mcp" in result
        assert "/agent" in result

    @pytest.mark.asyncio
    async def test_handle_help_topic_command(self, command_handler):
        """Тест команды помощи по теме."""
        result = await command_handler.handle_command("/help mcp")
        
        assert "MCP команды" in result
        assert "/mcp list" in result
        assert "/mcp start" in result

    @pytest.mark.asyncio
    async def test_handle_unknown_command(self, command_handler):
        """Тест обработки неизвестной команды."""
        result = await command_handler.handle_command("unknown")
        
        assert "Неизвестная команда" in result

    @pytest.mark.asyncio
    async def test_handle_mcp_enable_command(self, command_handler, mock_mcp_manager):
        """Тест команды включения MCP сервера для workflow."""
        result = await command_handler.handle_command("/mcp enable server1 workflow1")
        
        mock_mcp_manager.enable_for_workflow.assert_called_once_with("server1", "workflow1")
        assert "включен" in result

    @pytest.mark.asyncio
    async def test_handle_agent_delete_command(self, command_handler, mock_agent_manager):
        """Тест команды удаления агента."""
        mock_agent_manager.delete_agent.return_value = True
        
        result = await command_handler.handle_command("/agent delete test_agent")
        
        mock_agent_manager.delete_agent.assert_called_once_with("test_agent")
        assert "удален" in result

    @pytest.mark.asyncio
    async def test_handle_incomplete_command(self, command_handler):
        """Тест обработки неполной команды."""
        result = await command_handler.handle_command("/mcp start")
        
        assert "Укажите имя сервера" in result
