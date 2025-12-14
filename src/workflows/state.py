"""
Система состояний для LangGraph workflow.
"""

from typing import Dict, Any, List, Optional, TypedDict, Annotated
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph.message import add_messages


class WorkflowContext(BaseModel):
    """Контекст выполнения workflow."""
    
    task_description: str = ""
    current_stage: str = ""
    completed_stages: List[str] = Field(default_factory=list)
    failed_stages: List[str] = Field(default_factory=list)
    stage_outputs: Dict[str, Any] = Field(default_factory=dict)
    user_inputs: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentState(BaseModel):
    """Состояние агента в workflow."""
    
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
    
    # Контекст workflow
    context: WorkflowContext
    
    # Активные агенты
    agents: Dict[str, AgentState]
    
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
    agents: Optional[Dict[str, AgentState]] = None
) -> WorkflowState:
    """Создание начального состояния workflow."""
    
    return WorkflowState(
        messages=[HumanMessage(content=task_description)],
        context=WorkflowContext(
            task_description=task_description,
            metadata={"workflow_name": workflow_name}
        ),
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
    
    context_dict = state["context"].model_dump()
    context_dict.update(updates)
    
    new_state = state.copy()
    new_state["context"] = WorkflowContext(**context_dict)
    
    return new_state


def add_stage_output(state: WorkflowState, stage: str, output: Any) -> WorkflowState:
    """Добавление результата выполнения stage."""
    
    context = state["context"]
    context.stage_outputs[stage] = output
    context.completed_stages.append(stage)
    
    return update_context(state, 
                         stage_outputs=context.stage_outputs,
                         completed_stages=context.completed_stages)


def mark_stage_failed(state: WorkflowState, stage: str, error: str) -> WorkflowState:
    """Отметка stage как неуспешного."""
    
    context = state["context"]
    context.failed_stages.append(stage)
    
    new_state = update_context(state, failed_stages=context.failed_stages)
    new_state["errors"].append(f"Stage {stage}: {error}")
    
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
    context.user_inputs[key] = value
    
    new_state = update_context(state, user_inputs=context.user_inputs)
    new_state["human_input_required"] = False
    new_state["human_input_prompt"] = None
    
    return new_state
