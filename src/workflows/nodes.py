"""
Базовые узлы для LangGraph workflow.
"""

import asyncio
from typing import Dict, Any, List, Optional, Callable
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from rich.console import Console

from .state import WorkflowState, add_stage_output, mark_stage_failed, require_human_input, create_agent_dict, agent_dict_to_state
from core.trust import TrustManager
from core.logging import get_logger
from agents.manager import AgentManager


console = Console()
logger = get_logger("workflow.nodes")


class BaseNode:
    """Базовый класс для узлов workflow."""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
    
    async def execute(self, state: WorkflowState) -> WorkflowState:
        """Выполнение узла."""
        raise NotImplementedError
    
    def __call__(self, state: WorkflowState) -> WorkflowState:
        """Синхронная обертка для выполнения."""
        # Проверяем тип входящего состояния
        if isinstance(state, str):
            # Если получили строку, создаем базовое состояние
            from .state import create_initial_state
            state = create_initial_state(state, "unknown")
        elif not isinstance(state, dict):
            # Если получили что-то другое, пытаемся преобразовать
            raise ValueError(f"Неожиданный тип состояния: {type(state)}")
        
        return asyncio.run(self.execute(state))


class StartNode(BaseNode):
    """Стартовый узел workflow."""
    
    def __init__(self):
        super().__init__("start", "Инициализация workflow")
    
    async def execute(self, state: WorkflowState) -> WorkflowState:
        """Инициализация workflow."""
        
        # Проверяем и исправляем состояние если нужно
        if not isinstance(state, dict) or "context" not in state:
            from .state import create_initial_state
            state = create_initial_state("Unknown task", "unknown")
        
        context = state.get("context", {})
        
        workflow_name = context.get("metadata", {}).get("workflow_name", "Unknown")
        task_description = context.get("task_description", "Unknown task")
        
        console.print(f"Запуск workflow: {workflow_name}")
        console.print(f"Задача: {task_description}")
        
        # Обновляем состояние
        new_state = state.copy()
        new_state["current_node"] = self.name
        if "messages" not in new_state:
            new_state["messages"] = []
        new_state["messages"].append(SystemMessage(content="Workflow инициализирован"))
        
        return new_state


class EndNode(BaseNode):
    """Финальный узел workflow."""
    
    def __init__(self):
        super().__init__("end", "Завершение workflow")
    
    async def execute(self, state: WorkflowState) -> WorkflowState:
        """Завершение workflow."""
        
        # Проверяем и исправляем состояние если нужно
        if not isinstance(state, dict) or "context" not in state:
            from .state import create_initial_state
            state = create_initial_state("Unknown task", "unknown")
        
        context = state.get("context", {})
        
        completed_stages = context.get("completed_stages", [])
        failed_stages = context.get("failed_stages", [])
        stage_outputs = context.get("stage_outputs", {})
        
        console.print("Workflow завершен")
        console.print(f"Выполнено stages: {len(completed_stages)}")
        console.print(f"Неуспешных stages: {len(failed_stages)}")
        
        if failed_stages:
            console.print(f"Ошибки: {failed_stages}")
        
        # Финализируем состояние
        new_state = state.copy()
        new_state["current_node"] = self.name
        new_state["finished"] = True
        new_state["result"] = {
            "completed_stages": completed_stages,
            "failed_stages": failed_stages,
            "stage_outputs": stage_outputs,
            "success": len(failed_stages) == 0
        }
        
        return new_state


