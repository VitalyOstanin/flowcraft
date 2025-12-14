"""
Базовые узлы для LangGraph workflow.
"""

import asyncio
from typing import Dict, Any, List, Optional, Callable
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from rich.console import Console

from .state import WorkflowState, add_stage_output, mark_stage_failed, require_human_input, create_agent_dict, agent_dict_to_state
from core.trust import TrustManager
from agents.manager import AgentManager


console = Console()


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
                 agent_role: str,
                 stage_config: Dict[str, Any],
                 agent_manager: AgentManager,
                 is_last_stage: bool = False,
                 mcp_manager=None,
                 workflow_id: str = None):
        super().__init__(name, stage_config.get("description", ""))
        self.agent_role = agent_role
        self.stage_config = stage_config
        self.agent_manager = agent_manager
        self.skippable = stage_config.get("skippable", False)
        self.is_last_stage = is_last_stage
        self.mcp_manager = mcp_manager
        self.workflow_id = workflow_id or "direct"
    
    async def execute(self, state: WorkflowState) -> WorkflowState:
        """Выполнение задачи агентом."""
        
        try:
            # Проверяем и исправляем состояние если нужно
            if not isinstance(state, dict):
                from .state import create_initial_state
                state = create_initial_state("Unknown task", "unknown")
            
            # Инициализируем отсутствующие поля
            if "agents" not in state:
                state["agents"] = {}
            if "context" not in state:
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
            console.print(f"Роль агента: {self.agent_role}")
            console.print(f"Описание: {self.description}")
            
            # Получаем или создаем агента
            agent = await self._get_or_create_agent(state)
            
            # Подготавливаем контекст для агента
            agent_context = self._prepare_agent_context(state)
            
            # Выполняем задачу
            result = await self._execute_agent_task(agent, agent_context, state)
            
            # Сохраняем результат
            new_state = add_stage_output(state, self.name, result)
            new_state["current_node"] = self.name
            if "messages" not in new_state:
                new_state["messages"] = []
            new_state["messages"].append(AIMessage(content=f"Stage {self.name} выполнен"))
            
            console.print(f"Stage {self.name} завершен успешно")
            
            return new_state
            
        except Exception as e:
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
            if agent.get("role") == self.agent_role:
                return agent
        
        # Создаем нового агента
        agent_name = f"{self.agent_role}_{len(state['agents'])}"
        
        # Получаем конфигурацию роли из workflow config
        # Сначала ищем в stage_config, потом в общих ролях workflow
        role_config = None
        
        # Проверяем roles в stage_config
        stage_roles = self.stage_config.get("roles", [])
        for role in stage_roles:
            if isinstance(role, dict) and role.get("name") == self.agent_role:
                role_config = role
                break
            elif isinstance(role, str) and role == self.agent_role:
                # Если роль задана строкой, создаем базовую конфигурацию
                role_config = {"name": self.agent_role, "prompt": f"Ты {self.agent_role}"}
                break
        
        # Если не найдено, создаем базовую конфигурацию
        if not role_config:
            role_config = {"name": self.agent_role, "prompt": f"Ты {self.agent_role}"}
        
        agent = create_agent_dict(
            name=agent_name,
            role=self.agent_role,
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
        """Выполнение задачи агентом через LLM с доступом к MCP инструментам."""
        
        console.print(f"Агент {agent['name']} обрабатывает задачу...")
        
        # Проверяем, есть ли MCP серверы для этого stage
        stage_config = self.stage_config or {}
        mcp_servers = stage_config.get('mcp_servers', [])
        
        if mcp_servers:
            # Выполняем задачу через LLM с доступом к MCP инструментам
            try:
                result = await self._execute_with_llm_and_mcp(agent, context, mcp_servers)
                return {
                    "agent": agent["name"],
                    "stage": self.name,
                    "status": "completed", 
                    "output": result,
                    "context_used": context
                }
            except Exception as e:
                console.print(f"Ошибка выполнения с MCP: {e}", style="red")
        
        # Заглушка для других случаев
        await asyncio.sleep(1)
        
        return {
            "agent": agent["name"],
            "stage": self.name,
            "status": "completed",
            "output": f"Результат выполнения stage {self.name} агентом {agent['name']}",
            "context_used": context
        }
    
    async def _execute_with_llm_and_mcp(self, agent: Dict[str, Any], context: Dict[str, Any], mcp_servers: List[str]) -> str:
        """Выполнение задачи через LLM с доступом к MCP инструментам."""
        from .llm_integration import WorkflowLLMIntegration
        
        # Создаем LLM интеграцию
        llm_integration = WorkflowLLMIntegration(self.agent_manager.settings_manager)
        
        # Формируем system prompt с описанием доступных MCP инструментов
        system_prompt = self._build_system_prompt_with_mcp(agent, mcp_servers)
        
        # Формируем user prompt с контекстом задачи
        user_prompt = self._build_user_prompt(context)
        
        # Выполняем через LLM с MCP инструментами (только от разрешенных серверов)
        result = await llm_integration.execute_with_mcp_tools(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            mcp_servers=mcp_servers,
            agent_config=agent
        )
        
        return result
    
    def _build_system_prompt_with_mcp(self, agent: Dict[str, Any], mcp_servers: List[str]) -> str:
        """Создает system prompt с описанием доступных MCP инструментов."""
        base_prompt = agent.get('prompt', f"Ты {agent.get('role', 'агент')}.")
        
        mcp_description = ""
        if 'youtrack-mcp' in mcp_servers:
            mcp_description += """
У тебя есть доступ к YouTrack MCP инструментам для анализа активности:
- workitems_list: получить список work items за период
- issues_search: поиск задач по критериям  
- user_current: получить текущего пользователя
- issues_starred_list: получить избранные задачи

Используй эти инструменты для получения актуальных данных из YouTrack.
"""
        
        return f"{base_prompt}\n{mcp_description}"
    
    def _build_user_prompt(self, context: Dict[str, Any]) -> str:
        """Создает user prompt с контекстом задачи."""
        task_description = context.get('task_description', 'Выполни анализ активности')
        
        prompt = f"""Задача: {task_description}

Контекст:
- Период анализа: последние 7 дней
- Требуется получить данные о work items и активности пользователя
- Проанализируй полученные данные и предоставь краткий отчет

Используй доступные MCP инструменты для получения актуальных данных."""
        
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
