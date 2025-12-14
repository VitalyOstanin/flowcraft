"""MCP Manager для управления MCP серверами с изоляцией по workflow."""

import asyncio
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any


class MCPServerStatus(Enum):
    """Статус MCP сервера."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


@dataclass
class MCPServer:
    """Конфигурация MCP сервера."""
    name: str
    command: List[str]
    cwd: Optional[str] = None
    env: Optional[Dict[str, str]] = None
    status: MCPServerStatus = MCPServerStatus.STOPPED
    process: Optional[subprocess.Popen] = None
    enabled_for_workflows: List[str] = None
    session: Optional[Any] = None
    context_manager: Optional[Any] = None

    def __post_init__(self):
        if self.enabled_for_workflows is None:
            self.enabled_for_workflows = []


class MCPManager:
    """Менеджер для управления MCP серверами с изоляцией по workflow."""

    def __init__(self, settings):
        self.settings = settings
        self.server_configs: Dict[str, MCPServer] = {}
        self.workflow_instances: Dict[str, Dict[str, MCPServer]] = {}  # workflow_id -> {server_name -> instance}
        self._load_servers()

    def _load_servers(self):
        """Загрузка конфигураций серверов из настроек."""
        for server_config in self.settings.mcp_servers:
            server = MCPServer(
                name=server_config.name,
                command=[server_config.command] + server_config.args,
                cwd=server_config.cwd,
                env=server_config.env,
            )
            self.server_configs[server.name] = server

    async def start_workflow_servers(self, workflow_id: str, server_names: List[str]) -> bool:
        """Запуск MCP серверов для конкретного workflow."""
        if workflow_id not in self.workflow_instances:
            self.workflow_instances[workflow_id] = {}
        
        results = []
        for server_name in server_names:
            if server_name not in self.server_configs:
                results.append(False)
                continue
            
            # Создаем отдельный экземпляр для workflow
            config = self.server_configs[server_name]
            instance = MCPServer(
                name=f"{server_name}_{workflow_id}",
                command=config.command.copy(),
                cwd=config.cwd,
                env=config.env.copy() if config.env else None
            )
            
            success = await self._start_server_instance(instance)
            if success:
                self.workflow_instances[workflow_id][server_name] = instance
            results.append(success)
        
        return all(results)

    async def stop_workflow_servers(self, workflow_id: str) -> bool:
        """Остановка всех MCP серверов для workflow."""
        if workflow_id not in self.workflow_instances:
            return True
        
        results = []
        for server_name, instance in self.workflow_instances[workflow_id].items():
            success = await self._stop_server_instance(instance)
            results.append(success)
        
        # Очищаем экземпляры workflow
        del self.workflow_instances[workflow_id]
        return all(results)

    async def _start_server_instance(self, server: MCPServer) -> bool:
        """Запуск экземпляра MCP сервера."""
        if server.status == MCPServerStatus.RUNNING:
            return True

        try:
            server.status = MCPServerStatus.STARTING
            
            # Импортируем MCP клиент
            from mcp.client.stdio import stdio_client
            from mcp import ClientSession, StdioServerParameters
            
            # Создаем MCP session
            server_params = StdioServerParameters(
                command=server.command[0],
                args=server.command[1:] if len(server.command) > 1 else [],
                env=server.env or {}
            )
            
            # Создаем и сохраняем context manager
            server.context_manager = stdio_client(server_params)
            
            # Входим в context manager
            read, write = await server.context_manager.__aenter__()
            
            # Создаем session
            server.session = ClientSession(read, write)
            
            # Инициализируем session
            await server.session.initialize()
            
            server.status = MCPServerStatus.RUNNING
            return True

        except Exception as e:
            print(f"Ошибка запуска MCP сервера {server.name}: {e}")
            # Правильно закрываем context manager при ошибке
            if server.context_manager:
                try:
                    await server.context_manager.__aexit__(type(e), e, e.__traceback__)
                except:
                    pass
            server.status = MCPServerStatus.ERROR
            server.context_manager = None
            return False

    async def _stop_server_instance(self, server: MCPServer) -> bool:
        """Остановка экземпляра MCP сервера."""
        try:
            if server.context_manager:
                # Правильно выходим из context manager
                await server.context_manager.__aexit__(None, None, None)
            server.status = MCPServerStatus.STOPPED
            server.session = None
            server.context_manager = None
            return True
        except Exception as e:
            print(f"Ошибка остановки MCP сервера {server.name}: {e}")
            server.status = MCPServerStatus.STOPPED  # Все равно помечаем как остановленный
            server.session = None
            server.context_manager = None
            return False

    def get_workflow_server(self, workflow_id: str, server_name: str) -> Optional[MCPServer]:
        """Получение экземпляра сервера для workflow."""
        return self.workflow_instances.get(workflow_id, {}).get(server_name)

    async def call_workflow_tool(self, workflow_id: str, server_name: str, tool_name: str, params: Dict[str, Any]) -> Any:
        """Вызов инструмента через экземпляр сервера для workflow."""
        server = self.get_workflow_server(workflow_id, server_name)
        if not server or server.status != MCPServerStatus.RUNNING or not server.session:
            raise ValueError(f"Сервер {server_name} не запущен для workflow {workflow_id}")
        
        try:
            result = await server.session.call_tool(tool_name, params)
            return result
        except Exception as e:
            raise ValueError(f"Ошибка вызова инструмента {tool_name}: {str(e)}")

    async def cleanup(self):
        """Очистка всех ресурсов."""
        for workflow_id in list(self.workflow_instances.keys()):
            await self.stop_workflow_servers(workflow_id)
