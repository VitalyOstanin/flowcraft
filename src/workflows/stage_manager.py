"""
Менеджер этапов workflow с CRUD операциями и поддержкой команд от LLM
"""

import os
import yaml
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path

from core.settings import Settings


@dataclass
class WorkflowStage:
    """Этап workflow"""
    name: str
    description: str
    roles: List[str]
    skippable: bool = False
    enabled: bool = True
    dependencies: List[str] = None
    timeout_minutes: Optional[int] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class StageManager:
    """Менеджер этапов workflow"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.workflows_dir = Path(settings.workflows_dir).expanduser()
        
    def _get_workflow_path(self, workflow_name: str) -> Path:
        """Получить путь к файлу workflow"""
        return self.workflows_dir / f"{workflow_name}.yaml"
    
    def _load_workflow(self, workflow_name: str) -> Dict[str, Any]:
        """Загрузить workflow из файла"""
        workflow_path = self._get_workflow_path(workflow_name)
        if not workflow_path.exists():
            raise FileNotFoundError(f"Workflow '{workflow_name}' не найден")
        
        with open(workflow_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def _save_workflow(self, workflow_name: str, workflow_data: Dict[str, Any]):
        """Сохранить workflow в файл"""
        workflow_path = self._get_workflow_path(workflow_name)
        workflow_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(workflow_path, 'w', encoding='utf-8') as f:
            yaml.dump(workflow_data, f, default_flow_style=False, 
                     allow_unicode=True, sort_keys=False)
    
    def list_stages(self, workflow_name: str) -> List[WorkflowStage]:
        """Получить список этапов workflow"""
        workflow_data = self._load_workflow(workflow_name)
        stages = []
        
        for stage_data in workflow_data.get('stages', []):
            stage = WorkflowStage(
                name=stage_data['name'],
                description=stage_data['description'],
                roles=stage_data['roles'],
                skippable=stage_data.get('skippable', False),
                enabled=stage_data.get('enabled', True),
                dependencies=stage_data.get('dependencies', []),
                timeout_minutes=stage_data.get('timeout_minutes')
            )
            stages.append(stage)
        
        return stages
    
    def get_stage(self, workflow_name: str, stage_name: str) -> Optional[WorkflowStage]:
        """Получить этап по имени"""
        stages = self.list_stages(workflow_name)
        for stage in stages:
            if stage.name == stage_name:
                return stage
        return None
    
    def create_stage(self, workflow_name: str, stage: WorkflowStage) -> bool:
        """Создать новый этап"""
        workflow_data = self._load_workflow(workflow_name)
        
        # Проверить, что этап не существует
        existing_names = [s['name'] for s in workflow_data.get('stages', [])]
        if stage.name in existing_names:
            raise ValueError(f"Этап '{stage.name}' уже существует")
        
        # Добавить этап
        if 'stages' not in workflow_data:
            workflow_data['stages'] = []
        
        stage_dict = asdict(stage)
        workflow_data['stages'].append(stage_dict)
        
        self._save_workflow(workflow_name, workflow_data)
        return True
    
    def update_stage(self, workflow_name: str, stage_name: str, updates: Dict[str, Any]) -> bool:
        """Обновить этап"""
        workflow_data = self._load_workflow(workflow_name)
        
        stages = workflow_data.get('stages', [])
        for i, stage_data in enumerate(stages):
            if stage_data['name'] == stage_name:
                # Обновить поля
                for key, value in updates.items():
                    if key in stage_data or key in ['enabled', 'dependencies', 'timeout_minutes']:
                        stage_data[key] = value
                
                self._save_workflow(workflow_name, workflow_data)
                return True
        
        raise ValueError(f"Этап '{stage_name}' не найден")
    
    def delete_stage(self, workflow_name: str, stage_name: str) -> bool:
        """Удалить этап"""
        workflow_data = self._load_workflow(workflow_name)
        
        stages = workflow_data.get('stages', [])
        for i, stage_data in enumerate(stages):
            if stage_data['name'] == stage_name:
                stages.pop(i)
                self._save_workflow(workflow_name, workflow_data)
                return True
        
        raise ValueError(f"Этап '{stage_name}' не найден")
    
    def enable_stage(self, workflow_name: str, stage_name: str) -> bool:
        """Включить этап"""
        return self.update_stage(workflow_name, stage_name, {'enabled': True})
    
    def disable_stage(self, workflow_name: str, stage_name: str) -> bool:
        """Отключить этап"""
        return self.update_stage(workflow_name, stage_name, {'enabled': False})
    
    def get_enabled_stages(self, workflow_name: str) -> List[WorkflowStage]:
        """Получить только включенные этапы"""
        stages = self.list_stages(workflow_name)
        return [stage for stage in stages if stage.enabled]


class StageCommandProcessor:
    """Обработчик команд для управления этапами"""
    
    def __init__(self, stage_manager: StageManager):
        self.stage_manager = stage_manager
    
    def process_command(self, command: str, workflow_name: str, 
                       confirm_callback=None) -> Dict[str, Any]:
        """
        Обработать команду управления этапами
        
        Args:
            command: Команда (например: "create_stage name='test' description='Test stage' roles=['developer']")
            workflow_name: Имя workflow
            confirm_callback: Функция подтверждения для команд от LLM
        """
        try:
            # Парсинг команды
            parts = command.strip().split(' ', 1)
            action = parts[0]
            
            # Запрос подтверждения если есть callback
            if confirm_callback:
                if not confirm_callback(f"Выполнить команду: {command}"):
                    return {"success": False, "message": "Команда отменена пользователем"}
            
            if action == "list_stages":
                stages = self.stage_manager.list_stages(workflow_name)
                return {
                    "success": True, 
                    "data": [asdict(stage) for stage in stages],
                    "message": f"Найдено {len(stages)} этапов"
                }
            
            elif action == "create_stage":
                params = self._parse_params(parts[1] if len(parts) > 1 else "")
                stage = WorkflowStage(
                    name=params.get('name', ''),
                    description=params.get('description', ''),
                    roles=params.get('roles', []),
                    skippable=params.get('skippable', False),
                    enabled=params.get('enabled', True),
                    dependencies=params.get('dependencies', []),
                    timeout_minutes=params.get('timeout_minutes')
                )
                
                self.stage_manager.create_stage(workflow_name, stage)
                return {"success": True, "message": f"Этап '{stage.name}' создан"}
            
            elif action == "update_stage":
                params = self._parse_params(parts[1] if len(parts) > 1 else "")
                stage_name = params.pop('name', '')
                
                self.stage_manager.update_stage(workflow_name, stage_name, params)
                return {"success": True, "message": f"Этап '{stage_name}' обновлен"}
            
            elif action == "delete_stage":
                params = self._parse_params(parts[1] if len(parts) > 1 else "")
                stage_name = params.get('name', '')
                
                self.stage_manager.delete_stage(workflow_name, stage_name)
                return {"success": True, "message": f"Этап '{stage_name}' удален"}
            
            elif action == "enable_stage":
                params = self._parse_params(parts[1] if len(parts) > 1 else "")
                stage_name = params.get('name', '')
                
                self.stage_manager.enable_stage(workflow_name, stage_name)
                return {"success": True, "message": f"Этап '{stage_name}' включен"}
            
            elif action == "disable_stage":
                params = self._parse_params(parts[1] if len(parts) > 1 else "")
                stage_name = params.get('name', '')
                
                self.stage_manager.disable_stage(workflow_name, stage_name)
                return {"success": True, "message": f"Этап '{stage_name}' отключен"}
            
            else:
                return {"success": False, "message": f"Неизвестная команда: {action}"}
                
        except Exception as e:
            return {"success": False, "message": f"Ошибка выполнения команды: {str(e)}"}
    
    def _parse_params(self, params_str: str) -> Dict[str, Any]:
        """Парсинг параметров команды"""
        params = {}
        if not params_str:
            return params
        
        # Простой парсер для параметров вида key='value' key2=['item1', 'item2']
        import re
        
        # Найти все параметры
        pattern = r"(\w+)=(['\"].*?['\"]|\[.*?\]|\w+)"
        matches = re.findall(pattern, params_str)
        
        for key, value in matches:
            # Обработать значение
            if value.startswith('[') and value.endswith(']'):
                # Список
                items = value[1:-1].split(',')
                params[key] = [item.strip().strip("'\"") for item in items if item.strip()]
            elif value.startswith('"') or value.startswith("'"):
                # Строка
                params[key] = value[1:-1]
            elif value.lower() in ['true', 'false']:
                # Булево значение
                params[key] = value.lower() == 'true'
            elif value.isdigit():
                # Число
                params[key] = int(value)
            else:
                # Строка без кавычек
                params[key] = value
        
        return params
