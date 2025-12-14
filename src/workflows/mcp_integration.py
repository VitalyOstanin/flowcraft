"""
Интеграция с MCP серверами
"""

import asyncio
import subprocess
import json
from typing import Dict, List, Optional, Any
from pathlib import Path
from rich.console import Console

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

console = Console()

class MCPTool:
    """Представление MCP инструмента"""
    
    def __init__(self, server_name: str, tool_name: str, description: str, input_schema: Dict):
        self.server_name = server_name
        self.tool_name = tool_name
        self.description = description
        self.input_schema = input_schema
        self.full_name = f"{server_name}.{tool_name}"

class MCPClient:
    """Клиент для работы с MCP сервером"""
    
    def __init__(self, server_config: Dict[str, Any]):
        self.name = server_config.get("name", "")
        self.command = server_config.get("command", "")
        self.args = server_config.get("args", [])
        self.env = server_config.get("env", {})
        self.cwd = server_config.get("cwd")
        self.disabled = server_config.get("disabled", False)
        
        self.session: Optional[ClientSession] = None
        self.tools: Dict[str, MCPTool] = {}
        self.process = None
    
    async def start(self) -> bool:
        """Запустить MCP сервер"""
        if self.disabled:
            console.print(f"MCP сервер {self.name} отключен", style="yellow")
            return False
        
        if not MCP_AVAILABLE:
            console.print(f"Библиотека MCP недоступна для сервера {self.name}", style="red")
            return False
        
        try:
            # Создать параметры сервера
            server_params = StdioServerParameters(
                command=self.command,
                args=self.args,
                env=self.env
            )
            
            # Запустить клиент
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    self.session = session
                    
                    # Инициализация
                    await session.initialize()
                    
                    # Получить список инструментов
                    tools_result = await session.list_tools()
                    
                    # Сохранить инструменты
                    for tool in tools_result.tools:
                        mcp_tool = MCPTool(
                            server_name=self.name,
                            tool_name=tool.name,
                            description=tool.description or "",
                            input_schema=tool.inputSchema or {}
                        )
                        self.tools[tool.name] = mcp_tool
                    
                    console.print(f"MCP сервер {self.name} запущен с {len(self.tools)} инструментами", style="green")
                    return True
                    
        except Exception as e:
            console.print(f"Ошибка запуска MCP сервера {self.name}: {e}", style="red")
            return False
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Вызвать инструмент MCP сервера"""
        if not self.session:
            raise RuntimeError(f"MCP сервер {self.name} не запущен")
        
        if tool_name not in self.tools:
            raise ValueError(f"Инструмент {tool_name} не найден в сервере {self.name}")
        
        try:
            result = await self.session.call_tool(tool_name, arguments)
            return result
        except Exception as e:
            console.print(f"Ошибка вызова {self.name}.{tool_name}: {e}", style="red")
            raise
    
    def stop(self):
        """Остановить MCP сервер"""
        try:
            if self.session:
                # Сессия закроется автоматически при выходе из контекста
                self.session = None
            
            if self.process:
                self.process.terminate()
                self.process = None
            
            self.tools.clear()
            console.print(f"MCP сервер {self.name} остановлен", style="yellow")
        except Exception as e:
            console.print(f"Ошибка остановки MCP сервера {self.name}: {e}", style="red")
    
    def is_available(self) -> bool:
        """Проверить доступность сервера"""
        return not self.disabled and bool(self.command) and MCP_AVAILABLE
    
    def get_tools_for_llm(self) -> List[Dict[str, Any]]:
        """Получить инструменты в формате для LLM"""
        llm_tools = []
        for tool in self.tools.values():
            llm_tools.append({
                "name": tool.full_name,
                "description": tool.description,
                "input_schema": tool.input_schema
            })
        return llm_tools

class MCPManager:
    """Менеджер MCP серверов"""
    
    def __init__(self, settings_manager):
        self.settings_manager = settings_manager
        self.active_servers: Dict[str, MCPClient] = {}
    
    async def start_servers_for_workflow(self, workflow_config: Dict) -> List[str]:
        """Запустить MCP серверы для workflow"""
        required_servers = workflow_config.get("mcp_servers", [])
        started_servers = []
        
        for server_name in required_servers:
            if await self.start_server(server_name):
                started_servers.append(server_name)
        
        return started_servers
    
    async def start_server(self, server_name: str) -> bool:
        """Запустить конкретный MCP сервер"""
        if server_name in self.active_servers:
            return True
        
        # Найти конфигурацию сервера
        server_config = None
        for server in self.settings_manager.settings.mcp_servers:
            if server.name == server_name:
                server_config = server.model_dump()
                break
        
        if not server_config:
            console.print(f"Конфигурация MCP сервера {server_name} не найдена", style="red")
            return False
        
        client = MCPClient(server_config)
        if await client.start():
            self.active_servers[server_name] = client
            return True
        
        return False
    
    def stop_all_servers(self):
        """Остановить все активные серверы"""
        for client in self.active_servers.values():
            client.stop()
        self.active_servers.clear()
    
    def get_available_servers(self) -> List[str]:
        """Получить список доступных серверов"""
        available = []
        for server in self.settings_manager.settings.mcp_servers:
            if not server.disabled:
                available.append(server.name)
        return available
    
    def get_all_tools_for_llm(self) -> List[Dict[str, Any]]:
        """Получить все инструменты всех активных серверов для LLM"""
        all_tools = []
        for client in self.active_servers.values():
            all_tools.extend(client.get_tools_for_llm())
        return all_tools
    
    async def call_tool(self, full_tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Вызвать инструмент по полному имени (server.tool)"""
        if "." not in full_tool_name:
            raise ValueError(f"Неверный формат имени инструмента: {full_tool_name}. Ожидается: server.tool")
        
        server_name, tool_name = full_tool_name.split(".", 1)
        
        if server_name not in self.active_servers:
            raise RuntimeError(f"MCP сервер {server_name} не активен")
        
        return await self.active_servers[server_name].call_tool(tool_name, arguments)
