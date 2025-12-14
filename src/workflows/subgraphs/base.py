"""
Базовый класс для подграфов workflow.
"""

from typing import Dict, Any, List, Optional, Set
from abc import ABC, abstractmethod
from langgraph.graph import StateGraph, END, START

from workflows.state import WorkflowState
from workflows.nodes import BaseNode, create_node


class BaseSubgraph(ABC):
    """Базовый класс для переиспользуемых подграфов."""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self._nodes: Dict[str, BaseNode] = {}
        self._edges: List[tuple] = []
        self._conditional_edges: List[Dict[str, Any]] = []
        self._compiled_graph: Optional[Any] = None
    
    @abstractmethod
    def define_nodes(self) -> Dict[str, BaseNode]:
        """Определение узлов подграфа."""
        pass
    
    @abstractmethod
    def define_edges(self) -> List[tuple]:
        """Определение связей между узлами."""
        pass
    
    def define_conditional_edges(self) -> List[Dict[str, Any]]:
        """Определение условных связей (опционально)."""
        return []
    
    def get_input_requirements(self) -> Set[str]:
        """Требования к входным данным."""
        return set()
    
    def get_output_keys(self) -> Set[str]:
        """Ключи выходных данных."""
        return set()
    
    def validate_inputs(self, state: WorkflowState) -> bool:
        """Валидация входных данных."""
        requirements = self.get_input_requirements()
        context = state["context"]
        
        for req in requirements:
            if req not in context.stage_outputs and req not in context.user_inputs:
                return False
        
        return True
    
    def build_graph(self) -> Any:
        """Построение LangGraph из определения подграфа."""
        
        if self._compiled_graph is not None:
            return self._compiled_graph
        
        # Создаем граф
        graph = StateGraph(WorkflowState)
        
        # Добавляем узлы
        self._nodes = self.define_nodes()
        for node_name, node in self._nodes.items():
            graph.add_node(node_name, node)
        
        # Добавляем обычные связи
        self._edges = self.define_edges()
        for source, target in self._edges:
            graph.add_edge(source, target)
        
        # Добавляем условные связи
        self._conditional_edges = self.define_conditional_edges()
        for edge_config in self._conditional_edges:
            graph.add_conditional_edges(
                edge_config["source"],
                edge_config["condition"],
                edge_config["mapping"]
            )
        
        # Компилируем граф
        self._compiled_graph = graph.compile()
        
        return self._compiled_graph
    
    async def execute(self, state: WorkflowState) -> WorkflowState:
        """Выполнение подграфа."""
        
        if not self.validate_inputs(state):
            raise ValueError(f"Подграф {self.name}: не выполнены требования к входным данным")
        
        graph = self.build_graph()
        
        # Выполняем граф
        result = await graph.ainvoke(state)
        
        return result
    
    def get_config(self) -> Dict[str, Any]:
        """Получение конфигурации подграфа для сериализации."""
        
        return {
            "name": self.name,
            "description": self.description,
            "input_requirements": list(self.get_input_requirements()),
            "output_keys": list(self.get_output_keys()),
            "nodes": list(self._nodes.keys()) if self._nodes else [],
            "edges": self._edges,
            "conditional_edges": self._conditional_edges
        }


class CompositeSubgraph(BaseSubgraph):
    """Композитный подграф из других подграфов."""
    
    def __init__(self, name: str, description: str = ""):
        super().__init__(name, description)
        self.subgraphs: List[BaseSubgraph] = []
        self.subgraph_order: List[str] = []
    
    def add_subgraph(self, subgraph: BaseSubgraph, position: Optional[int] = None):
        """Добавление подграфа в композицию."""
        
        if position is None:
            self.subgraphs.append(subgraph)
            self.subgraph_order.append(subgraph.name)
        else:
            self.subgraphs.insert(position, subgraph)
            self.subgraph_order.insert(position, subgraph.name)
    
    def define_nodes(self) -> Dict[str, BaseNode]:
        """Объединение узлов всех подграфов."""
        
        nodes = {}
        
        for subgraph in self.subgraphs:
            subgraph_nodes = subgraph.define_nodes()
            
            # Добавляем префикс для избежания конфликтов имен
            for node_name, node in subgraph_nodes.items():
                prefixed_name = f"{subgraph.name}_{node_name}"
                nodes[prefixed_name] = node
        
        return nodes
    
    def define_edges(self) -> List[tuple]:
        """Объединение связей всех подграфов."""
        
        edges = []
        
        # Внутренние связи подграфов
        for subgraph in self.subgraphs:
            subgraph_edges = subgraph.define_edges()
            
            for source, target in subgraph_edges:
                prefixed_source = f"{subgraph.name}_{source}"
                prefixed_target = f"{subgraph.name}_{target}"
                edges.append((prefixed_source, prefixed_target))
        
        # Связи между подграфами
        for i in range(len(self.subgraphs) - 1):
            current_subgraph = self.subgraphs[i]
            next_subgraph = self.subgraphs[i + 1]
            
            # Находим конечные узлы текущего подграфа
            current_end_nodes = self._find_end_nodes(current_subgraph)
            next_start_nodes = self._find_start_nodes(next_subgraph)
            
            # Соединяем конечные узлы с начальными
            for end_node in current_end_nodes:
                for start_node in next_start_nodes:
                    prefixed_end = f"{current_subgraph.name}_{end_node}"
                    prefixed_start = f"{next_subgraph.name}_{start_node}"
                    edges.append((prefixed_end, prefixed_start))
        
        return edges
    
    def _find_end_nodes(self, subgraph: BaseSubgraph) -> List[str]:
        """Поиск конечных узлов подграфа."""
        
        edges = subgraph.define_edges()
        all_sources = {source for source, _ in edges}
        all_targets = {target for _, target in edges}
        
        # Узлы, которые являются источниками, но не целями
        end_nodes = all_sources - all_targets
        
        return list(end_nodes) if end_nodes else ["end"]
    
    def _find_start_nodes(self, subgraph: BaseSubgraph) -> List[str]:
        """Поиск начальных узлов подграфа."""
        
        edges = subgraph.define_edges()
        all_sources = {source for source, _ in edges}
        all_targets = {target for _, target in edges}
        
        # Узлы, которые являются целями, но не источниками
        start_nodes = all_targets - all_sources
        
        return list(start_nodes) if start_nodes else ["start"]
    
    def get_input_requirements(self) -> Set[str]:
        """Объединение требований всех подграфов."""
        
        requirements = set()
        
        for subgraph in self.subgraphs:
            requirements.update(subgraph.get_input_requirements())
        
        return requirements
    
    def get_output_keys(self) -> Set[str]:
        """Объединение выходных ключей всех подграфов."""
        
        output_keys = set()
        
        for subgraph in self.subgraphs:
            output_keys.update(subgraph.get_output_keys())
        
        return output_keys
