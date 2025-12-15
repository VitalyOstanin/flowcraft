"""
Интеграция LLM провайдеров с LangGraph workflow.
"""

import asyncio
import re
from typing import Dict, Any, List, Optional, Union, Tuple
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from rich.console import Console

try:
    from .state import WorkflowState, AgentState, agent_dict_to_state
    from ..llm.qwen_code import QwenCodeProvider
    from ..core.settings import Settings
except ImportError:
    # Fallback для прямого запуска
    from workflows.state import WorkflowState, AgentState, agent_dict_to_state
    from llm.qwen_code import QwenCodeProvider
    from core.settings import Settings


console = Console()


class LLMCommandParser:
    """Парсер специальных команд LLM."""
    
    @staticmethod
    def parse_llm_response(response: str) -> Dict[str, Any]:
        """Парсинг ответа LLM на предмет специальных команд."""
        
        result = {
            "has_commands": False,
            "commands": [],
            "content": response,
            "requires_user_input": False
        }
        
        # Паттерны для специальных команд
        patterns = {
            "CONFIRM_DATA": r'CONFIRM_DATA:\s*(.+?)(?:\n|$)',
            "REQUEST_APPROVAL": r'REQUEST_APPROVAL:\s*(.+?)(?:\n|$)', 
            "STAGE_COMPLETE": r'STAGE_COMPLETE(?:\s*:\s*(.+?))?(?:\n|$)'
        }
        
        for command_type, pattern in patterns.items():
            matches = re.findall(pattern, response, re.MULTILINE | re.DOTALL)
            
            for match in matches:
                command = {
                    "type": command_type,
                    "content": match.strip() if match else "",
                    "requires_user_input": command_type in ["CONFIRM_DATA", "REQUEST_APPROVAL"]
                }
                
                result["commands"].append(command)
                result["has_commands"] = True
                
                if command["requires_user_input"]:
                    result["requires_user_input"] = True
        
        return result
    
    @staticmethod
    def interpret_user_response(user_input: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Интерпретация ответа пользователя на естественном языке."""
        
        user_input_lower = user_input.lower().strip()
        
        result = {
            "intent": "unknown",
            "confidence": 0.0,
            "parameters": {},
            "raw_input": user_input
        }
        
        # Паттерны для подтверждения
        confirm_patterns = [
            r'\b(да|yes|подтверждаю|согласен|правильно|верно|ок|окей)\b',
            r'\b(продолжай|продолжить|далее|next)\b'
        ]
        
        # Паттерны для отклонения
        reject_patterns = [
            r'\b(нет|no|отклоняю|не согласен|неправильно|неверно|отмена)\b',
            r'\b(исправь|измени|поправь|fix|change)\b'
        ]
        
        # Паттерны для модификации
        modify_patterns = [
            r'измени\s+(.+)',
            r'поправь\s+(.+)',
            r'сделай\s+(.+)',
            r'добавь\s+(.+)',
            r'убери\s+(.+)'
        ]
        
        # Проверяем подтверждение
        for pattern in confirm_patterns:
            if re.search(pattern, user_input_lower):
                result["intent"] = "confirm"
                result["confidence"] = 0.9
                return result
        
        # Проверяем отклонение
        for pattern in reject_patterns:
            if re.search(pattern, user_input_lower):
                result["intent"] = "reject"
                result["confidence"] = 0.9
                return result
        
        # Проверяем модификацию
        for pattern in modify_patterns:
            match = re.search(pattern, user_input_lower)
            if match:
                result["intent"] = "modify"
                result["confidence"] = 0.8
                result["parameters"]["modification"] = match.group(1).strip()
                
                # Пытаемся извлечь конкретные параметры
                LLMCommandParser._extract_modification_parameters(user_input, result)
                return result
        
        # Если не распознали, возвращаем как есть для обработки LLM
        result["intent"] = "unclear"
        result["confidence"] = 0.1
        
        return result
    
    @staticmethod
    def _extract_modification_parameters(user_input: str, result: Dict[str, Any]):
        """Извлечение конкретных параметров модификации."""
        
        user_input_lower = user_input.lower()
        
        # Паттерны для извлечения дат
        date_patterns = [
            r'(\d{1,2})\s+дн[ейя]',
            r'(\d{4}-\d{2}-\d{2})',
            r'с\s+(\d{4}-\d{2}-\d{2})\s+до\s+(\d{4}-\d{2}-\d{2})'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, user_input_lower)
            if match:
                if len(match.groups()) == 1:
                    result["parameters"]["period_days"] = match.group(1)
                elif len(match.groups()) == 2:
                    result["parameters"]["start_date"] = match.group(1)
                    result["parameters"]["end_date"] = match.group(2)
                break
        
        # Паттерны для категорий
        if "категори" in user_input_lower:
            result["parameters"]["modify_categories"] = True
        
        # Паттерны для пользователей
        user_match = re.search(r'пользовател[ья]\s+(\w+)', user_input_lower)
        if user_match:
            result["parameters"]["user"] = user_match.group(1)


class WorkflowLLMIntegration:
    """Интеграция LLM с MCP инструментами."""
    
    def __init__(self, settings_manager):
        self.settings_manager = settings_manager
        self.settings = settings_manager.settings
        self.providers = {}
        self.command_parser = LLMCommandParser()
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Инициализация LLM провайдеров."""
        try:
            self.providers["qwen3-coder-plus"] = QwenCodeProvider("qwen3-coder-plus")
        except Exception as e:
            console.print(f"Ошибка инициализации Qwen провайдера: {e}")
    
    async def execute_stage_with_iterations(self,
                                          system_prompt: str,
                                          user_prompt: str,
                                          mcp_servers: List[str],
                                          agent_config: Dict[str, Any],
                                          state: WorkflowState) -> Tuple[str, bool, Optional[str]]:
        """
        Выполнение stage с поддержкой многоитерационного взаимодействия.
        
        Returns:
            Tuple[str, bool, Optional[str]]: (результат, требуется_ввод_пользователя, промпт_для_пользователя)
        """
        
        from core.logging import get_logger
        from .state import get_stage_conversation_context
        
        logger = get_logger("llm_integration")
        
        logger.info("=== EXECUTE_STAGE_WITH_ITERATIONS ===")
        
        # Добавляем контекст предыдущих итераций в user prompt
        conversation_context = get_stage_conversation_context(state)
        if conversation_context:
            enhanced_user_prompt = f"{conversation_context}\n\n{user_prompt}"
        else:
            enhanced_user_prompt = user_prompt
        
        # Добавляем инструкции по специальным командам
        enhanced_user_prompt += self._get_special_commands_instructions()
        
        # Выполняем базовый запрос к LLM
        llm_response = await self.execute_stage_with_mcp(
            system_prompt, enhanced_user_prompt, mcp_servers, agent_config
        )
        
        # Парсим ответ на предмет специальных команд
        parsed_response = self.command_parser.parse_llm_response(llm_response)
        
        logger.info(f"Parsed response: {parsed_response}")
        
        if parsed_response["requires_user_input"]:
            # LLM запрашивает взаимодействие с пользователем
            user_prompt = self._extract_user_prompt_from_commands(parsed_response["commands"])
            return llm_response, True, user_prompt
        
        elif parsed_response["has_commands"]:
            # Проверяем команду STAGE_COMPLETE
            for command in parsed_response["commands"]:
                if command["type"] == "STAGE_COMPLETE":
                    logger.info("LLM сигнализирует о завершении stage")
                    return llm_response, False, None
        
        # Обычный ответ без специальных команд
        return llm_response, False, None
    
    async def process_user_response_iteration(self,
                                            user_response: str,
                                            original_system_prompt: str,
                                            original_user_prompt: str,
                                            mcp_servers: List[str],
                                            agent_config: Dict[str, Any],
                                            state: WorkflowState) -> Tuple[str, bool, Optional[str]]:
        """
        Обработка ответа пользователя и продолжение итерации.
        
        Returns:
            Tuple[str, bool, Optional[str]]: (результат, требуется_ввод_пользователя, промпт_для_пользователя)
        """
        
        from core.logging import get_logger
        from .state import get_stage_conversation_context
        
        logger = get_logger("llm_integration")
        
        logger.info("=== PROCESS_USER_RESPONSE_ITERATION ===")
        logger.info(f"User response: {user_response}")
        
        # Интерпретируем ответ пользователя
        interpreted_response = self.command_parser.interpret_user_response(user_response)
        logger.info(f"Interpreted response: {interpreted_response}")
        
        # Формируем контекст для LLM с учетом ответа пользователя
        conversation_context = get_stage_conversation_context(state)
        
        user_response_prompt = f"""
Пользователь ответил: "{user_response}"

Интерпретация ответа:
- Намерение: {interpreted_response['intent']}
- Уверенность: {interpreted_response['confidence']}
- Параметры: {interpreted_response.get('parameters', {})}

Обработай ответ пользователя и продолжи выполнение задачи согласно его указаниям.
Если пользователь подтвердил данные - заверши stage командой STAGE_COMPLETE.
Если пользователь запросил изменения - внеси их и запроси новое подтверждение.
"""
        
        enhanced_user_prompt = f"{conversation_context}\n\n{original_user_prompt}\n\n{user_response_prompt}"
        enhanced_user_prompt += self._get_special_commands_instructions()
        
        # Выполняем запрос к LLM с учетом ответа пользователя
        llm_response = await self.execute_stage_with_mcp(
            original_system_prompt, enhanced_user_prompt, mcp_servers, agent_config
        )
        
        # Парсим новый ответ
        parsed_response = self.command_parser.parse_llm_response(llm_response)
        
        if parsed_response["requires_user_input"]:
            user_prompt = self._extract_user_prompt_from_commands(parsed_response["commands"])
            return llm_response, True, user_prompt
        
        elif parsed_response["has_commands"]:
            for command in parsed_response["commands"]:
                if command["type"] == "STAGE_COMPLETE":
                    logger.info("LLM завершил stage после обработки ответа пользователя")
                    return llm_response, False, None
        
        return llm_response, False, None
    
    def _get_special_commands_instructions(self) -> str:
        """Получение инструкций по специальным командам для LLM."""
        
        return """

СПЕЦИАЛЬНЫЕ КОМАНДЫ:
- CONFIRM_DATA: <вопрос> - запросить подтверждение данных у пользователя
- REQUEST_APPROVAL: <вопрос> - запросить одобрение действий у пользователя  
- STAGE_COMPLETE - явно завершить выполнение stage

Примеры:
CONFIRM_DATA: Данные за период 2025-12-07 до 2025-12-14 корректны?
REQUEST_APPROVAL: Могу ли я продолжить анализ с этими параметрами?
STAGE_COMPLETE

Используй эти команды для взаимодействия с пользователем и управления выполнением stage.
"""
    
    def _extract_user_prompt_from_commands(self, commands: List[Dict[str, Any]]) -> str:
        """Извлечение промпта для пользователя из команд LLM."""
        
        user_prompts = []
        
        for command in commands:
            if command["type"] in ["CONFIRM_DATA", "REQUEST_APPROVAL"]:
                if command["content"]:
                    user_prompts.append(command["content"])
                else:
                    # Дефолтные промпты
                    if command["type"] == "CONFIRM_DATA":
                        user_prompts.append("Подтвердите корректность данных")
                    elif command["type"] == "REQUEST_APPROVAL":
                        user_prompts.append("Одобрите выполнение действий")
        
        return " | ".join(user_prompts) if user_prompts else "Требуется ваш ответ"
    
    def _format_tools_for_user_prompt(self, tools: List[Dict]) -> str:
        """Форматирует схемы инструментов для user prompt."""
        if not tools:
            return ""
        
        formatted = ["Доступные MCP инструменты:"]
        for tool in tools:
            tool_info = f"\n- {tool['name']}: {tool['description']}"
            
            # Добавляем схему параметров если есть
            if 'schema' in tool and tool['schema']:
                schema = tool['schema']
                if 'properties' in schema:
                    params = []
                    required = schema.get('required', [])
                    for param_name, param_info in schema['properties'].items():
                        param_desc = param_info.get('description', '')
                        param_type = param_info.get('type', 'string')
                        is_required = param_name in required
                        req_marker = " (обязательный)" if is_required else " (опциональный)"
                        params.append(f"    {param_name} ({param_type}){req_marker}: {param_desc}")
                    
                    if params:
                        tool_info += "\n  Параметры:\n" + "\n".join(params)
            
            formatted.append(tool_info)
        
        formatted.append("\nДля вызова инструмента используй формат: TOOL_CALL:tool_name:parameters_json")
        return "\n".join(formatted)

    def _format_tools_for_user_prompt(self, tools: List[Dict]) -> str:
        """Форматирует схемы инструментов для user prompt."""
        if not tools:
            return ""
        
        import json
        tools_json = json.dumps(tools, indent=2, ensure_ascii=False)
        return f"Доступные MCP инструменты:\n{tools_json}\n\nДля вызова инструмента используй формат: TOOL_CALL:tool_name:parameters_json"

    async def execute_stage_with_mcp(self, 
                                   system_prompt: str,
                                   user_prompt: str, 
                                   mcp_servers: List[str],
                                   agent_config: Dict[str, Any]) -> str:
        """Выполнение stage через LLM с MCP подключением на уровне stage."""
        
        from core.logging import get_logger
        logger = get_logger("llm_integration")
        
        logger.info(f"=== EXECUTE_STAGE_WITH_MCP ===")
        logger.info(f"MCP серверы: {mcp_servers}")
        
        # Выбираем провайдера
        model_name = agent_config.get('llm_model', self.settings.llm.cheap_model)
        logger.info(f"Выбранная модель: {model_name}")
        
        provider = self.providers.get(model_name)
        
        if not provider:
            error_msg = f"LLM провайдер {model_name} недоступен"
            logger.error(error_msg)
            return error_msg
        
        logger.info(f"Провайдер найден: {provider}")
        
        # Создаем MCP подключение для этого stage
        logger.info("=== СОЗДАНИЕ MCP ПОДКЛЮЧЕНИЯ ДЛЯ STAGE ===")
        
        try:
            # Получаем конфигурацию MCP сервера
            mcp_server_config = None
            for server_config in self.settings.mcp_servers:
                if server_config.name in mcp_servers:
                    mcp_server_config = server_config
                    break
            
            if not mcp_server_config:
                raise Exception(f"MCP сервер не найден в конфигурации: {mcp_servers}")
            
            logger.info(f"Найдена конфигурация MCP: {mcp_server_config}")
            
            # Создаем подключение для stage (как в langgraph-telegram)
            from mcp.client.stdio import stdio_client
            from mcp import ClientSession, StdioServerParameters
            
            server_params = StdioServerParameters(
                command=mcp_server_config.command,
                args=mcp_server_config.args,
                env=mcp_server_config.env or {}
            )
            
            logger.info(f"Параметры MCP сервера: {server_params}")
            
            async with stdio_client(server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    logger.info("=== ИНИЦИАЛИЗАЦИЯ MCP СЕССИИ ===")
                    await session.initialize()
                    logger.info("MCP сессия инициализирована")
                    
                    logger.info("=== ПОЛУЧЕНИЕ MCP ИНСТРУМЕНТОВ ===")
                    tools_response = await session.list_tools()
                    available_tools = []
                    
                    if tools_response and tools_response.tools:
                        for tool in tools_response.tools:
                            # Безопасная сериализация схемы
                            try:
                                import json
                                schema = json.loads(json.dumps(tool.inputSchema, default=str))
                            except:
                                schema = {"type": "object", "properties": {}}
                            
                            available_tools.append({
                                'name': tool.name,
                                'description': tool.description,
                                'schema': schema
                            })
                    
                    logger.info(f"Доступные инструменты: {len(available_tools)}")
                    
                    logger.info("=== ПОДГОТОВКА СООБЩЕНИЙ ===")
                    
                    # Добавляем схемы инструментов в user prompt
                    tools_info = self._format_tools_for_user_prompt(available_tools)
                    enhanced_user_prompt = f"{user_prompt}\n\n{tools_info}"
                    
                    messages = [
                        SystemMessage(content=system_prompt),
                        HumanMessage(content=enhanced_user_prompt)
                    ]
                    
                    # Добавляем информацию о сервере к инструментам
                    for tool in available_tools:
                        tool['server'] = mcp_server_config.name
                    
                    # Создаем словарь сессий
                    mcp_sessions = {mcp_server_config.name: session}
                    
                    logger.info("=== ВЫЗОВ LLM ПРОВАЙДЕРА ===")
                    
                    # Используем накопление tool calls если доступно
                    if hasattr(provider, 'chat_completion_with_tool_accumulation'):
                        logger.info("=== ИСПОЛЬЗУЕМ НАКОПЛЕНИЕ TOOL CALLS ===")
                        result = await provider.chat_completion_with_tool_accumulation(
                            messages, available_tools, mcp_sessions, max_iterations=10
                        )
                    else:
                        logger.info("=== ОБЫЧНЫЙ МЕТОД (БЕЗ НАКОПЛЕНИЯ) ===")
                        result = await provider.generate_with_tools(messages, available_tools, mcp_sessions)
                    
                    logger.info(f"Результат от провайдера: {result}")
                    
                    return result
            
        except Exception as e:
            logger.error(f"=== ОШИБКА В EXECUTE_STAGE_WITH_MCP ===")
            logger.error(f"Ошибка: {str(e)}")
            logger.error(f"Тип ошибки: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    def _get_mcp_manager(self):
        """Получает MCP менеджер из настроек."""
        from core.logging import get_logger
        logger = get_logger("llm_integration")
        
        logger.debug("Получение MCP менеджера")
        # Импортируем здесь чтобы избежать циклических импортов
        try:
            from mcp_integration.manager import MCPManager
            logger.debug("Импорт MCPManager успешен")
        except ImportError as e:
            logger.error(f"Ошибка импорта MCPManager: {e}")
            try:
                from mcp_integration.manager import MCPManager
                logger.debug("Альтернативный импорт MCPManager успешен")
            except ImportError as e2:
                logger.error(f"Альтернативный импорт MCPManager неуспешен: {e2}")
                raise
        
        logger.debug("Создание экземпляра MCPManager")
        manager = MCPManager(self.settings_manager)
        logger.debug(f"MCPManager создан: {manager}")
        return manager
    
    async def _get_mcp_tools(self, mcp_manager, workflow_id: str, mcp_servers: List[str]) -> List[Dict]:
        """Получает все инструменты от разрешенных MCP серверов."""
        from core.logging import get_logger
        logger = get_logger("llm_integration")
        
        logger.info(f"=== ПОЛУЧЕНИЕ MCP ИНСТРУМЕНТОВ ===")
        logger.info(f"Workflow ID: {workflow_id}")
        logger.info(f"MCP серверы: {mcp_servers}")
        logger.info(f"Workflow instances: {mcp_manager.workflow_instances}")
        
        tools = []
        
        for server_name in mcp_servers:
            logger.info(f"Обработка сервера: {server_name}")
            
            if workflow_id not in mcp_manager.workflow_instances:
                logger.warning(f"Workflow {workflow_id} не найден в workflow_instances")
                continue
                
            if server_name not in mcp_manager.workflow_instances[workflow_id]:
                logger.warning(f"Сервер {server_name} не найден в workflow {workflow_id}")
                continue
                
            session = mcp_manager.workflow_instances[workflow_id][server_name]
            logger.info(f"Сессия для {server_name}: {session}")
            
            try:
                logger.info(f"Получение инструментов от {server_name}")
                # Получаем все инструменты от MCP сервера
                tools_response = await session.list_tools()
                logger.info(f"Ответ от {server_name}: {tools_response}")
                
                if tools_response and tools_response.tools:
                    logger.info(f"Найдено {len(tools_response.tools)} инструментов от {server_name}")
                    for tool in tools_response.tools:
                        tool_info = {
                            'name': tool.name,
                            'description': tool.description,
                            'server': server_name,
                            'schema': tool.inputSchema
                        }
                        tools.append(tool_info)
                        logger.debug(f"Добавлен инструмент: {tool_info}")
                else:
                    logger.warning(f"Нет инструментов от {server_name}")
                    
            except Exception as e:
                logger.error(f"=== ОШИБКА ПОЛУЧЕНИЯ ИНСТРУМЕНТОВ ОТ {server_name} ===")
                logger.error(f"Ошибка: {str(e)}")
                logger.error(f"Тип ошибки: {type(e)}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                console.print(f"Ошибка получения инструментов от {server_name}: {e}")
        
        logger.info(f"=== ИТОГО ПОЛУЧЕНО ИНСТРУМЕНТОВ: {len(tools)} ===")
        return tools


class WorkflowLLMManager:
    """Менеджер LLM для workflow."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.providers = {}
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Инициализация LLM провайдеров."""
        
        # Инициализируем доступные провайдеры
        try:
            self.providers["qwen3-coder-plus"] = QwenCodeProvider("qwen3-coder-plus")
        except Exception as e:
            console.print(f"Ошибка инициализации Qwen провайдера: {e}")
        
        # TODO: Добавить другие провайдеры (kiro-cli, etc.)
    
    async def execute_agent_task(self, 
                               agent: Dict[str, Any],
                               context: Dict[str, Any],
                               state: WorkflowState) -> Dict[str, Any]:
        """Выполнение задачи агента через LLM."""
        
        try:
            # Преобразуем словарь агента в AgentState для работы с LLM
            agent_state = agent_dict_to_state(agent)
            
            # Выбираем провайдера для агента
            provider = self._select_provider(agent_state, context)
            
            if provider is None:
                raise ValueError(f"Нет доступного LLM провайдера для агента {agent_state.name}")
            
            # Подготавливаем промпт
            messages = self._prepare_messages(agent_state, context, state)
            
            # Выполняем запрос к LLM
            console.print(f"Агент {agent_state.name} обращается к LLM...")
            
            response = await provider.generate_async(messages)
            
            # Обрабатываем ответ
            result = self._process_llm_response(agent_state, response, context)
            
            console.print(f"Агент {agent_state.name} получил ответ от LLM")
            
            return result
            
        except Exception as e:
            console.print(f"Ошибка выполнения задачи агента {agent.get('name', 'unknown')}: {str(e)}")
            raise
    
    def _select_provider(self, agent: AgentState, context: Dict[str, Any]) -> Optional[Any]:
        """Выбор LLM провайдера для агента."""
        
        # Проверяем, указана ли конкретная модель для агента
        preferred_model = agent.llm_model
        
        if preferred_model in self.providers:
            return self.providers[preferred_model]
        
        # Проверяем, требуется ли дорогая модель для этого stage
        stage_name = context.get("current_stage", "")
        expensive_stages = self.settings.llm.expensive_stages
        
        if stage_name in expensive_stages:
            # Используем дорогую модель
            expensive_model = self.settings.llm.expensive_model
            if expensive_model in self.providers:
                return self.providers[expensive_model]
        
        # Используем дешевую модель по умолчанию
        cheap_model = self.settings.llm.cheap_model
        if cheap_model in self.providers:
            return self.providers[cheap_model]
        
        # Возвращаем любой доступный провайдер
        if self.providers:
            return next(iter(self.providers.values()))
        
        return None
    
    def _prepare_messages(self, 
                         agent: AgentState, 
                         context: Dict[str, Any],
                         state: WorkflowState) -> List[BaseMessage]:
        """Подготовка сообщений для LLM."""
        
        messages = []
        
        # Системный промпт для роли агента
        role_prompt = self._get_role_prompt(agent, context)
        messages.append(SystemMessage(content=role_prompt))
        
        # Контекст задачи
        task_context = self._build_task_context(context, state)
        messages.append(HumanMessage(content=task_context))
        
        # История сообщений (последние несколько)
        recent_messages = state.get("messages", [])[-3:]
        for msg in recent_messages:
            if isinstance(msg, (HumanMessage, AIMessage)):
                messages.append(msg)
        
        return messages
    
    def _get_role_prompt(self, agent: AgentState, context: Dict[str, Any]) -> str:
        """Получение промпта для роли агента."""
        
        # Базовый промпт для роли
        role_prompts = {
            "developer": "Ты опытный разработчик. Анализируй код, предлагай решения, пиши качественный код.",
            "tester": "Ты тестировщик. Создавай тесты, находи баги, проверяй качество.",
            "reviewer": "Ты код-ревьюер. Проверяй код на качество, стандарты, безопасность.",
            "devops": "Ты DevOps инженер. Настраивай CI/CD, развертывание, мониторинг.",
            "security_expert": "Ты эксперт по безопасности. Ищи уязвимости, проверяй безопасность.",
            "technical_writer": "Ты технический писатель. Создавай документацию, руководства, описания.",
            "architect": "Ты архитектор ПО. Проектируй архитектуру, принимай технические решения."
        }
        
        base_prompt = role_prompts.get(agent.role, f"Ты {agent.role}.")
        
        # Добавляем контекст текущего stage
        stage_description = context.get("stage_description", "")
        if stage_description:
            base_prompt += f"\n\nТекущая задача: {stage_description}"
        
        # Добавляем информацию о возможностях агента
        if agent.capabilities:
            capabilities_str = ", ".join(agent.capabilities)
            base_prompt += f"\n\nТвои возможности: {capabilities_str}"
        
        base_prompt += "\n\nОтвечай на русском языке. Будь конкретным и практичным."
        
        return base_prompt
    
    def _build_task_context(self, context: Dict[str, Any], state: WorkflowState) -> str:
        """Построение контекста задачи для LLM."""
        
        context_parts = []
        
        # Основная задача
        task_description = context.get("task_description", "")
        if task_description:
            context_parts.append(f"Основная задача: {task_description}")
        
        # Текущий stage
        current_stage = context.get("current_stage", "")
        stage_description = context.get("stage_description", "")
        if current_stage:
            context_parts.append(f"Текущий этап: {current_stage}")
            if stage_description:
                context_parts.append(f"Описание этапа: {stage_description}")
        
        # Завершенные этапы
        completed_stages = context.get("completed_stages", [])
        if completed_stages:
            context_parts.append(f"Завершенные этапы: {', '.join(completed_stages)}")
        
        # Результаты предыдущих этапов
        stage_outputs = context.get("stage_outputs", {})
        if stage_outputs:
            outputs_summary = []
            for stage, output in stage_outputs.items():
                if isinstance(output, dict) and "output" in output:
                    outputs_summary.append(f"{stage}: {output['output']}")
            
            if outputs_summary:
                context_parts.append("Результаты предыдущих этапов:")
                context_parts.extend([f"- {summary}" for summary in outputs_summary])
        
        # Пользовательские входы
        user_inputs = context.get("user_inputs", {})
        if user_inputs:
            context_parts.append("Пользовательские данные:")
            for key, value in user_inputs.items():
                context_parts.append(f"- {key}: {value}")
        
        return "\n\n".join(context_parts)
    
    def _process_llm_response(self, 
                            agent: Dict[str, Any], 
                            response: str,
                            context: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка ответа LLM."""
        
        return {
            "agent": agent.name,
            "role": agent.role,
            "stage": context.get("current_stage", "unknown"),
            "status": "completed",
            "output": response,
            "llm_model": agent.llm_model,
            "timestamp": asyncio.get_event_loop().time(),
            "context_used": {
                "task_description": context.get("task_description", ""),
                "stage_description": context.get("stage_description", ""),
                "completed_stages": context.get("completed_stages", [])
            }
        }
    
    async def validate_agent_response(self, 
                                    agent: AgentState,
                                    response: Dict[str, Any],
                                    expected_format: Optional[Dict[str, Any]] = None) -> bool:
        """Валидация ответа агента."""
        
        # Базовая валидация
        required_fields = ["agent", "stage", "status", "output"]
        
        for field in required_fields:
            if field not in response:
                console.print(f"Отсутствует обязательное поле в ответе агента: {field}")
                return False
        
        # Проверка статуса
        if response["status"] not in ["completed", "failed", "partial"]:
            console.print(f"Неверный статус в ответе агента: {response['status']}")
            return False
        
        # Проверка наличия содержательного ответа
        output = response.get("output", "")
        if not output or len(output.strip()) < 10:
            console.print("Слишком короткий ответ от агента")
            return False
        
        # Дополнительная валидация по формату (если указан)
        if expected_format:
            # TODO: Реализовать валидацию по схеме
            pass
        
        return True
    
    def get_available_models(self) -> List[str]:
        """Получение списка доступных моделей."""
        return list(self.providers.keys())
    
    def get_provider_status(self) -> Dict[str, Dict[str, Any]]:
        """Получение статуса провайдеров."""
        
        status = {}
        
        for name, provider in self.providers.items():
            try:
                # Проверяем доступность провайдера
                if hasattr(provider, 'check_availability'):
                    available = provider.check_availability()
                else:
                    available = True
                
                status[name] = {
                    "available": available,
                    "type": provider.__class__.__name__,
                    "status": "ready" if available else "unavailable"
                }
                
            except Exception as e:
                status[name] = {
                    "available": False,
                    "type": provider.__class__.__name__,
                    "status": "error",
                    "error": str(e)
                }
        
        return status
