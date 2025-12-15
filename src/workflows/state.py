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
    
    # === НОВЫЕ ПОЛЯ ДЛЯ МНОГОИТЕРАЦИОННОГО ВЗАИМОДЕЙСТВИЯ ===
    
    # Номер итерации в текущем stage
    stage_iteration: int
    
    # История сообщений в рамках текущего stage
    stage_conversation: List[Dict[str, Any]]
    
    # Флаг ожидания подтверждения
    awaiting_confirmation: bool
    
    # Максимальное количество итераций для stage
    max_stage_iterations: int


def create_initial_state(
    task_description: str,
    workflow_name: str,
    agents: Optional[Dict[str, Dict[str, Any]]] = None,
    max_stage_iterations: int = 5
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
        human_input_prompt=None,
        # Новые поля
        stage_iteration=0,
        stage_conversation=[],
        awaiting_confirmation=False,
        max_stage_iterations=max_stage_iterations
    )


def update_context(state: WorkflowState, **updates) -> WorkflowState:
    """Обновление контекста workflow."""
    
    new_state = state.copy()
    new_state["context"] = state["context"].copy()
    new_state["context"].update(updates)
    
    return new_state


def add_stage_output(state: WorkflowState, stage: str, output: Any) -> WorkflowState:
    """Добавление результата выполнения stage."""
    
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


# === НОВЫЕ ФУНКЦИИ ДЛЯ МНОГОИТЕРАЦИОННОГО ВЗАИМОДЕЙСТВИЯ ===

def start_stage_iteration(state: WorkflowState, stage_name: str) -> WorkflowState:
    """Начало новой итерации stage."""
    
    new_state = state.copy()
    new_state["stage_iteration"] = state["stage_iteration"] + 1
    new_state["awaiting_confirmation"] = False
    
    # Обновляем контекст
    new_state = update_context(new_state, current_stage=stage_name)
    
    return new_state


def add_stage_message(state: WorkflowState, role: str, content: str, metadata: Optional[Dict] = None) -> WorkflowState:
    """Добавление сообщения в историю stage."""
    
    new_state = state.copy()
    new_conversation = state["stage_conversation"].copy()
    
    message = {
        "role": role,  # "llm", "user", "system"
        "content": content,
        "iteration": state["stage_iteration"],
        "timestamp": None,  # Можно добавить timestamp
        "metadata": metadata or {}
    }
    
    new_conversation.append(message)
    new_state["stage_conversation"] = new_conversation
    
    return new_state


def request_confirmation(state: WorkflowState, prompt: str, data: Optional[Dict] = None) -> WorkflowState:
    """Запрос подтверждения от пользователя."""
    
    new_state = state.copy()
    new_state["awaiting_confirmation"] = True
    new_state["human_input_required"] = True
    new_state["human_input_prompt"] = prompt
    
    # Добавляем сообщение в историю stage
    new_state = add_stage_message(new_state, "system", f"CONFIRMATION_REQUEST: {prompt}", 
                                 {"data": data})
    
    return new_state


def process_user_confirmation(state: WorkflowState, user_response: str) -> WorkflowState:
    """Обработка ответа пользователя на запрос подтверждения."""
    
    new_state = state.copy()
    new_state["awaiting_confirmation"] = False
    new_state["human_input_required"] = False
    new_state["human_input_prompt"] = None
    
    # Добавляем ответ пользователя в историю
    new_state = add_stage_message(new_state, "user", user_response)
    
    return new_state


def complete_stage_iteration(state: WorkflowState, stage_name: str, output: Any, is_final: bool = False) -> WorkflowState:
    """Завершение итерации stage."""
    
    new_state = state.copy()
    
    if is_final:
        # Финальное завершение stage
        new_state = add_stage_output(new_state, stage_name, output)
        new_state["stage_iteration"] = 0
        new_state["stage_conversation"] = []
        new_state["awaiting_confirmation"] = False
    else:
        # Промежуточное завершение итерации
        new_state = add_stage_message(new_state, "llm", str(output), {"iteration_complete": True})
    
    return new_state


def can_continue_stage_iteration(state: WorkflowState) -> bool:
    """Проверка возможности продолжения итераций stage."""
    
    return state["stage_iteration"] < state["max_stage_iterations"]


def get_stage_conversation_context(state: WorkflowState) -> str:
    """Получение контекста разговора в рамках stage для LLM."""
    
    conversation = state["stage_conversation"]
    if not conversation:
        return ""
    
    context_parts = [f"=== ИСТОРИЯ ВЗАИМОДЕЙСТВИЯ В STAGE (итерация {state['stage_iteration']}) ==="]
    
    for msg in conversation:
        role_label = {
            "llm": "LLM",
            "user": "ПОЛЬЗОВАТЕЛЬ", 
            "system": "СИСТЕМА"
        }.get(msg["role"], msg["role"].upper())
        
        context_parts.append(f"{role_label}: {msg['content']}")
    
    context_parts.append("=== КОНЕЦ ИСТОРИИ ===")
    
    return "\n".join(context_parts)


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