class AgentNode(BaseNode):
    """Узел для выполнения задач агентом."""
    
    def __init__(self, 
                 name: str,
                 agent_name: str,
                 stage_config: Dict[str, Any],
                 agent_manager: AgentManager,
                 is_last_stage: bool = False,
                 mcp_manager=None,
                 workflow_id: str = None):
        super().__init__(name, stage_config.get("description", ""))
        self.agent_name = agent_name
        self.stage_config = stage_config
        self.agent_manager = agent_manager
        self.skippable = stage_config.get("skippable", False)
        self.is_last_stage = is_last_stage
        self.mcp_manager = mcp_manager
        self.workflow_id = workflow_id or "direct"
    
    async def execute(self, state: WorkflowState) -> WorkflowState:
        """Выполнение задачи агентом."""
        
        # Получаем таймаут из конфигурации stage
        timeout = self.stage_config.get("timeout", 30)
        
        try:
            logger.info(f"=== НАЧАЛО ВЫПОЛНЕНИЯ STAGE ===")
            logger.info(f"Stage: {self.name}")
            logger.info(f"Агент: {self.agent_name}")
            logger.info(f"Таймаут: {timeout}s")
            logger.info(f"Конфигурация stage: {self.stage_config}")
            logger.info(f"Состояние входа: {state}")
            
            # Выполняем с таймаутом
            result = await asyncio.wait_for(self._execute_stage(state), timeout=timeout)
            
            logger.info(f"=== STAGE ЗАВЕРШЕН УСПЕШНО ===")
            logger.info(f"Stage: {self.name}")
            logger.info(f"Результат: {result}")
            
            return result
            
        except asyncio.TimeoutError:
            error_msg = f"Таймаут выполнения stage {self.name} ({timeout}s)"
            logger.error(f"=== ТАЙМАУТ STAGE ===")
            logger.error(f"Stage: {self.name}")
            logger.error(f"Таймаут: {timeout}s")
            logger.error(f"Состояние на момент таймаута: {state}")
            console.print(f"[red]{error_msg}[/red]")
            return mark_stage_failed(state, self.name, error_msg)
        except Exception as e:
            error_msg = f"Ошибка выполнения stage {self.name}: {str(e)}"
            logger.error(f"=== ОШИБКА STAGE ===")
            logger.error(f"Stage: {self.name}")
            logger.error(f"Ошибка: {str(e)}")
            logger.error(f"Тип ошибки: {type(e)}")
            logger.error(f"Состояние на момент ошибки: {state}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            console.print(f"[red]{error_msg}[/red]")
            return mark_stage_failed(state, self.name, str(e))
    
    async def _execute_stage(self, state: WorkflowState) -> WorkflowState:
        """Внутренний метод выполнения stage."""
        
        try:
            logger.debug(f"=== _execute_stage НАЧАТ ===")
            logger.debug(f"Stage: {self.name}")
            logger.debug(f"Входящее состояние: {state}")
            
            # Проверяем и исправляем состояние если нужно
            if not isinstance(state, dict):
                logger.warning(f"Состояние не является dict: {type(state)}")
                from .state import create_initial_state
                state = create_initial_state("Unknown task", "unknown")
            
            # Инициализируем отсутствующие поля
            if "agents" not in state:
                logger.debug("Инициализация поля agents")
                state["agents"] = {}
            if "context" not in state:
                logger.debug("Инициализация поля context")
                state["context"] = {
                    "task_description": "Unknown task",
                    "current_stage": "",
                    "completed_stages": [],
                    "failed_stages": [],
                    "stage_outputs": {},
                    "user_inputs": {},
                    "metadata": {}
                }
            
            console.print(f"Выполнение stage: {self.name}")
            console.print(f"Агент: {self.agent_name}")
            console.print(f"Описание: {self.description}")
            
            logger.debug(f"Получение агента {self.agent_name}")
            # Получаем или создаем агента
            agent = await self._get_or_create_agent(state)
            logger.debug(f"Агент получен: {agent}")
            
            # Подготавливаем контекст для агента
            logger.debug("Подготовка контекста агента")
            agent_context = self._prepare_agent_context(state)
            logger.debug(f"Контекст подготовлен: {len(str(agent_context))} символов")
            
            # Выполняем задачу
            logger.debug("=== НАЧАЛО ВЫПОЛНЕНИЯ ЗАДАЧИ АГЕНТОМ ===")
            logger.debug(f"Агент: {agent}")
            logger.debug(f"Контекст: {agent_context}")
            
            result = await self._execute_agent_task(agent, agent_context, state)
            
            logger.debug(f"=== ЗАДАЧА ВЫПОЛНЕНА ===")
            logger.debug(f"Результат: {result}")
            
            # Сохраняем результат
            new_state = add_stage_output(state, self.name, result)
            new_state["current_node"] = self.name
            if "messages" not in new_state:
                new_state["messages"] = []
            new_state["messages"].append(AIMessage(content=f"Stage {self.name} выполнен"))
            
            console.print(f"Stage {self.name} завершен успешно")
            logger.info(f"Stage {self.name} завершен успешно")
            
            return new_state
            
        except Exception as e:
            logger.error(f"=== ОШИБКА В _execute_stage ===")
            logger.error(f"Stage: {self.name}")
            logger.error(f"Ошибка: {str(e)}")
            logger.error(f"Тип ошибки: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            console.print(f"Ошибка в stage {self.name}: {str(e)}")
            
            if self.skippable:
                console.print(f"Stage {self.name} пропущен (skippable=true)")
                new_state = state.copy()
                new_state["current_node"] = self.name
                return new_state
            else:
                return mark_stage_failed(state, self.name, str(e))
    
    async def _get_or_create_agent(self, state: WorkflowState) -> Dict[str, Any]:
        """Получение или создание агента для роли."""
        
        # Ищем существующего агента с нужной ролью
        for agent in state["agents"].values():
            if agent.get("name") == self.agent_name:
                return agent
        
        # Создаем нового агента
        agent_name = self.agent_name
        
        # Получаем конфигурацию роли из workflow config
        # Сначала ищем в stage_config, потом в общих ролях workflow
        role_config = None
        
        # Проверяем roles в stage_config
        stage_roles = self.stage_config.get("roles", [])
        for role in stage_roles:
            if isinstance(role, dict) and role.get("name") == self.agent_name:
                role_config = role
                break
            elif isinstance(role, str) and role == self.agent_name:
                # Если роль задана строкой, создаем базовую конфигурацию
                role_config = {"name": self.agent_name, "prompt": f"Ты {self.agent_name}"}
                break
        
        # Если не найдено, создаем базовую конфигурацию
        if not role_config:
            role_config = {"name": self.agent_name, "prompt": f"Ты {self.agent_name}"}
        
        agent = create_agent_dict(
            name=agent_name,
            role=self.agent_name,
            current_task=self.name,
            capabilities=role_config.get("capabilities", []),
            llm_model=role_config.get("llm_model", "qwen3-coder-plus")
        )
        
        # Добавляем агента в состояние
        state["agents"][agent_name] = agent
        
        return agent
    
    def _prepare_agent_context(self, state: WorkflowState) -> Dict[str, Any]:
        """Подготовка контекста для агента."""
        
        context = state["context"]
        
        return {
            "task_description": context.get("task_description", ""),
            "current_stage": self.name,
            "stage_description": self.description,
            "completed_stages": context.get("completed_stages", []),
            "stage_outputs": context.get("stage_outputs", {}),
            "user_inputs": context.get("user_inputs", {}),
            "messages": [msg.content for msg in state.get("messages", [])[-5:]]  # Последние 5 сообщений
        }
    
    async def _execute_agent_task(self, 
                                agent: Dict[str, Any], 
                                context: Dict[str, Any], 
                                state: WorkflowState) -> Dict[str, Any]:
        """Выполнение задачи агентом через LLM с поддержкой многоитерационного взаимодействия."""
        
        from .state import (start_stage_iteration, add_stage_message, can_continue_stage_iteration,
                           complete_stage_iteration, request_confirmation, process_user_confirmation)
        
        logger.info(f"=== ВЫПОЛНЕНИЕ ЗАДАЧИ АГЕНТОМ ===")
        logger.info(f"Агент: {agent['name']}")
        logger.info(f"Контекст: {context}")
        
        console.print(f"Агент {agent['name']} обрабатывает задачу...")
        
        # Проверяем, есть ли MCP серверы для этого stage
        stage_config = self.stage_config or {}
        mcp_servers = stage_config.get('mcp_servers', [])
        
        logger.info(f"MCP серверы для stage: {mcp_servers}")
        
        if not mcp_servers:
            # Заглушка для случаев без MCP
            logger.info("=== ВЫПОЛНЕНИЕ БЕЗ MCP (ЗАГЛУШКА) ===")
            await asyncio.sleep(1)
            
            return {
                "agent": agent["name"],
                "stage": self.name,
                "status": "completed",
                "output": f"Результат выполнения stage {self.name} агентом {agent['name']}",
                "context_used": context
            }
        
        # === МНОГОИТЕРАЦИОННОЕ ВЫПОЛНЕНИЕ С MCP ===
        
        try:
            logger.info("=== НАЧАЛО МНОГОИТЕРАЦИОННОГО ВЫПОЛНЕНИЯ ===")
            
            # Начинаем новую итерацию stage
            current_state = start_stage_iteration(state, self.name)
            
            # Основной цикл итераций
            while can_continue_stage_iteration(current_state):
                logger.info(f"=== ИТЕРАЦИЯ {current_state['stage_iteration']} ===")
                
                # Проверяем, ожидаем ли мы ответ пользователя
                if current_state.get("awaiting_confirmation", False):
                    logger.info("Ожидание ответа пользователя, прерываем выполнение")
                    # Возвращаем состояние с требованием пользовательского ввода
                    return {
                        "agent": agent["name"],
                        "stage": self.name,
                        "status": "awaiting_user_input",
                        "output": "Ожидание ответа пользователя",
                        "context_used": context,
                        "requires_user_input": True,
                        "user_prompt": current_state.get("human_input_prompt", "Требуется ваш ответ")
                    }
                
                # Выполняем итерацию с LLM
                llm_result, requires_input, user_prompt = await self._execute_llm_iteration(
                    agent, context, mcp_servers, current_state
                )
                
                # Добавляем ответ LLM в историю stage
                current_state = add_stage_message(current_state, "llm", llm_result)
                
                if requires_input:
                    # LLM запрашивает взаимодействие с пользователем
                    logger.info(f"LLM запрашивает взаимодействие: {user_prompt}")
                    current_state = request_confirmation(current_state, user_prompt)
                    
                    # Возвращаем состояние с требованием пользовательского ввода
                    return {
                        "agent": agent["name"],
                        "stage": self.name,
                        "status": "awaiting_user_input",
                        "output": llm_result,
                        "context_used": context,
                        "requires_user_input": True,
                        "user_prompt": user_prompt,
                        "state": current_state  # Передаем обновленное состояние
                    }
                else:
                    # LLM завершил stage или продолжает без взаимодействия
                    logger.info("LLM завершил итерацию без запроса взаимодействия")
                    break
            
            # Завершаем stage
            logger.info("=== ЗАВЕРШЕНИЕ МНОГОИТЕРАЦИОННОГО ВЫПОЛНЕНИЯ ===")
            
            final_result = {
                "agent": agent["name"],
                "stage": self.name,
                "status": "completed",
                "output": llm_result,
                "context_used": context,
                "iterations": current_state["stage_iteration"]
            }
            
            return final_result
            
        except Exception as e:
            logger.error(f"=== ОШИБКА МНОГОИТЕРАЦИОННОГО ВЫПОЛНЕНИЯ ===")
            logger.error(f"Ошибка: {str(e)}")
            logger.error(f"Тип ошибки: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            console.print(f"Ошибка многоитерационного выполнения: {e}", style="red")
            raise Exception(f"Ошибка в многоитерационном stage {self.name}: {str(e)}")
    
    async def _execute_llm_iteration(self, 
                                   agent: Dict[str, Any], 
                                   context: Dict[str, Any], 
                                   mcp_servers: List[str],
                                   state: WorkflowState) -> tuple[str, bool, Optional[str]]:
        """Выполнение одной итерации с LLM."""
        
        logger.info("=== ВЫПОЛНЕНИЕ ИТЕРАЦИИ LLM ===")
        
        try:
            from .llm_integration import WorkflowLLMIntegration
            
            # Создаем LLM интеграцию
            llm_integration = WorkflowLLMIntegration(self.agent_manager.settings_manager)
            
            # Формируем промпты
            system_prompt = self._build_system_prompt_with_mcp(agent, mcp_servers)
            user_prompt = self._build_user_prompt(context)
            
            # Выполняем итерацию с поддержкой многоитерационного взаимодействия
            result, requires_input, user_prompt_text = await llm_integration.execute_stage_with_iterations(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                mcp_servers=mcp_servers,
                agent_config=agent,
                state=state
            )
            
            logger.info(f"Результат итерации LLM: {result}")
            logger.info(f"Требует ввода: {requires_input}")
            logger.info(f"Промпт пользователя: {user_prompt_text}")
            
            return result, requires_input, user_prompt_text
            
        except Exception as e:
            logger.error(f"Ошибка выполнения итерации LLM: {str(e)}")
            raise
    
    async def process_user_response(self, 
                                  user_response: str,
                                  agent: Dict[str, Any],
                                  context: Dict[str, Any],
                                  state: WorkflowState) -> Dict[str, Any]:
        """Обработка ответа пользователя и продолжение выполнения."""
        
        from .state import process_user_confirmation, add_stage_message, can_continue_stage_iteration
        
        logger.info(f"=== ОБРАБОТКА ОТВЕТА ПОЛЬЗОВАТЕЛЯ ===")
        logger.info(f"Ответ: {user_response}")
        
        try:
            # Обрабатываем ответ пользователя
            current_state = process_user_confirmation(state, user_response)
            
            # Добавляем ответ пользователя в историю
            current_state = add_stage_message(current_state, "user", user_response)
            
            # Проверяем, можем ли продолжить итерации
            if not can_continue_stage_iteration(current_state):
                logger.warning("Достигнут лимит итераций stage")
                return {
                    "agent": agent["name"],
                    "stage": self.name,
                    "status": "completed",
                    "output": "Достигнут лимит итераций",
                    "context_used": context
                }
            
            # Получаем MCP серверы
            mcp_servers = self.stage_config.get('mcp_servers', [])
            
            # Выполняем итерацию с учетом ответа пользователя
            from .llm_integration import WorkflowLLMIntegration
            llm_integration = WorkflowLLMIntegration(self.agent_manager.settings_manager)
            
            system_prompt = self._build_system_prompt_with_mcp(agent, mcp_servers)
            user_prompt = self._build_user_prompt(context)
            
            result, requires_input, user_prompt_text = await llm_integration.process_user_response_iteration(
                user_response=user_response,
                original_system_prompt=system_prompt,
                original_user_prompt=user_prompt,
                mcp_servers=mcp_servers,
                agent_config=agent,
                state=current_state
            )
            
            # Добавляем новый ответ LLM в историю
            current_state = add_stage_message(current_state, "llm", result)
            
            if requires_input:
                # LLM снова запрашивает взаимодействие
                from .state import request_confirmation
                current_state = request_confirmation(current_state, user_prompt_text)
                
                return {
                    "agent": agent["name"],
                    "stage": self.name,
                    "status": "awaiting_user_input",
                    "output": result,
                    "context_used": context,
                    "requires_user_input": True,
                    "user_prompt": user_prompt_text,
                    "state": current_state
                }
            else:
                # LLM завершил stage
                return {
                    "agent": agent["name"],
                    "stage": self.name,
                    "status": "completed",
                    "output": result,
                    "context_used": context,
                    "iterations": current_state["stage_iteration"]
                }
                
        except Exception as e:
            logger.error(f"Ошибка обработки ответа пользователя: {str(e)}")
            raise
    
    async def _execute_with_llm_and_mcp(self, agent: Dict[str, Any], context: Dict[str, Any], mcp_servers: List[str]) -> str:
        """Выполнение задачи через LLM с доступом к MCP инструментам."""
        logger.info(f"=== ВЫПОЛНЕНИЕ С LLM И MCP ===")
        logger.info(f"Агент: {agent}")
        logger.info(f"MCP серверы: {mcp_servers}")
        
        try:
            from .llm_integration import WorkflowLLMIntegration
            
            logger.debug("Создание LLM интеграции")
            # Создаем LLM интеграцию
            llm_integration = WorkflowLLMIntegration(self.agent_manager.settings_manager)
            
            logger.debug("Построение system prompt")
            # Формируем system prompt с описанием доступных MCP инструментов
            system_prompt = self._build_system_prompt_with_mcp(agent, mcp_servers)
            logger.debug(f"System prompt: {system_prompt}")
            
            logger.debug("Построение user prompt")
            # Формируем user prompt с контекстом задачи
            user_prompt = self._build_user_prompt(context)
            logger.debug(f"User prompt: {user_prompt}")
            
            logger.info("=== ВЫЗОВ LLM ИНТЕГРАЦИИ С MCP НА УРОВНЕ STAGE ===")
            # Выполняем через LLM с MCP инструментами на уровне stage
            result = await llm_integration.execute_stage_with_mcp(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                mcp_servers=mcp_servers,
                agent_config=agent
            )
            
            logger.info(f"=== РЕЗУЛЬТАТ LLM ИНТЕГРАЦИИ ===")
            logger.info(f"Результат: {result}")
            
            return result
            
        except Exception as e:
            logger.error(f"=== ОШИБКА В _execute_with_llm_and_mcp ===")
            logger.error(f"Ошибка: {str(e)}")
            logger.error(f"Тип ошибки: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    def _build_system_prompt_with_mcp(self, agent: Dict[str, Any], mcp_servers: List[str]) -> str:
        """Создает system prompt с описанием доступных MCP инструментов."""
        base_prompt = agent.get('prompt', f"Ты {agent.get('role', 'агент')}.")
        
        # Добавляем текущую дату и время
        from datetime import datetime
        current_time = datetime.now()
        context_info = f"""
Текущая дата и время: {current_time.strftime('%Y-%m-%d %H:%M:%S')}
Язык общения: русский"""
        
        mcp_description = ""
        if mcp_servers:
            mcp_description = "\nУ тебя есть доступ к MCP инструментам. Используй их для получения актуальных данных."
        
        return f"{base_prompt}\n{context_info}\n{mcp_description}"
    
    def _build_user_prompt_with_tools(self, context: Dict[str, Any], tools: List[Dict]) -> str:
        """Создает user prompt с контекстом задачи и схемами инструментов."""
        task_description = context.get('task_description', 'Выполни анализ активности')
        
        prompt = f"""Задача: {task_description}

Контекст:
- Период анализа: последние 7 дней
- Требуется получить данные о work items и активности пользователя
- Проанализируй полученные данные и предоставь краткий отчет

Доступные MCP инструменты:"""
        
        # Добавляем схемы инструментов
        for tool in tools:
            prompt += f"\n\n- {tool['name']}: {tool['description']}"
            
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
                        prompt += "\n  Параметры:\n" + "\n".join(params)
        
        prompt += """

Для вызова инструментов используй JSON формат в блоке кода:

```json
{
  "tool_calls": [
    {
      "name": "tool_name",
      "parameters": {
        "param1": "value1",
        "param2": "value2"
      }
    }
  ]
}
```

Или для одного инструмента:

```json
{
  "name": "tool_name", 
  "parameters": {
    "param1": "value1"
  }
}
```

Старый формат TOOL_CALL:tool_name:parameters_json также поддерживается для совместимости."""
        return prompt
    
    def _build_user_prompt(self, context: Dict[str, Any]) -> str:
        """Создает user prompt с контекстом задачи."""
        task_description = context.get('task_description', 'Выполни анализ активности')
        
        prompt = f"""Задача: {task_description}

Контекст:
- Период анализа: последние 7 дней (2025-12-07 до 2025-12-14)
- Требуется получить данные о work items и активности пользователя
- Проанализируй полученные данные и предоставь краткий отчет

ОБЯЗАТЕЛЬНО выполни следующие шаги:
1. Получи информацию о текущем пользователе
2. Используй полученный логин пользователя для следующих вызовов
3. Получи список work items за указанный период для этого пользователя
4. Получи данные об активности пользователя (используй ВСЕ доступные категории активности)
5. Проанализируй данные и создай отчет

После получения данных используй команду:
CONFIRM_DATA: Данные за период корректны? Логин пользователя: [логин], найдено work items: [количество], активность получена?

Если пользователь подтвердит данные, используй:
STAGE_COMPLETE

Если пользователь запросит изменения, внеси их и снова запроси подтверждение.

Используй доступные MCP инструменты для получения всех необходимых данных."""
        
        return prompt


class HumanInputNode(BaseNode):
    """Узел для запроса пользовательского ввода."""
    
    def __init__(self, name: str, prompt: str, input_key: str):
        super().__init__(name, f"Запрос пользовательского ввода: {prompt}")
        self.prompt = prompt
        self.input_key = input_key
    
    async def execute(self, state: WorkflowState) -> WorkflowState:
        """Запрос пользовательского ввода."""
        
        console.print(f"Требуется пользовательский ввод для: {self.name}")
        
        # Устанавливаем флаг необходимости пользовательского ввода
        new_state = require_human_input(state, self.prompt)
        new_state["current_node"] = self.name
        
        return new_state


class ConditionalNode(BaseNode):
    """Узел для условных переходов."""
    
    def __init__(self, 
                 name: str, 
                 condition_func: Callable[[WorkflowState], bool],
                 true_node: str,
                 false_node: str):
        super().__init__(name, "Условный переход")
        self.condition_func = condition_func
        self.true_node = true_node
        self.false_node = false_node
    
    async def execute(self, state: WorkflowState) -> WorkflowState:
        """Выполнение условного перехода."""
        
        try:
            result = self.condition_func(state)
            next_node = self.true_node if result else self.false_node
            
            console.print(f"Условный переход: {self.name} -> {next_node}")
            
            new_state = state.copy()
            new_state["current_node"] = self.name
            new_state["next_node"] = next_node
            
            return new_state
            
        except Exception as e:
            console.print(f"Ошибка в условном переходе {self.name}: {str(e)}")
            return mark_stage_failed(state, self.name, str(e))


# Фабрика узлов
def create_node(node_type: str, **kwargs) -> BaseNode:
    """Фабрика для создания узлов."""
    
    node_types = {
        "start": StartNode,
        "end": EndNode,
        "agent": AgentNode,
        "human_input": HumanInputNode,
        "conditional": ConditionalNode
    }
    
    if node_type not in node_types:
        raise ValueError(f"Неизвестный тип узла: {node_type}")
    
    return node_types[node_type](**kwargs)
