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
                 checkpoint_dir: Optional[str] = None,
                 mcp_manager=None):
        self.agent_manager = agent_manager
        self.trust_manager = trust_manager
        self.mcp_manager = mcp_manager
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
        
        from core.logging import get_logger
        logger = get_logger("workflow.engine")
        
        workflow_name = workflow_config.get("name", "unknown")
        workflow_id = f"{workflow_name}_{asyncio.get_event_loop().time()}"
        
        logger.info(f"=== ЗАПУСК WORKFLOW ===")
        logger.info(f"Workflow: {workflow_name}")
        logger.info(f"ID: {workflow_id}")
        logger.info(f"Задача: {task_description}")
        logger.info(f"Конфигурация: {workflow_config}")
        
        console.print(f"Запуск workflow: {workflow_name}")
        console.print(f"Задача: {task_description}")
        
        # Запускаем MCP серверы для этого workflow (временно отключено из-за зависания)
        # if self.mcp_manager:
        #     mcp_servers = workflow_config.get('mcp_servers', [])
        #     if mcp_servers:
        #         await self.mcp_manager.start_workflow_servers(workflow_id, mcp_servers)
        
        try:
            logger.info("=== СОЗДАНИЕ ГРАФА ===")
            # Создаем граф из конфигурации
            graph = await self._build_graph_from_config(workflow_config)
            logger.info(f"Граф создан: {graph}")
            
            logger.info("=== СОЗДАНИЕ НАЧАЛЬНОГО СОСТОЯНИЯ ===")
            # Создаем начальное состояние с поддержкой многоитерационного взаимодействия
            initial_state = create_initial_state(
                task_description=task_description,
                workflow_name=workflow_name,
                max_stage_iterations=workflow_config.get("max_stage_iterations", 5)
            )
            logger.info(f"Начальное состояние: {initial_state}")
            
            console.print(f"Начальное состояние: {initial_state}")
            
            # Настраиваем конфигурацию выполнения
            config = {
                "configurable": {
                    "thread_id": thread_id or f"workflow_{workflow_name}_{asyncio.get_event_loop().time()}"
                }
            }
            logger.info(f"Конфигурация выполнения: {config}")
            
            logger.info("=== НАЧАЛО ВЫПОЛНЕНИЯ WORKFLOW ===")
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
            
            logger.info(f"=== WORKFLOW ЗАВЕРШЕН ===")
            logger.info(f"Финальное состояние: {result_state}")
            
            console.print(f"Финальное состояние: {result_state}")
            
            # Возвращаем результат
            if result_state is None:
                error_msg = "Workflow завершен с ошибками: состояние не получено"
                logger.error(error_msg)
                console.print(error_msg)
                return {
                    "success": False,
                    "error": "Workflow state is None",
                    "completed_stages": [],
                    "failed_stages": []
                }
            
            result = result_state.get("result", {})
            
            if result.get("success", False):
                logger.info("Workflow завершен успешно!")
                console.print("Workflow завершен успешно!")
            else:
                logger.warning("Workflow завершен с ошибками")
                console.print("Workflow завершен с ошибками")
                if result_state.get("errors"):
                    for error in result_state["errors"]:
                        logger.error(f"Ошибка: {error}")
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
        finally:
            # Останавливаем MCP серверы после завершения workflow
            if self.mcp_manager:
                try:
                    await self.mcp_manager.stop_workflow_servers(workflow_id)
                except Exception as e:
                    console.print(f"Ошибка остановки MCP серверов: {e}", style="yellow")
    
    async def _build_graph_from_config(self, workflow_config: Dict[str, Any]) -> Any:
        """Построение LangGraph из конфигурации workflow."""
        
        workflow_name = workflow_config.get("name", "unknown")
        
        # Проверяем кэш
        if workflow_name in self._compiled_graphs:
            return self._compiled_graphs[workflow_name]
        
        # Создаем новый граф
        graph = StateGraph(WorkflowState)
        
        # Добавляем явный EndNode
        end_node = EndNode()
        graph.add_node("workflow_end", end_node)
        
        # Обрабатываем stages из конфигурации
        stages = workflow_config.get("stages", [])
        previous_stage = None
        first_stage = None
        last_stage = None
        
        for i, stage_config in enumerate(stages):
            stage_name = stage_config.get("name", f"stage_{i}")
            
            # Проверяем, является ли stage подграфом
            if stage_config.get("type") == "subgraph":
                await self._add_subgraph_to_graph(graph, stage_config, stage_name)
            else:
                # Обычный stage с агентами
                await self._add_stage_to_graph(graph, stage_config, stage_name)
            
            # Запоминаем первый и последний stage
            if first_stage is None:
                first_stage = stage_name
            last_stage = stage_name
            
            # Добавляем связь с предыдущим stage (кроме первого)
            if previous_stage is not None:
                graph.add_edge(previous_stage, stage_name)
            
            previous_stage = stage_name
        
        # Добавляем обязательную связь от START к первому узлу
        if first_stage:
            graph.add_edge(START, first_stage)
            # Связываем последний stage с нашим EndNode
            graph.add_edge(last_stage, "workflow_end")
            # Связываем EndNode с END
            graph.add_edge("workflow_end", END)
            console.print(f"Создан граф: START -> {first_stage} -> ... -> {last_stage} -> workflow_end -> END")
        else:
            # Если нет stages, связываем START с EndNode
            graph.add_edge(START, "workflow_end")
            graph.add_edge("workflow_end", END)
            console.print("Создан граф: START -> workflow_end -> END")
        
        # Компилируем граф без checkpointer для упрощения
        compiled_graph = graph.compile()
        
        # Кэшируем
        self._compiled_graphs[workflow_name] = compiled_graph
        
        return compiled_graph
    
    async def _add_stage_to_graph(self, 
                                graph: StateGraph, 
                                stage_config: Dict[str, Any], 
                                stage_name: str):
        """Добавление обычного stage в граф."""
        
        # Получаем агента для stage (новый формат) или роли (старый формат)
        agent = stage_config.get("agent")
        roles = stage_config.get("roles", [])
        
        if agent:
            # Новый формат с agent
            agent_name = agent
        elif roles:
            # Старый формат с roles
            agent_name = roles[0] if isinstance(roles[0], str) else roles[0].get("name")
        else:
            raise ValueError(f"Stage {stage_name}: не указан агент или роли")
        
        # Создаем узел агента
        agent_node = AgentNode(
            name=stage_name,
            agent_name=agent_name,
            stage_config=stage_config,
            agent_manager=self.agent_manager,
            mcp_manager=self.mcp_manager
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
        """Выполнение workflow с поддержкой human-in-the-loop и многоитерационного взаимодействия."""
        
        from core.logging import get_logger
        logger = get_logger("workflow.engine")
        
        logger.info("=== НАЧАЛО ВЫПОЛНЕНИЯ С HUMAN LOOP ===")
        
        current_state = initial_state
        max_iterations = 50  # Защита от бесконечных циклов
        iteration = 0
        
        try:
            while iteration < max_iterations:
                iteration += 1
                logger.info(f"=== ИТЕРАЦИЯ WORKFLOW {iteration} ===")
                
                # Выполняем один шаг workflow
                step_completed = False
                async for state_update in graph.astream(current_state, config):
                    logger.debug(f"State update: {state_update}")
                    
                    # Обновляем состояние
                    for node_name, node_state in state_update.items():
                        if node_state is not None:
                            current_state = node_state
                            logger.info(f"Узел {node_name} выполнен")
                        
                        # Обновляем прогресс
                        progress.update(task_id, description=f"Выполняется: {node_name}")
                        
                        # Проверяем завершение workflow
                        if current_state and current_state.get("finished", False):
                            logger.info("Workflow завершен")
                            progress.update(task_id, description="Завершено")
                            return current_state
                        
                        # Проверяем, нужен ли пользовательский ввод
                        if current_state and current_state.get("human_input_required", False):
                            logger.info("Требуется взаимодействие с пользователем")
                            
                            # Обрабатываем многоитерационное взаимодействие
                            current_state = await self._handle_human_input_with_iterations(
                                current_state, progress, task_id
                            )
                            
                            # Если пользователь отменил выполнение
                            if current_state is None:
                                logger.info("Выполнение отменено пользователем")
                                return create_initial_state("Отменено", "cancelled")
                            
                            step_completed = True
                            break
                    
                    if step_completed:
                        break
                
                # Если не было обновлений состояния, выходим из цикла
                if not step_completed:
                    logger.info("Нет обновлений состояния, завершаем выполнение")
                    break
            
            # Если достигли лимита итераций
            if iteration >= max_iterations:
                logger.warning(f"Достигнут лимит итераций workflow: {max_iterations}")
                current_state["finished"] = True
                current_state["result"] = {
                    "success": False,
                    "error": f"Превышен лимит итераций ({max_iterations})",
                    "completed_stages": current_state.get("context", {}).get("completed_stages", []),
                    "failed_stages": current_state.get("context", {}).get("failed_stages", [])
                }
            
            return current_state
            
        except Exception as e:
            logger.error(f"Ошибка в _execute_with_human_loop: {str(e)}")
            console.print(f"Ошибка в _execute_with_human_loop: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            traceback.print_exc()
            raise
    
    async def _handle_human_input_with_iterations(self, 
                                                state: WorkflowState,
                                                progress: Progress,
                                                task_id) -> Optional[WorkflowState]:
        """Обработка пользовательского ввода с поддержкой многоитерационного взаимодействия."""
        
        from core.logging import get_logger
        logger = get_logger("workflow.engine")
        
        logger.info("=== ОБРАБОТКА ПОЛЬЗОВАТЕЛЬСКОГО ВВОДА ===")
        
        # Получаем промпт для пользователя
        user_prompt = state.get("human_input_prompt", "Требуется ваш ввод")
        
        # Показываем контекст итерации если есть
        if state.get("stage_iteration", 0) > 0:
            iteration_info = f" (итерация {state['stage_iteration']})"
            progress.update(task_id, description=f"Ожидание ответа пользователя{iteration_info}")
        else:
            progress.update(task_id, description="Ожидание ответа пользователя")
        
        # Показываем историю stage если есть
        if state.get("stage_conversation"):
            console.print("\n=== ИСТОРИЯ ВЗАИМОДЕЙСТВИЯ ===")
            for msg in state["stage_conversation"][-3:]:  # Показываем последние 3 сообщения
                role_label = {
                    "llm": "🤖 LLM",
                    "user": "👤 Вы", 
                    "system": "⚙️ Система"
                }.get(msg["role"], msg["role"].upper())
                
                console.print(f"{role_label}: {msg['content'][:200]}{'...' if len(msg['content']) > 200 else ''}")
            console.print("=" * 30)
        
        # Запрашиваем ввод пользователя
        console.print(f"\n[bold yellow]Вопрос:[/bold yellow] {user_prompt}")
        console.print("[dim]Введите ваш ответ (или 'quit' для выхода):[/dim]")
        
        try:
            user_input = input("> ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'отмена']:
                logger.info("Пользователь отменил выполнение")
                return None
            
            if not user_input:
                console.print("[red]Пустой ввод, попробуйте еще раз[/red]")
                return await self._handle_human_input_with_iterations(state, progress, task_id)
            
            logger.info(f"Получен ответ пользователя: {user_input}")
            
            # Обрабатываем ответ пользователя
            updated_state = await self._process_user_response_in_stage(state, user_input)
            
            return updated_state
            
        except KeyboardInterrupt:
            logger.info("Выполнение прервано пользователем (Ctrl+C)")
            return None
        except Exception as e:
            logger.error(f"Ошибка обработки пользовательского ввода: {str(e)}")
            console.print(f"[red]Ошибка: {str(e)}[/red]")
            return state
    
    async def _process_user_response_in_stage(self, 
                                            state: WorkflowState, 
                                            user_response: str) -> WorkflowState:
        """Обработка ответа пользователя в контексте текущего stage."""
        
        from core.logging import get_logger
        from .state import process_user_confirmation, add_stage_message
        
        logger = get_logger("workflow.engine")
        
        logger.info("=== ОБРАБОТКА ОТВЕТА ПОЛЬЗОВАТЕЛЯ В STAGE ===")
        logger.info(f"Ответ: {user_response}")
        
        # Обновляем состояние с ответом пользователя
        updated_state = process_user_confirmation(state, user_response)
        
        # Добавляем ответ в историю stage
        updated_state = add_stage_message(updated_state, "user", user_response)
        
        # Если stage ожидает продолжения, нужно найти соответствующий AgentNode
        # и вызвать его метод process_user_response
        current_stage = updated_state.get("context", {}).get("current_stage", "")
        
        if current_stage:
            # Ищем AgentNode для текущего stage
            # Это упрощенная реализация - в реальности нужно более сложная логика
            logger.info(f"Обработка ответа для stage: {current_stage}")
            
            # Пока просто помечаем, что ответ обработан
            # В полной реализации здесь должен быть вызов AgentNode.process_user_response
            
        return updated_state
    
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
