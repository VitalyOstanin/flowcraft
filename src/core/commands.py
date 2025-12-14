"""Система команд управления FlowCraft."""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class CommandType(Enum):
    """Типы команд."""
    MCP = "mcp"
    AGENT = "agent"
    WORKFLOW = "workflow"
    SESSION = "session"
    HELP = "help"
    UNKNOWN = "unknown"


@dataclass
class Command:
    """Команда управления."""
    type: CommandType
    action: str
    args: List[str]
    kwargs: Dict[str, str]


class CommandParser:
    """Парсер команд управления."""

    def __init__(self):
        self.command_patterns = {
            r'^/mcp\s+(\w+)(?:\s+(.+))?$': CommandType.MCP,
            r'^/agent\s+(\w+)(?:\s+(.+))?$': CommandType.AGENT,
            r'^/workflow\s+(\w+)(?:\s+(.+))?$': CommandType.WORKFLOW,
            r'^/session\s+(\w+)(?:\s+(.+))?$': CommandType.SESSION,
            r'^/help(?:\s+(\w+))?$': CommandType.HELP,
        }

    def parse(self, command_text: str) -> Command:
        """Парсинг команды."""
        command_text = command_text.strip()
        
        for pattern, cmd_type in self.command_patterns.items():
            match = re.match(pattern, command_text)
            if match:
                action = match.group(1) if match.group(1) else ""
                args_str = match.group(2) if len(match.groups()) > 1 and match.group(2) else ""
                
                args, kwargs = self._parse_args(args_str)
                
                return Command(
                    type=cmd_type,
                    action=action,
                    args=args,
                    kwargs=kwargs
                )
        
        return Command(
            type=CommandType.UNKNOWN,
            action="",
            args=[command_text],
            kwargs={}
        )

    def _parse_args(self, args_str: str) -> Tuple[List[str], Dict[str, str]]:
        """Парсинг аргументов команды."""
        if not args_str:
            return [], {}
        
        parts = args_str.split()
        args = []
        kwargs = {}
        
        for part in parts:
            if '=' in part:
                key, value = part.split('=', 1)
                kwargs[key] = value
            else:
                args.append(part)
        
        return args, kwargs


