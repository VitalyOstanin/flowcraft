"""
Система состояний для LangGraph workflow.
"""

from typing import Dict, Any, List, Optional, TypedDict, Annotated
from pydantic import BaseModel, Field, ConfigDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph.message import add_messages


class AgentState(BaseModel):
    """Состояние агента в workflow."""
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    name: str
    role: str
    current_task: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    memory: Dict[str, Any] = Field(default_factory=dict)
    llm_model: str = "qwen3-coder-plus"


class WorkflowState(TypedDict):
    """Основное состояние LangGraph workflow."""
    
    # Сообщения между узлами
    messages: Annotated[List[BaseMessage], add_messages]
    
    # Контекст workflow (обычный словарь для сериализации)
    context: Dict[str, Any]
    
    # Активные агенты (словари для сериализации)
    agents: Dict[str, Dict[str, Any]]
    
    # Текущий узел
    current_node: str
    
    # Следующий узел для выполнения
    next_node: Optional[str]
    
    # Флаг завершения
    finished: bool
    
    # Результат выполнения
    result: Optional[Dict[str, Any]]
    
    # Ошибки
    errors: List[str]
    
    # Требуется ли вмешательство пользователя
    human_input_required: bool
    
    # Данные для human-in-the-loop
    human_input_prompt: Optional[str]


def create_initial_state(
    task_description: str,
    workflow_name: str,
    agents: Optional[Dict[str, Dict[str, Any]]] = None
) -> WorkflowState:
    """Создание начального состояния workflow."""
    
    return WorkflowState(
        messages=[HumanMessage(content=task_description)],
        context={
            "task_description": task_description,
            "current_stage": "",
            "completed_stages": [],
            "failed_stages": [],
            "stage_outputs": {},
            "user_inputs": {},
            "metadata": {"workflow_name": workflow_name}
        },
        agents=agents or {},
        current_node="start",
        next_node=None,
        finished=False,
        result=None,
        errors=[],
        human_input_required=False,
        human_input_prompt=None
    )


def update_context(state: WorkflowState, **updates) -> WorkflowState:
    """Обновление контекста workflow."""
    
    new_state = state.copy()
    new_state["context"] = state["context"].copy()
    new_state["context"].update(updates)
    
    return new_state


def add_stage_output(state: WorkflowState, stage: str, output: Any) -> WorkflowState:
    """Добавление результата выполнен��я stage."""
    
    context = state["context"]
    new_stage_outputs = context["stage_outputs"].copy()
    new_stage_outputs[stage] = output
    
    new_completed_stages = context["completed_stages"].copy()
    new_completed_stages.append(stage)
    
    return update_context(state, 
                         stage_outputs=new_stage_outputs,
                         completed_stages=new_completed_stages)


def mark_stage_failed(state: WorkflowState, stage: str, error: str) -> WorkflowState:
    """Отметка stage как неуспешного."""
    
    context = state["context"]
    new_failed_stages = context["failed_stages"].copy()
    new_failed_stages.append(stage)
    
    new_state = update_context(state, failed_stages=new_failed_stages)
    new_errors = new_state["errors"].copy()
    new_errors.append(f"Stage {stage}: {error}")
    new_state["errors"] = new_errors
    
    return new_state


def require_human_input(state: WorkflowState, prompt: str) -> WorkflowState:
    """Запрос вмешательства пользователя."""
    
    new_state = state.copy()
    new_state["human_input_required"] = True
    new_state["human_input_prompt"] = prompt
    
    return new_state


def add_user_input(state: WorkflowState, key: str, value: Any) -> WorkflowState:
    """Добавление пользовательского ввода."""
    
    context = state["context"]
    new_user_inputs = context["user_inputs"].copy()
    new_user_inputs[key] = value
    
    new_state = update_context(state, user_inputs=new_user_inputs)
    new_state["human_input_required"] = False
    new_state["human_input_prompt"] = None
    
    return new_state


def create_agent_dict(name: str, role: str, current_task: Optional[str] = None,
                     capabilities: List[str] = None, llm_model: str = "qwen3-coder-plus") -> Dict[str, Any]:
    """Создание словаря агента для сериализации."""
    
    return {
        "name": name,
        "role": role,
        "current_task": current_task,
        "capabilities": capabilities or [],
        "memory": {},
        "llm_model": llm_model
    }


def agent_dict_to_state(agent_dict: Dict[str, Any]) -> AgentState:
    """Преобразование словаря агента в AgentState."""
    
    return AgentState(
        name=agent_dict.get("name", ""),
        role=agent_dict.get("role", ""),
        current_task=agent_dict.get("current_task"),
        capabilities=agent_dict.get("capabilities", []),
        memory=agent_dict.get("memory", {}),
        llm_model=agent_dict.get("llm_model", "qwen3-coder-plus")
    )
