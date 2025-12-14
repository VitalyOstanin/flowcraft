"""MCP Manager для управления MCP серверами."""

import asyncio
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


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

    def __post_init__(self):
        if self.enabled_for_workflows is None:
            self.enabled_for_workflows = []


class MCPManager:
    """Менеджер для управления MCP серверами."""

    def __init__(self, settings):
        self.settings = settings
        self.servers: Dict[str, MCPServer] = {}
        self._load_servers()

    def _load_servers(self):
        """Загрузка серверов из настроек."""
        for server_config in self.settings.mcp_servers:
            server = MCPServer(
                name=server_config.name,
                command=[server_config.command] + server_config.args,
                cwd=server_config.cwd,
                env=server_config.env,
                enabled_for_workflows=server_config.enabled_for_workflows
            )
            self.servers[server.name] = server

    async def start_server(self, name: str) -> bool:
        """Запуск MCP сервера."""
        if name not in self.servers:
            return False

        server = self.servers[name]
        if server.status == MCPServerStatus.RUNNING:
            return True

        try:
            server.status = MCPServerStatus.STARTING
            
            # Запуск процесса
            server.process = subprocess.Popen(
                server.command,
                cwd=server.cwd,
                env=server.env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Проверка, что процесс запустился
            await asyncio.sleep(0.5)
            if server.process.poll() is None:
                server.status = MCPServerStatus.RUNNING
                return True
            else:
                server.status = MCPServerStatus.ERROR
                return False

        except Exception:
            server.status = MCPServerStatus.ERROR
            return False

    async def stop_server(self, name: str) -> bool:
        """Остановка MCP сервера."""
        if name not in self.servers:
            return False

        server = self.servers[name]
        if server.status != MCPServerStatus.RUNNING or not server.process:
            server.status = MCPServerStatus.STOPPED
            return True

        try:
            server.process.terminate()
            await asyncio.sleep(1)
            
            if server.process.poll() is None:
                server.process.kill()
                await asyncio.sleep(0.5)
            
            server.status = MCPServerStatus.STOPPED
            server.process = None
            return True

        except Exception:
            server.status = MCPServerStatus.ERROR
            return False

    async def restart_server(self, name: str) -> bool:
        """Перезапуск MCP сервера."""
        await self.stop_server(name)
        return await self.start_server(name)

    def enable_for_workflow(self, server_name: str, workflow_name: str):
        """Включение сервера для workflow."""
        if server_name in self.servers:
            server = self.servers[server_name]
            if workflow_name not in server.enabled_for_workflows:
                server.enabled_for_workflows.append(workflow_name)

    def disable_for_workflow(self, server_name: str, workflow_name: str):
        """Отключение сервера для workflow."""
        if server_name in self.servers:
            server = self.servers[server_name]
            if workflow_name in server.enabled_for_workflows:
                server.enabled_for_workflows.remove(workflow_name)

    def get_servers_for_workflow(self, workflow_name: str) -> List[MCPServer]:
        """Получение серверов для workflow."""
        return [
            server for server in self.servers.values()
            if workflow_name in server.enabled_for_workflows
        ]

    def list_servers(self) -> List[MCPServer]:
        """Список всех серверов."""
        return list(self.servers.values())

    async def start_workflow_servers(self, workflow_name: str) -> bool:
        """Запуск всех серверов для workflow."""
        servers = self.get_servers_for_workflow(workflow_name)
        results = []
        
        for server in servers:
            result = await self.start_server(server.name)
            results.append(result)
        
        return all(results)

    async def stop_workflow_servers(self, workflow_name: str) -> bool:
        """Остановка всех серверов для workflow."""
        servers = self.get_servers_for_workflow(workflow_name)
        results = []
        
        for server in servers:
            result = await self.stop_server(server.name)
            results.append(result)
        
        return all(results)

    async def cleanup(self):
        """Очистка ресурсов."""
        for server in self.servers.values():
            if server.status == MCPServerStatus.RUNNING:
                await self.stop_server(server.name)