class CommandHandler:
    """Обработчик команд управления."""

    def __init__(self, settings, agent_manager, mcp_manager):
        self.settings = settings
        self.agent_manager = agent_manager
        self.mcp_manager = mcp_manager
        self.parser = CommandParser()

    async def handle_command(self, command_text: str) -> str:
        """Обработка команды."""
        command = self.parser.parse(command_text)
        
        if command.type == CommandType.MCP:
            return await self._handle_mcp_command(command)
        elif command.type == CommandType.AGENT:
            return self._handle_agent_command(command)
        elif command.type == CommandType.WORKFLOW:
            return self._handle_workflow_command(command)
        elif command.type == CommandType.SESSION:
            return self._handle_session_command(command)
        elif command.type == CommandType.HELP:
            return self._handle_help_command(command)
        else:
            return f"Неизвестная команда: {command_text}"

    async def _handle_mcp_command(self, command: Command) -> str:
        """Обработка MCP команд."""
        if command.action == "list":
            servers = self.mcp_manager.list_servers()
            if not servers:
                return "MCP серверы не настроены"
            
            result = "MCP серверы:\n"
            for server in servers:
                result += f"  - {server.name}: {server.status.value}\n"
            return result
        
        elif command.action == "start":
            if not command.args:
                return "Укажите имя сервера: /mcp start <name>"
            
            server_name = command.args[0]
            success = await self.mcp_manager.start_server(server_name)
            return f"Сервер {server_name}: {'запущен' if success else 'ошибка запуска'}"
        
        elif command.action == "stop":
            if not command.args:
                return "Укажите имя сервера: /mcp stop <name>"
            
            server_name = command.args[0]
            success = await self.mcp_manager.stop_server(server_name)
            return f"Сервер {server_name}: {'остановлен' if success else 'ошибка остановки'}"
        
        elif command.action == "restart":
            if not command.args:
                return "Укажите имя сервера: /mcp restart <name>"
            
            server_name = command.args[0]
            success = await self.mcp_manager.restart_server(server_name)
            return f"Сервер {server_name}: {'перезапущен' if success else 'ошибка перезапуска'}"
        
        elif command.action == "enable":
            if len(command.args) < 2:
                return "Укажите сервер и workflow: /mcp enable <server> <workflow>"
            
            server_name, workflow_name = command.args[0], command.args[1]
            self.mcp_manager.enable_for_workflow(server_name, workflow_name)
            return f"Сервер {server_name} включен для workflow {workflow_name}"
        
        elif command.action == "disable":
            if len(command.args) < 2:
                return "Укажите сервер и workflow: /mcp disable <server> <workflow>"
            
            server_name, workflow_name = command.args[0], command.args[1]
            self.mcp_manager.disable_for_workflow(server_name, workflow_name)
            return f"Сервер {server_name} отключен для workflow {workflow_name}"
        
        else:
            return f"Неизвестная MCP команда: {command.action}"

    def _handle_agent_command(self, command: Command) -> str:
        """Обработка команд агентов."""
        if command.action == "list":
            agents = self.agent_manager.list_agents()
            if not agents:
                return "Агенты не созданы"
            
            result = "Агенты:\n"
            for agent in agents:
                status = "активен" if agent.enabled else "отключен"
                result += f"  - {agent.name} ({agent.role}): {status}\n"
            return result
        
        elif command.action == "create":
            if len(command.args) < 2:
                return "Укажите имя и роль: /agent create <name> <role>"
            
            name, role = command.args[0], command.args[1]
            description = command.kwargs.get("description", f"Агент {name}")
            
            success = self.agent_manager.create_agent(
                name=name,
                role=role,
                description=description
            )
            return f"Агент {name}: {'создан' if success else 'ошибка создания'}"
        
        elif command.action == "delete":
            if not command.args:
                return "Укажите имя агента: /agent delete <name>"
            
            name = command.args[0]
            success = self.agent_manager.delete_agent(name)
            return f"Агент {name}: {'удален' if success else 'не найден'}"
        
        elif command.action == "enable":
            if not command.args:
                return "Укажите имя агента: /agent enable <name>"
            
            name = command.args[0]
            success = self.agent_manager.enable_agent(name)
            return f"Агент {name}: {'включен' if success else 'не найден'}"
        
        elif command.action == "disable":
            if not command.args:
                return "Укажите имя агента: /agent disable <name>"
            
            name = command.args[0]
            success = self.agent_manager.disable_agent(name)
            return f"Агент {name}: {'отключен' if success else 'не найден'}"
        
        else:
            return f"Неизвестная команда агента: {command.action}"

    def _handle_workflow_command(self, command: Command) -> str:
        """Обработка команд workflow."""
        if command.action == "skip-stage":
            return "Команда skip-stage будет реализована в LangGraph интеграции"
        
        elif command.action == "from-stage":
            return "Команда from-stage будет реализована в LangGraph интеграции"
        
        else:
            return f"Неизвестная команда workflow: {command.action}"

    def _handle_session_command(self, command: Command) -> str:
        """Обработка команд сессии."""
        if command.action == "save":
            return "Команда save будет реализована в системе сессий"
        
        elif command.action == "resume":
            return "Команда resume будет реализована в системе сессий"
        
        elif command.action == "list":
            return "Команда list будет реализована в системе сессий"
        
        else:
            return f"Неизвестная команда сессии: {command.action}"

    def _handle_help_command(self, command: Command) -> str:
        """Обработка команды помощи."""
        if command.action:
            return self._get_help_for_topic(command.action)
        
        return self._get_general_help()

    def _get_help_for_topic(self, topic: str) -> str:
        """Помощь по конкретной теме."""
        help_topics = {
            "mcp": """MCP команды:
  /mcp list                    - список серверов
  /mcp start <name>           - запуск сервера
  /mcp stop <name>            - остановка сервера
  /mcp restart <name>         - перезапуск сервера
  /mcp enable <server> <workflow>  - включить для workflow
  /mcp disable <server> <workflow> - отключить для workflow""",
            
            "agent": """Команды агентов:
  /agent list                 - список агентов
  /agent create <name> <role> - создание агента
  /agent delete <name>        - удаление агента
  /agent enable <name>        - включение агента
  /agent disable <name>       - отключение агента""",
            
            "workflow": """Команды workflow:
  /workflow skip-stage        - пропустить этап (в разработке)
  /workflow from-stage        - начать с этапа (в разработке)""",
            
            "session": """Команды сессии:
  /session save               - сохранить сессию (в разработке)
  /session resume             - восстановить сессию (в разработке)
  /session list               - список сессий (в разработке)"""
        }
        
        return help_topics.get(topic, f"Нет справки по теме: {topic}")

    def _get_general_help(self) -> str:
        """Общая справка."""
        return """Доступные команды FlowCraft:

/mcp <action>      - управление MCP серверами
/agent <action>    - управление агентами
/workflow <action> - управление workflow
/session <action>  - управление сессиями
/help [topic]      - справка

Для подробной справки используйте: /help <topic>
Например: /help mcp"""
