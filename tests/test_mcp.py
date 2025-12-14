"""Тесты для MCP компонентов."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock

from src.mcp.manager import MCPManager, MCPServer, MCPServerStatus
from src.mcp.client import MCPClient, MCPClientManager
from src.core.settings import Settings


@pytest.fixture
def mock_settings():
    """Мок настроек."""
    settings = Mock(spec=Settings)
    settings.mcp_servers = [
        {
            "name": "test_server",
            "command": ["python", "-m", "test_server"],
            "enabled_for_workflows": ["bug-fix"]
        }
    ]
    return settings


@pytest.fixture
def mcp_manager(mock_settings):
    """Фикстура MCP менеджера."""
    return MCPManager(mock_settings)


class TestMCPManager:
    """Тесты MCP менеджера."""

    def test_load_servers(self, mcp_manager):
        """Тест загрузки серверов."""
        assert "test_server" in mcp_manager.servers
        server = mcp_manager.servers["test_server"]
        assert server.name == "test_server"
        assert server.command == ["python", "-m", "test_server"]
        assert "bug-fix" in server.enabled_for_workflows

    @pytest.mark.asyncio
    async def test_start_server_success(self, mcp_manager):
        """Тест успешного запуска сервера."""
        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.poll.return_value = None  # Процесс запущен
            mock_popen.return_value = mock_process
            
            result = await mcp_manager.start_server("test_server")
            
            assert result is True
            assert mcp_manager.servers["test_server"].status == MCPServerStatus.RUNNING

    @pytest.mark.asyncio
    async def test_start_server_failure(self, mcp_manager):
        """Тест неудачного запуска сервера."""
        with patch('subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.poll.return_value = 1  # Процесс завершился с ошибкой
            mock_popen.return_value = mock_process
            
            result = await mcp_manager.start_server("test_server")
            
            assert result is False
            assert mcp_manager.servers["test_server"].status == MCPServerStatus.ERROR

    @pytest.mark.asyncio
    async def test_stop_server(self, mcp_manager):
        """Тест остановки сервера."""
        # Сначала "запустим" сервер
        server = mcp_manager.servers["test_server"]
        server.status = MCPServerStatus.RUNNING
        mock_process = Mock()
        mock_process.poll.return_value = None
        server.process = mock_process
        
        result = await mcp_manager.stop_server("test_server")
        
        assert result is True
        assert server.status == MCPServerStatus.STOPPED
        mock_process.terminate.assert_called_once()

    def test_enable_for_workflow(self, mcp_manager):
        """Тест включения сервера для workflow."""
        mcp_manager.enable_for_workflow("test_server", "feature-dev")
        
        server = mcp_manager.servers["test_server"]
        assert "feature-dev" in server.enabled_for_workflows

    def test_disable_for_workflow(self, mcp_manager):
        """Тест отключения сервера для workflow."""
        mcp_manager.disable_for_workflow("test_server", "bug-fix")
        
        server = mcp_manager.servers["test_server"]
        assert "bug-fix" not in server.enabled_for_workflows

    def test_get_servers_for_workflow(self, mcp_manager):
        """Тест получения серверов для workflow."""
        servers = mcp_manager.get_servers_for_workflow("bug-fix")
        
        assert len(servers) == 1
        assert servers[0].name == "test_server"

    @pytest.mark.asyncio
    async def test_start_workflow_servers(self, mcp_manager):
        """Тест запуска серверов для workflow."""
        with patch.object(mcp_manager, 'start_server', return_value=True) as mock_start:
            result = await mcp_manager.start_workflow_servers("bug-fix")
            
            assert result is True
            mock_start.assert_called_once_with("test_server")


class TestMCPClient:
    """Тесты MCP клиента."""

    @pytest.mark.asyncio
    async def test_connect(self):
        """Тест подключения к серверу."""
        client = MCPClient("test_server")
        
        result = await client.connect()
        
        assert result is True
        assert client.connected is True

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Тест отключения от сервера."""
        client = MCPClient("test_server")
        client.connected = True
        
        await client.disconnect()
        
        assert client.connected is False

    @pytest.mark.asyncio
    async def test_list_tools_not_connected(self):
        """Тест получения инструментов без подключения."""
        client = MCPClient("test_server")
        
        tools = await client.list_tools()
        
        assert tools == []

    @pytest.mark.asyncio
    async def test_call_tool_not_connected(self):
        """Тест вызова инструмента без подключения."""
        client = MCPClient("test_server")
        
        with pytest.raises(RuntimeError, match="Not connected"):
            await client.call_tool("test_tool", {})


class TestMCPClientManager:
    """Тесты менеджера MCP клиентов."""

    @pytest.mark.asyncio
    async def test_get_client_success(self):
        """Тест получения клиента."""
        manager = MCPClientManager()
        
        with patch.object(MCPClient, 'connect', return_value=True):
            client = await manager.get_client("test_server")
            
            assert client is not None
            assert client.server_name == "test_server"
            assert "test_server" in manager.clients

    @pytest.mark.asyncio
    async def test_get_client_failure(self):
        """Тест неудачного получения клиента."""
        manager = MCPClientManager()
        
        with patch.object(MCPClient, 'connect', return_value=False):
            client = await manager.get_client("test_server")
            
            assert client is None
            assert "test_server" not in manager.clients

    @pytest.mark.asyncio
    async def test_disconnect_all(self):
        """Тест отключения всех клиентов."""
        manager = MCPClientManager()
        
        # Добавим мок клиентов
        mock_client1 = Mock()
        mock_client1.disconnect = AsyncMock()
        mock_client2 = Mock()
        mock_client2.disconnect = AsyncMock()
        
        manager.clients = {
            "server1": mock_client1,
            "server2": mock_client2
        }
        
        await manager.disconnect_all()
        
        mock_client1.disconnect.assert_called_once()
        mock_client2.disconnect.assert_called_once()
        assert len(manager.clients) == 0
