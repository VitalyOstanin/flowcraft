"""
Загрузчик workflow конфигураций
"""

import yaml
from pathlib import Path
from typing import Dict, List, Optional
from rich.console import Console

console = Console()

class WorkflowLoader:
    """Загрузчик workflow из YAML файлов"""
    
    def __init__(self, workflows_dir: str):
        self.workflows_dir = Path(workflows_dir).expanduser()
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
    
    def load_workflow(self, workflow_name: str) -> Optional[Dict]:
        """Загрузить конфигурацию workflow"""
        workflow_file = self.workflows_dir / f"{workflow_name}.yaml"
        
        if not workflow_file.exists():
            console.print(f"Workflow файл не найден: {workflow_file}", style="red")
            return None
        
        try:
            with open(workflow_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # Валидация базовых полей
            if not self._validate_config(config):
                return None
            
            return config
            
        except Exception as e:
            console.print(f"Ошибка загрузки workflow {workflow_name}: {e}", style="red")
            return None
    
    def list_workflows(self) -> List[str]:
        """Получить список доступных workflow"""
        workflows = []
        for file_path in self.workflows_dir.glob("*.yaml"):
            workflow_name = file_path.stem
            workflows.append(workflow_name)
        return sorted(workflows)
    
    def create_workflow_template(self, workflow_name: str, description: str = "") -> bool:
        """Создать шаблон workflow"""
        workflow_file = self.workflows_dir / f"{workflow_name}.yaml"
        
        if workflow_file.exists():
            console.print(f"Workflow {workflow_name} уже существует", style="yellow")
            return False
        
        template = {
            "name": workflow_name,
            "description": description or f"Workflow для {workflow_name}",
            "mcp_servers": [],
            "roles": [
                {
                    "name": "developer",
                    "prompt": "Ты разработчик. Отвечай на русском.",
                    "expensive_model": False
                }
            ],
            "tools": ["file_crud", "shell", "search"],
            "stages": [
                {
                    "name": "analyze_task",
                    "roles": ["developer"],
                    "skippable": True,
                    "description": "Анализ задачи"
                },
                {
                    "name": "implement",
                    "roles": ["developer"],
                    "skippable": False,
                    "description": "Реализация"
                }
            ]
        }
        
        try:
            with open(workflow_file, 'w', encoding='utf-8') as f:
                yaml.dump(template, f, default_flow_style=False, allow_unicode=True)
            
            console.print(f"Создан шаблон workflow: {workflow_file}", style="green")
            return True
            
        except Exception as e:
            console.print(f"Ошибка создания шаблона: {e}", style="red")
            return False
    
    def _validate_config(self, config: Dict) -> bool:
        """Валидация конфигурации workflow"""
        required_fields = ["name", "stages"]
        
        for field in required_fields:
            if field not in config:
                console.print(f"Отсутствует обязательное поле: {field}", style="red")
                return False
        
        # Валидация stages
        stages = config.get("stages", [])
        if not isinstance(stages, list) or len(stages) == 0:
            console.print("Stages должен быть непустым списком", style="red")
            return False
        
        for i, stage in enumerate(stages):
            if not isinstance(stage, dict):
                console.print(f"Stage {i} должен быть объектом", style="red")
                return False
            
            if "name" not in stage:
                console.print(f"Stage {i} должен содержать поле 'name'", style="red")
                return False
            
            if "agent" not in stage:
                console.print(f"Stage {i} должен содержать поле 'agent'", style="red")
                return False
        
        return True
    
    def get_workflow_info(self, workflow_name: str) -> Optional[Dict]:
        """Получить краткую информацию о workflow"""
        config = self.load_workflow(workflow_name)
        if not config:
            return None
        
        return {
            "name": config.get("name", workflow_name),
            "description": config.get("description", ""),
            "stages_count": len(config.get("stages", [])),
            "agents": list(set(
                stage.get("agent") for stage in config.get("stages", [])
                if stage.get("agent")
            )),
            "mcp_servers": config.get("mcp_servers", [])
        }
