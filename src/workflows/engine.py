"""
Основной движок LangGraph workflow.
"""

import asyncio
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .state import WorkflowState, create_initial_state, add_user_input
from .nodes import BaseNode, StartNode, EndNode, AgentNode, HumanInputNode, ConditionalNode
from .subgraphs import get_registry, BaseSubgraph
from agents.manager import AgentManager
from core.trust import TrustManager


console = Console()


class WorkflowEngine:
    """Основной движок для выполнения LangGraph workflow."""
    
    def __init__(self, 
                 agent_manager: AgentManager,
                 trust_manager: TrustManager,
                 checkpoint_dir: Optional[str] = None):
        self.agent_manager = agent_manager
        self.trust_manager = trust_manager
        self.subgraph_registry = get_registry()
        
        # Настройка checkpoints
        if checkpoint_dir:
            self.checkpoint_dir = Path(checkpoint_dir)
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
            # TODO: Реализовать файловый checkpoint saver
            self.checkpointer = MemorySaver()
        else:
            self.checkpointer = MemorySaver()
        
        self._compiled_graphs: Dict[str, Any] = {}
    
    async def execute_workflow(self, 
                             workflow_config: Dict[str, Any],
                             task_description: str,
                             thread_id: Optional[str] = None) -> Dict[str, Any]:
        """Выполнение workflow."""
        
        workflow_name = workflow_config.get("name", "unknown")
        
        console.print(f"Запуск workflow: {workflow_name}")
        console.print(f"Задача: {task_description}")
        
        try:
            # Создаем граф из конфигурации
            graph = await self._build_graph_from_config(workflow_config)
            
            # Создаем начальное состояние
            initial_state = create_initial_state(
                task_description=task_description,
                workflow_name=workflow_name
            )
            
            # Настраиваем конфигурацию выполнения
            config = {
                "configurable": {
                    "thread_id": thread_id or f"workflow_{workflow_name}_{asyncio.get_event_loop().time()}"
                }
            }
            
            # Выполняем workflow с прогресс-баром
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                
                task = progress.add_task("Выполнение workflow...", total=None)
                
                result_state = await self._execute_with_human_loop(
                    graph, initial_state, config, progress, task
                )
            
            # Возвращаем результат
            result = result_state.get("result", {})
            
            if result.get("success", False):
                console.print("Workflow завершен успешно!")
            else:
                console.print("Workflow завершен с ошибками")
                if result_state.get("errors"):
                    for error in result_state["errors"]:
                        console.print(f"  {error}")
            
            return result
            
        except Exception as e:
            console.print(f"Критическая ошибка в workflow: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "completed_stages": [],
                "failed_stages": []
            }
    
    async def _build_graph_from_config(self, workflow_config: Dict[str, Any]) -> Any:
        """Построение LangGraph из конфигурации workflow."""
        
        workflow_name = workflow_config.get("name", "unknown")
        
        # Проверяем кэш
        if workflow_name in self._compiled_graphs:
            return self._compiled_graphs[workflow_name]
        
        # Создаем новый граф
        graph = StateGraph(WorkflowState)
        
        # Добавляем стартовый узел
        start_node = StartNode()
        graph.add_node("start", start_node)
        
        # Добавляем финальный узел
        end_node = EndNode()
        graph.add_node("end", end_node)
        
        # Обрабатываем stages из конфигурации
        stages = workflow_config.get("stages", [])
        previous_stage = "start"
        
        for i, stage_config in enumerate(stages):
            stage_name = stage_config.get("name", f"stage_{i}")
            
            # Проверяем, является ли stage подграфом
            if stage_config.get("type") == "subgraph":
                await self._add_subgraph_to_graph(graph, stage_config, stage_name)
            else:
                # Обычный stage с агентами
                await self._add_stage_to_graph(graph, stage_config, stage_name)
            
            # Добавляем связь с предыдущим stage
            if previous_stage:
                graph.add_edge(previous_stage, stage_name)
            
            previous_stage = stage_name
        
        # Связываем последний stage с концом
        if previous_stage and previous_stage != "start":
            graph.add_edge(previous_stage, "end")
        else:
            # Если нет stages, связываем start с end
            graph.add_edge("start", "end")
        
        # Компилируем граф с checkpointer
        compiled_graph = graph.compile(checkpointer=self.checkpointer)
        
        # Кэшируем
        self._compiled_graphs[workflow_name] = compiled_graph
        
        return compiled_graph
    
    async def _add_stage_to_graph(self, 
                                graph: StateGraph, 
                                stage_config: Dict[str, Any], 
                                stage_name: str):
        """Добавление обычного stage в граф."""
        
        # Получаем роли для stage
        roles = stage_config.get("roles", [])
        
        if not roles:
            raise ValueError(f"Stage {stage_name}: не указаны роли")
        
        # Пока что используем первую роль (в будущем можно добавить логику выбора)
        primary_role = roles[0] if isinstance(roles[0], str) else roles[0].get("name")
        
        # Создаем узел агента
        agent_node = AgentNode(
            name=stage_name,
            agent_role=primary_role,
            stage_config=stage_config,
            agent_manager=self.agent_manager
        )
        
        graph.add_node(stage_name, agent_node)
    
    async def _add_subgraph_to_graph(self, 
                                   graph: StateGraph, 
                                   stage_config: Dict[str, Any], 
                                   stage_name: str):
        """Добавление подграфа в основной граф."""
        
        subgraph_name = stage_config.get("subgraph")
        
        if not subgraph_name:
            raise ValueError(f"Stage {stage_name}: не указано имя подграфа")
        
        subgraph = self.subgraph_registry.get_subgraph(subgraph_name)
        
        if subgraph is None:
            raise ValueError(f"Подграф не найден: {subgraph_name}")
        
        # Создаем узел-обертку для подграфа
        subgraph_node = SubgraphWrapperNode(stage_name, subgraph)
        graph.add_node(stage_name, subgraph_node)
    
    async def _execute_with_human_loop(self, 
                                     graph: Any,
                                     initial_state: WorkflowState,
                                     config: Dict[str, Any],
                                     progress: Progress,
                                     task_id) -> WorkflowState:
        """Выполнение workflow с поддержкой human-in-the-loop."""
        
        current_state = initial_state
        
        async for state_update in graph.astream(initial_state, config):
            # Обновляем состояние
            for node_name, node_state in state_update.items():
                current_state = node_state
                
                # Обновляем прогресс
                progress.update(task_id, description=f"Выполняется: {node_name}")
                
                # Проверяем, нужен ли пользовательский ввод
                if current_state.get("human_input_required", False):
                    current_state = await self._handle_human_input(current_state, graph, config)
                
                # Проверяем завершение
                if current_state.get("finished", False):
                    progress.update(task_id, description="Завершено")
                    return current_state
        
        return current_state
    
    async def _handle_human_input(self, 
                                state: WorkflowState,
                                graph: Any,
                                config: Dict[str, Any]) -> WorkflowState:
        """Обработка запроса пользовательского ввода."""
        
        prompt = state.get("human_input_prompt", "Требуется пользовательский ввод:")
        
        console.print(f"{prompt}")
        
        # Запрашиваем ввод пользователя
        user_input = console.input("Ваш ответ: ")
        
        # Обновляем состояние с пользовательским вводом
        updated_state = add_user_input(state, "human_response", user_input)
        
        # Продолжаем выполнение
        return updated_state
    
    def get_workflow_status(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Получение статуса выполнения workflow."""
        
        try:
            # Получаем последнее состояние из checkpointer
            config = {"configurable": {"thread_id": thread_id}}
            
            # TODO: Реализовать получение состояния из checkpointer
            # state = self.checkpointer.get(config)
            
            return {
                "thread_id": thread_id,
                "status": "unknown",
                "message": "Статус недоступен (требуется реализация)"
            }
            
        except Exception as e:
            return {
                "thread_id": thread_id,
                "status": "error",
                "error": str(e)
            }
    
    def list_active_workflows(self) -> List[Dict[str, Any]]:
        """Список активных workflow."""
        
        # TODO: Реализовать получение списка из checkpointer
        return []
    
    async def pause_workflow(self, thread_id: str) -> bool:
        """Приостановка workflow."""
        
        # TODO: Реализовать приостановку
        console.print(f"Приостановка workflow {thread_id} (не реализовано)")
        return False
    
    async def resume_workflow(self, thread_id: str) -> bool:
        """Возобновление workflow."""
        
        # TODO: Реализовать возобновление
        console.print(f"Возобновление workflow {thread_id} (не реализовано)")
        return False
    
    async def cancel_workflow(self, thread_id: str) -> bool:
        """Отмена workflow."""
        
        # TODO: Реализовать отмену
        console.print(f"Отмена workflow {thread_id} (не реализовано)")
        return False


class SubgraphWrapperNode(BaseNode):
    """Узел-обертка для выполнения подграфов."""
    
    def __init__(self, name: str, subgraph: BaseSubgraph):
        super().__init__(name, subgraph.description)
        self.subgraph = subgraph
    
    async def execute(self, state: WorkflowState) -> WorkflowState:
        """Выполнение подграфа."""
        
        console.print(f"Выполнение подграфа: {self.subgraph.name}")
        
        try:
            # Выполняем подграф
            result_state = await self.subgraph.execute(state)
            
            console.print(f"Подграф {self.subgraph.name} завершен")
            
            return result_state
            
        except Exception as e:
            console.print(f"Ошибка в подграфе {self.subgraph.name}: {str(e)}")
            
            from .state import mark_stage_failed
            return mark_stage_failed(state, self.name, str(e))
