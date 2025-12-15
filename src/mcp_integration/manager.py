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

    def __init__(self, settings_manager):
        self.settings_manager = settings_manager
        self.settings = settings_manager.settings
        self.server_configs: Dict[str, MCPServer] = {}
        self.workflow_instances: Dict[str, Dict[str, MCPServer]] = {}  # workflow_id -> {server_name -> instance}
        self._load_servers()

    def _load_servers(self):
        """Загрузка конфигураций серверов из mcp.yaml."""
        import yaml
        from pathlib import Path
        
        mcp_config_path = Path.home() / ".flowcraft" / "mcp.yaml"
        if not mcp_config_path.exists():
            return
            
        with open(mcp_config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            
        for server_name, server_config in config.get('mcp_servers', {}).items():
            if server_config.get('disabled', False):
                continue
                
            server = MCPServer(
                name=server_name,
                command=[server_config['command']] + server_config.get('args', []),
                cwd=server_config.get('cwd'),
                env=server_config.get('env', {}),
            )
            self.server_configs[server.name] = server

    async def start_workflow_servers(self, workflow_id: str, server_names: List[str]) -> bool:
        """Запуск MCP серверов для конкретного workflow."""
        from core.logging import get_logger
        logger = get_logger("mcp_manager")
        
        logger.info(f"=== ЗАПУСК MCP СЕРВЕРОВ ДЛЯ WORKFLOW ===")
        logger.info(f"Workflow ID: {workflow_id}")
        logger.info(f"Серверы: {server_names}")
        logger.info(f"Доступные конфигурации: {list(self.server_configs.keys())}")
        
        if workflow_id not in self.workflow_instances:
            logger.debug(f"Создание новой записи для workflow {workflow_id}")
            self.workflow_instances[workflow_id] = {}
        
        results = []
        for server_name in server_names:
            logger.info(f"=== ОБРАБОТКА СЕРВЕРА {server_name} ===")
            
            if server_name not in self.server_configs:
                logger.error(f"Конфигурация сервера {server_name} не найдена")
                results.append(False)
                continue
            
            # Создаем отдельный экземпляр для workflow
            config = self.server_configs[server_name]
            logger.debug(f"Конфигурация сервера: {config}")
            logger.debug(f"Команда: {config.command}")
            logger.debug(f"Переменные окружения: {config.env}")
            
            instance = MCPServer(
                name=f"{server_name}_{workflow_id}",
                command=config.command.copy(),
                cwd=config.cwd,
                env=config.env.copy() if config.env else None
            )
            logger.debug(f"Создан экземпляр: {instance}")
            logger.debug(f"Экземпляр env: {instance.env}")
            
            logger.info(f"Запуск экземпляра сервера {server_name}")
            try:
                success = await asyncio.wait_for(
                    self._start_server_instance(instance), 
                    timeout=8.0  # Уменьшил таймаут для быстрой диагностики
                )
            except asyncio.TimeoutError:
                logger.error(f"Таймаут запуска MCP сервера {server_name}")
                success = False
            except Exception as e:
                logger.error(f"Ошибка запуска MCP сервера {server_name}: {e}")
                success = False
                
            logger.info(f"Результат запуска {server_name}: {success}")
            
            if success:
                self.workflow_instances[workflow_id][server_name] = instance
                logger.info(f"Сервер {server_name} добавлен в workflow {workflow_id}")
            else:
                logger.error(f"Не удалось запустить сервер {server_name}")
                
            results.append(success)
        
        final_result = all(results)
        logger.info(f"=== ИТОГОВЫЙ РЕЗУЛЬТАТ ЗАПУСКА: {final_result} ===")
        logger.info(f"Workflow instances: {self.workflow_instances}")
        
        return final_result

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
        from core.logging import get_logger
        logger = get_logger("mcp_manager")
        
        logger.info(f"=== ЗАПУСК ЭКЗЕМПЛЯРА СЕРВЕРА ===")
        logger.info(f"Сервер: {server.name}")
        logger.info(f"Команда: {server.command}")
        logger.info(f"Текущий статус: {server.status}")
        
        if server.status == MCPServerStatus.RUNNING:
            logger.info("Сервер уже запущен")
            return True

        try:
            logger.debug("Установка статуса STARTING")
            server.status = MCPServerStatus.STARTING
            
            logger.debug("Импорт MCP клиента")
            # Импортируем MCP клиент
            from mcp.client.stdio import stdio_client
            from mcp import ClientSession, StdioServerParameters
            
            logger.debug("Создание параметров сервера")
            # Создаем MCP session
            server_params = StdioServerParameters(
                command=server.command[0],
                args=server.command[1:] if len(server.command) > 1 else [],
                env=server.env or {}
            )
            logger.debug(f"Параметры сервера: {server_params}")
            logger.debug(f"Команда: {server_params.command}")
            logger.debug(f"Аргументы: {server_params.args}")
            logger.debug(f"Переменные окружения: {server_params.env}")
            
            logger.debug("Создание context manager")
            # Создаем и сохраняем context manager
            server.context_manager = stdio_client(server_params)
            logger.debug(f"Context manager создан: {server.context_manager}")
            
            logger.info("=== ПОДКЛЮЧЕНИЕ К MCP СЕРВЕРУ ===")
            # Правильный способ работы с MCP (как в langgraph-telegram)
            read_stream, write_stream = await server.context_manager.__aenter__()
            logger.debug("Потоки получены")
            
            server.session = ClientSession(read_stream, write_stream)
            logger.debug(f"Сессия создана: {server.session}")
            
            logger.info("Инициализация сессии")
            try:
                await asyncio.wait_for(server.session.initialize(), timeout=5.0)
                logger.info("Сессия инициализирована успешно")
                
                server.status = MCPServerStatus.RUNNING
                logger.info(f"=== СЕРВЕР {server.name} УСПЕШНО ЗАПУЩЕН ===")
                return True
                
            except asyncio.TimeoutError:
                logger.error("Таймаут инициализации MCP сессии")
                raise
            except Exception as e:
                logger.error(f"Ошибка инициализации MCP сессии: {e}")
                raise
            
        except Exception as e:
            logger.error(f"=== ОШИБКА ЗАПУСКА СЕРВЕРА {server.name} ===")
            logger.error(f"Ошибка: {str(e)}")
            logger.error(f"Тип ошибки: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            server.status = MCPServerStatus.ERROR
            
            # Очищаем ресурсы при ошибке
            if server.context_manager:
                try:
                    logger.debug("Очистка context manager при ошибке")
                    await server.context_manager.__aexit__(type(e), e, e.__traceback__)
                except Exception as cleanup_error:
                    logger.error(f"Ошибка очистки context manager: {cleanup_error}")
                server.context_manager = None
            
            server.session = None
            return False
            
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
