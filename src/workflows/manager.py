import os
import yaml
from typing import List, Dict, Optional
from pathlib import Path

from .engine import WorkflowEngine
from .stage_manager import StageManager, StageCommandProcessor
from .subgraphs import get_registry


class WorkflowManager:
    def __init__(self, workflows_dir: str, workflow_engine: Optional[WorkflowEngine] = None, settings=None):
        self.workflows_dir = Path(workflows_dir).expanduser()
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        self.workflow_engine = workflow_engine
        self.subgraph_registry = get_registry()
        
        # Инициализация менеджера этапов
        if settings:
            self.stage_manager = StageManager(settings)
            self.stage_command_processor = StageCommandProcessor(self.stage_manager)
        else:
            self.stage_manager = None
            self.stage_command_processor = None
    
    def list_workflows(self) -> List[Dict]:
        """Список всех workflow"""
        workflows = []
        for yaml_file in self.workflows_dir.glob("*.yaml"):
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    workflows.append({
                        'name': config.get('name', yaml_file.stem),
                        'description': config.get('description', ''),
                        'file': str(yaml_file),
                        'stages': len(config.get('stages', [])),
                        'has_subgraphs': any(stage.get('type') == 'subgraph' 
                                           for stage in config.get('stages', []))
                    })
            except Exception:
                continue
        return workflows
    
    def create_workflow(self, name: str, description: str, config: Dict) -> bool:
        """Создать новый workflow"""
        file_path = self.workflows_dir / f"{name}.yaml"
        if file_path.exists():
            return False
        
        workflow_config = {
            'name': name,
            'description': description,
            **config
        }
        
        # Валидируем конфигурацию
        if not self._validate_workflow_config(workflow_config):
            return False
        
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(workflow_config, f, default_flow_style=False, allow_unicode=True)
        return True
    
    def delete_workflow(self, name: str) -> bool:
        """Удалить workflow"""
        file_path = self.workflows_dir / f"{name}.yaml"
        if file_path.exists():
            file_path.unlink()
            return True
        return False
    
    def get_workflow(self, name: str) -> Optional[Dict]:
        """Получить конфигурацию workflow"""
        file_path = self.workflows_dir / f"{name}.yaml"
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        return None
    
    def select_workflow_by_description(self, user_input: str, llm_provider) -> Optional[str]:
        """Выбор workflow через LLM по описанию пользователя"""
        workflows = self.list_workflows()
        if not workflows:
            return None
        
        workflow_list = "\n".join([f"{i+1}. {w['name']}: {w['description']}" 
                                  for i, w in enumerate(workflows)])
        
        prompt = f"""Пользователь хочет: "{user_input}"

Доступные workflow:
{workflow_list}

Выбери наиболее подходящий workflow и верни только его название (name). Если ничего не подходит, верни "none".
"""
        
        try:
            response = llm_provider.generate(prompt, max_tokens=50)
            selected_name = response.strip().lower()
            
            # Найти workflow по имени
            for workflow in workflows:
                if workflow['name'].lower() == selected_name:
                    return workflow['name']
            return None
        except Exception:
            return None
    
    async def execute_workflow(self, 
                             workflow_name: str, 
                             task_description: str,
                             thread_id: Optional[str] = None) -> Dict:
        """Выполнение workflow через LangGraph engine"""
        
        if self.workflow_engine is None:
            return {
                "success": False,
                "error": "Workflow engine не инициализирован",
                "completed_stages": [],
                "failed_stages": []
            }
        
        # Получаем конфигурацию workflow
        workflow_config = self.get_workflow(workflow_name)
        
        if workflow_config is None:
            return {
                "success": False,
                "error": f"Workflow не найден: {workflow_name}",
                "completed_stages": [],
                "failed_stages": []
            }
        
        # Валидируем конфигурацию
        if not self._validate_workflow_config(workflow_config):
            return {
                "success": False,
                "error": f"Неверная конфигурация workflow: {workflow_name}",
                "completed_stages": [],
                "failed_stages": []
            }
        
        # Выполняем workflow
        try:
            result = await self.workflow_engine.execute_workflow(
                workflow_config=workflow_config,
                task_description=task_description,
                thread_id=thread_id
            )
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Ошибка выполнения workflow: {str(e)}",
                "completed_stages": [],
                "failed_stages": []
            }
    
    def _validate_workflow_config(self, config: Dict) -> bool:
        """Валидация конфигурации workflow"""
        
        # Проверяем обязательные поля
        required_fields = ["name", "description"]
        for field in required_fields:
            if field not in config:
                return False
        
        # Проверяем stages
        stages = config.get("stages", [])
        if not stages:
            return False
        
        for stage in stages:
            if not isinstance(stage, dict):
                return False
            
            if "name" not in stage:
                return False
            
            # Проверяем тип stage
            stage_type = stage.get("type", "agent")
            
            if stage_type == "subgraph":
                # Проверяем существование подграфа
                subgraph_name = stage.get("subgraph")
                if not subgraph_name:
                    return False
                
                if self.subgraph_registry.get_subgraph(subgraph_name) is None:
                    return False
            
            elif stage_type == "agent":
                # Проверяем наличие ролей
                roles = stage.get("roles", [])
                if not roles:
                    return False
        
        return True
    
    def get_workflow_dependencies(self, workflow_name: str) -> Dict[str, List[str]]:
        """Получение зависимостей workflow"""
        
        workflow_config = self.get_workflow(workflow_name)
        if workflow_config is None:
            return {"subgraphs": [], "roles": []}
        
        subgraphs = []
        roles = set()
        
        for stage in workflow_config.get("stages", []):
            if stage.get("type") == "subgraph":
                subgraph_name = stage.get("subgraph")
                if subgraph_name:
                    subgraphs.append(subgraph_name)
            
            # Собираем роли
            stage_roles = stage.get("roles", [])
            for role in stage_roles:
                if isinstance(role, str):
                    roles.add(role)
                elif isinstance(role, dict):
                    roles.add(role.get("name", ""))
        
        return {
            "subgraphs": subgraphs,
            "roles": list(roles)
        }
    
    def create_workflow_from_template(self, 
                                    name: str,
                                    template_name: str,
                                    description: str,
                                    parameters: Dict[str, str]) -> bool:
        """Создание workflow из шаблона"""
        
        # Предопределенные шаблоны
        templates = {
            "simple_development": {
                "stages": [
                    {
                        "name": "analyze_requirements",
                        "roles": ["developer"],
                        "description": "Анализ требований и планирование"
                    },
                    {
                        "name": "implement_solution",
                        "roles": ["developer"],
                        "description": "Реализация решения"
                    },
                    {
                        "name": "test_solution",
                        "roles": ["tester"],
                        "description": "Тестирование решения"
                    }
                ]
            },
            "full_development": {
                "stages": [
                    {
                        "name": "code_analysis",
                        "type": "subgraph",
                        "subgraph": "code_analysis",
                        "description": "Анализ существующего кода"
                    },
                    {
                        "name": "implement_feature",
                        "roles": ["developer"],
                        "description": "Реализация новой функциональности"
                    },
                    {
                        "name": "testing",
                        "type": "subgraph",
                        "subgraph": "testing",
                        "description": "Комплексное тестирование"
                    },
                    {
                        "name": "security_review",
                        "type": "subgraph",
                        "subgraph": "security_review",
                        "description": "Проверка безопасности"
                    }
                ]
            },
            "bug_fix": {
                "stages": [
                    {
                        "name": "analyze_bug",
                        "roles": ["developer"],
                        "description": "Анализ и воспроизведение бага"
                    },
                    {
                        "name": "implement_fix",
                        "roles": ["developer"],
                        "description": "Реализация исправления"
                    },
                    {
                        "name": "verify_fix",
                        "roles": ["tester"],
                        "description": "Проверка исправления"
                    }
                ]
            }
        }
        
        if template_name not in templates:
            return False
        
        template_config = templates[template_name].copy()
        
        # Применяем параметры шаблона
        for key, value in parameters.items():
            # Простая замена параметров в описаниях
            for stage in template_config.get("stages", []):
                if "description" in stage:
                    stage["description"] = stage["description"].replace(f"{{{key}}}", value)
        
        return self.create_workflow(name, description, template_config)
    
    def get_available_templates(self) -> List[Dict[str, str]]:
        """Получение списка доступных шаблонов"""
        
        return [
            {
                "name": "simple_development",
                "description": "Простой workflow разработки: анализ -> реализация -> тестирование"
            },
            {
                "name": "full_development", 
                "description": "Полный workflow разработки с подграфами: анализ кода -> реализация -> тестирование -> безопасность"
            },
            {
                "name": "bug_fix",
                "description": "Workflow исправления багов: анализ -> исправление -> проверка"
            }
        ]
    
    # Методы управления этапами
    
    def list_workflow_stages(self, workflow_name: str):
        """Получить список этапов workflow"""
        if not self.stage_manager:
            raise RuntimeError("Менеджер этапов не инициализирован")
        return self.stage_manager.list_stages(workflow_name)
    
    def get_workflow_stage(self, workflow_name: str, stage_name: str):
        """Получить этап по имени"""
        if not self.stage_manager:
            raise RuntimeError("Менеджер этапов не инициализирован")
        return self.stage_manager.get_stage(workflow_name, stage_name)
    
    def create_workflow_stage(self, workflow_name: str, stage):
        """Создать новый этап"""
        if not self.stage_manager:
            raise RuntimeError("Менеджер этапов не инициализирован")
        return self.stage_manager.create_stage(workflow_name, stage)
    
    def update_workflow_stage(self, workflow_name: str, stage_name: str, updates):
        """Обновить этап"""
        if not self.stage_manager:
            raise RuntimeError("Менеджер этапов не инициализирован")
        return self.stage_manager.update_stage(workflow_name, stage_name, updates)
    
    def delete_workflow_stage(self, workflow_name: str, stage_name: str):
        """Удалить этап"""
        if not self.stage_manager:
            raise RuntimeError("Менеджер этапов не инициализирован")
        return self.stage_manager.delete_stage(workflow_name, stage_name)
    
    def enable_workflow_stage(self, workflow_name: str, stage_name: str):
        """Включить этап"""
        if not self.stage_manager:
            raise RuntimeError("Менеджер этапов не инициализирован")
        return self.stage_manager.enable_stage(workflow_name, stage_name)
    
    def disable_workflow_stage(self, workflow_name: str, stage_name: str):
        """Отключить этап"""
        if not self.stage_manager:
            raise RuntimeError("Менеджер этапов не инициализирован")
        return self.stage_manager.disable_stage(workflow_name, stage_name)
    
    def process_stage_command(self, command: str, workflow_name: str, confirm_callback=None):
        """Обработать команду управления этапами"""
        if not self.stage_command_processor:
            raise RuntimeError("Процессор команд этапов не инициализирован")
        return self.stage_command_processor.process_command(command, workflow_name, confirm_callback)
