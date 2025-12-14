"""
Базовые узлы для LangGraph workflow.
"""

import asyncio
from typing import Dict, Any, List, Optional, Callable
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from rich.console import Console

from workflows.state import WorkflowState, add_stage_output, mark_stage_failed, require_human_input, create_agent_dict, agent_dict_to_state
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
        """Выполнение задачи агентом."""
        
        console.print(f"Агент {agent['name']} обрабатывает задачу...")
        
        # Проверяем, есть ли MCP серверы для этого stage
        stage_config = self.stage_config or {}
        mcp_servers = stage_config.get('mcp_servers', [])
        
        if 'youtrack-mcp' in mcp_servers and agent.get('role') == 'analyst':
            # Выполняем реальный анализ активности через YouTrack MCP (прямое соединение)
            try:
                result = await self._execute_youtrack_analysis_direct(context)
                return {
                    "agent": agent["name"],
                    "stage": self.name,
                    "status": "completed", 
                    "output": result,
                    "context_used": context
                }
            except Exception as e:
                console.print(f"Ошибка YouTrack анализа: {e}", style="red")
        
        # Заглушка для других случаев
        await asyncio.sleep(1)
        
        return {
            "agent": agent["name"],
            "stage": self.name,
            "status": "completed",
            "output": f"Результат выполнения stage {self.name} агентом {agent['name']}",
            "context_used": context
        }
    
    async def _execute_youtrack_analysis_direct(self, context: Dict[str, Any]) -> str:
        """Прямое выполнение анализа активности в YouTrack."""
        try:
            from datetime import datetime, timedelta
            import json
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            
            # Период за последние 7 дней
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            # Получаем настройки YouTrack из конфигурации MCP
            mcp_config = None
            if hasattr(self.agent_manager, 'settings_manager'):
                settings = self.agent_manager.settings_manager.settings
                for server_config in settings.mcp_servers:
                    if server_config.name == 'youtrack-mcp':
                        mcp_config = server_config
                        break
            
            if not mcp_config:
                return "Конфигурация YouTrack MCP не найдена в настройках"
            
            server_params = StdioServerParameters(
                command=mcp_config.command,
                args=mcp_config.args,
                env=mcp_config.env or {}
            )
            
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # Получаем пользователя
                    user_result = await session.call_tool('user_current', {})
                    user_data = json.loads(user_result.content[0].text)
                    user_info = user_data.get('payload', {}).get('user', {})
                    
                    # Получаем work items
                    workitems_result = await session.call_tool('workitems_list', {
                        'startDate': start_date.strftime('%Y-%m-%d'),
                        'endDate': end_date.strftime('%Y-%m-%d')
                    })
                    workitems_data = json.loads(workitems_result.content[0].text)
                    workitems = workitems_data.get('payload', {}).get('items', [])
                    
                    # Формируем отчет
                    if workitems:
                        total_minutes = sum(item.get('duration', {}).get('minutes', 0) for item in workitems)
                        total_hours = total_minutes / 60
                        
                        report = f"=== Анализ активности пользователя {user_info.get('name', 'N/A')} ===\n\n"
                        report += f"Период: {start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}\n"
                        report += f"Найдено work items: {len(workitems)}\n"
                        report += f"Общее время работы: {total_hours:.1f} часов ({total_minutes} минут)\n"
                        report += f"Workflow: {self.workflow_id or 'direct'}\n\n"
                        
                        # Топ-5 задач по времени
                        by_issue = {}
                        for item in workitems:
                            issue_id = item.get('issue', {}).get('idReadable', 'N/A')
                            if issue_id not in by_issue:
                                by_issue[issue_id] = {'minutes': 0}
                            by_issue[issue_id]['minutes'] += item.get('duration', {}).get('minutes', 0)
                        
                        report += "Топ задач по времени:\n"
                        for issue_id, data in sorted(by_issue.items(), key=lambda x: x[1]['minutes'], reverse=True)[:5]:
                            hours = data['minutes'] / 60
                            report += f"• {issue_id}: {hours:.1f}ч ({data['minutes']}м)\n"
                        
                        return report
                    else:
                        return f"Анализ активности пользователя {user_info.get('name', 'N/A')}: work items за последние 7 дней не найдены"
                        
        except Exception as e:
            return f"Ошибка анализа активности: {str(e)}"


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
