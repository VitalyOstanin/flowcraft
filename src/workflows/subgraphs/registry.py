"""
Реестр подграфов для управления и переиспользования.
"""

import os
import yaml
from typing import Dict, List, Optional, Type, Any
from pathlib import Path

from .base import BaseSubgraph, CompositeSubgraph


class SubgraphRegistry:
    """Реестр для управления подграфами."""
    
    def __init__(self, registry_dir: Optional[str] = None):
        self.registry_dir = Path(registry_dir or "~/.flowcraft/subgraphs").expanduser()
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        
        self._subgraphs: Dict[str, BaseSubgraph] = {}
        self._subgraph_classes: Dict[str, Type[BaseSubgraph]] = {}
        self._load_registry()
    
    def register_subgraph_class(self, name: str, subgraph_class: Type[BaseSubgraph]):
        """Регистрация класса подграфа."""
        self._subgraph_classes[name] = subgraph_class
    
    def register_subgraph(self, subgraph: BaseSubgraph):
        """Регистрация экземпляра подграфа."""
        self._subgraphs[subgraph.name] = subgraph
        self._save_subgraph_config(subgraph)
    
    def get_subgraph(self, name: str) -> Optional[BaseSubgraph]:
        """Получение подграфа по имени."""
        return self._subgraphs.get(name)
    
    def list_subgraphs(self) -> List[str]:
        """Список доступных подграфов."""
        return list(self._subgraphs.keys())
    
    def create_subgraph(self, 
                       name: str, 
                       subgraph_type: str, 
                       config: Dict[str, Any]) -> BaseSubgraph:
        """Создание подграфа из конфигурации."""
        
        if subgraph_type not in self._subgraph_classes:
            raise ValueError(f"Неизвестный тип подграфа: {subgraph_type}")
        
        subgraph_class = self._subgraph_classes[subgraph_type]
        subgraph = subgraph_class(name, config.get("description", ""))
        
        # Применяем дополнительную конфигурацию
        if hasattr(subgraph, "configure"):
            subgraph.configure(config)
        
        self.register_subgraph(subgraph)
        
        return subgraph
    
    def create_composite_subgraph(self, 
                                 name: str, 
                                 subgraph_names: List[str],
                                 description: str = "") -> CompositeSubgraph:
        """Создание композитного подграфа."""
        
        composite = CompositeSubgraph(name, description)
        
        for subgraph_name in subgraph_names:
            subgraph = self.get_subgraph(subgraph_name)
            if subgraph is None:
                raise ValueError(f"Подграф не найден: {subgraph_name}")
            
            composite.add_subgraph(subgraph)
        
        self.register_subgraph(composite)
        
        return composite
    
    def remove_subgraph(self, name: str) -> bool:
        """Удаление подграфа."""
        
        if name in self._subgraphs:
            del self._subgraphs[name]
            
            # Удаляем файл конфигурации
            config_file = self.registry_dir / f"{name}.yaml"
            if config_file.exists():
                config_file.unlink()
            
            return True
        
        return False
    
    def search_subgraphs(self, 
                        input_requirements: Optional[List[str]] = None,
                        output_keys: Optional[List[str]] = None,
                        description_keywords: Optional[List[str]] = None) -> List[BaseSubgraph]:
        """Поиск подграфов по критериям."""
        
        results = []
        
        for subgraph in self._subgraphs.values():
            match = True
            
            # Проверка входных требований
            if input_requirements:
                subgraph_inputs = subgraph.get_input_requirements()
                if not all(req in subgraph_inputs for req in input_requirements):
                    match = False
            
            # Проверка выходных ключей
            if output_keys:
                subgraph_outputs = subgraph.get_output_keys()
                if not any(key in subgraph_outputs for key in output_keys):
                    match = False
            
            # Проверка ключевых слов в описании
            if description_keywords:
                description_lower = subgraph.description.lower()
                if not any(keyword.lower() in description_lower for keyword in description_keywords):
                    match = False
            
            if match:
                results.append(subgraph)
        
        return results
    
    def get_subgraph_dependencies(self, name: str) -> List[str]:
        """Получение зависимостей подграфа."""
        
        subgraph = self.get_subgraph(name)
        if subgraph is None:
            return []
        
        if isinstance(subgraph, CompositeSubgraph):
            return [sg.name for sg in subgraph.subgraphs]
        
        return []
    
    def validate_subgraph_chain(self, subgraph_names: List[str]) -> bool:
        """Валидация цепочки подграфов."""
        
        for i in range(len(subgraph_names) - 1):
            current_name = subgraph_names[i]
            next_name = subgraph_names[i + 1]
            
            current_subgraph = self.get_subgraph(current_name)
            next_subgraph = self.get_subgraph(next_name)
            
            if current_subgraph is None or next_subgraph is None:
                return False
            
            # Проверяем совместимость выходов и входов
            current_outputs = current_subgraph.get_output_keys()
            next_inputs = next_subgraph.get_input_requirements()
            
            if next_inputs and not any(inp in current_outputs for inp in next_inputs):
                return False
        
        return True
    
    def _load_registry(self):
        """Загрузка реестра из файлов."""
        
        for config_file in self.registry_dir.glob("*.yaml"):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                
                subgraph_type = config.get("type", "base")
                
                if subgraph_type in self._subgraph_classes:
                    subgraph = self.create_subgraph(
                        config["name"], 
                        subgraph_type, 
                        config
                    )
                
            except Exception as e:
                print(f"Ошибка загрузки подграфа из {config_file}: {e}")
    
    def _save_subgraph_config(self, subgraph: BaseSubgraph):
        """Сохранение конфигурации подграфа."""
        
        config = subgraph.get_config()
        config["type"] = subgraph.__class__.__name__.lower().replace("subgraph", "")
        
        config_file = self.registry_dir / f"{subgraph.name}.yaml"
        
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    
    def export_registry(self, export_path: str):
        """Экспорт всего реестра в файл."""
        
        registry_data = {
            "subgraphs": {},
            "metadata": {
                "version": "1.0",
                "total_subgraphs": len(self._subgraphs)
            }
        }
        
        for name, subgraph in self._subgraphs.items():
            registry_data["subgraphs"][name] = subgraph.get_config()
        
        with open(export_path, 'w', encoding='utf-8') as f:
            yaml.dump(registry_data, f, default_flow_style=False, allow_unicode=True)
    
    def import_registry(self, import_path: str):
        """Импорт реестра из файла."""
        
        with open(import_path, 'r', encoding='utf-8') as f:
            registry_data = yaml.safe_load(f)
        
        for name, config in registry_data.get("subgraphs", {}).items():
            subgraph_type = config.get("type", "base")
            
            if subgraph_type in self._subgraph_classes:
                try:
                    self.create_subgraph(name, subgraph_type, config)
                except Exception as e:
                    print(f"Ошибка импорта подграфа {name}: {e}")


# Глобальный экземпляр реестра
_global_registry = None


def get_registry() -> SubgraphRegistry:
    """Получение глобального экземпляра реестра."""
    
    global _global_registry
    
    if _global_registry is None:
        _global_registry = SubgraphRegistry()
    
    return _global_registry
