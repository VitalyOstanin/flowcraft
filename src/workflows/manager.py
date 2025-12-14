import os
import yaml
from typing import List, Dict, Optional
from pathlib import Path

class WorkflowManager:
    def __init__(self, workflows_dir: str):
        self.workflows_dir = Path(workflows_dir).expanduser()
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
    
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
                        'file': str(yaml_file)
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
