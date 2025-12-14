"""
Интеграция LLM провайдеров с LangGraph workflow.
"""

import asyncio
from typing import Dict, Any, List, Optional, Union
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


class WorkflowLLMIntegration:
    """Интеграция LLM с MCP инструментами."""
    
    def __init__(self, settings_manager):
        self.settings_manager = settings_manager
        self.settings = settings_manager.settings
        self.providers = {}
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Инициализация LLM провайдеров."""
        try:
            self.providers["qwen3-coder-plus"] = QwenCodeProvider(self.settings)
        except Exception as e:
            console.print(f"Ошибка инициализации Qwen провайдера: {e}")
    
    async def execute_with_mcp_tools(self, 
                                   system_prompt: str,
                                   user_prompt: str, 
                                   mcp_servers: List[str],
                                   agent_config: Dict[str, Any]) -> str:
        """Выполнение задачи через LLM с доступом к MCP инструментам."""
        
        # Выбираем провайдера
        model_name = agent_config.get('llm_model', self.settings.llm.cheap_model)
        provider = self.providers.get(model_name)
        
        if not provider:
            return f"LLM провайдер {model_name} недоступен"
        
        # Запускаем MCP серверы для этой задачи
        mcp_manager = self._get_mcp_manager()
        workflow_id = f"llm_task_{id(self)}"
        
        try:
            await mcp_manager.start_workflow_servers(workflow_id, mcp_servers)
            
            # Получаем все инструменты от разрешенных MCP серверов
            available_tools = await self._get_mcp_tools(mcp_manager, workflow_id, mcp_servers)
            
            # Выполняем через LLM с инструментами
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            result = await provider.generate_with_tools(messages, available_tools)
            return result
            
        finally:
            await mcp_manager.stop_workflow_servers(workflow_id)
    
    def _get_mcp_manager(self):
        """Получает MCP менеджер из настроек."""
        # Импортируем здесь чтобы избежать циклических импортов
        try:
            from ..mcp_integration.manager import MCPManager
        except ImportError:
            from mcp_integration.manager import MCPManager
        return MCPManager(self.settings_manager)
    
    async def _get_mcp_tools(self, mcp_manager, workflow_id: str, mcp_servers: List[str]) -> List[Dict]:
        """Получает все инструменты от разрешенных MCP серверов."""
        tools = []
        
        for server_name in mcp_servers:
            if server_name in mcp_manager.workflow_instances.get(workflow_id, {}):
                session = mcp_manager.workflow_instances[workflow_id][server_name]
                try:
                    # Получаем все инструменты от MCP сервера
                    tools_response = await session.list_tools()
                    if tools_response and tools_response.tools:
                        for tool in tools_response.tools:
                            tools.append({
                                'name': tool.name,
                                'description': tool.description,
                                'server': server_name,
                                'schema': tool.inputSchema
                            })
                except Exception as e:
                    console.print(f"Ошибка получения инструментов от {server_name}: {e}")
        
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
            self.providers["qwen3-coder-plus"] = QwenCodeProvider(self.settings)
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
