"""
Базовая система workflow FlowCraft
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import yaml
from pathlib import Path

class WorkflowStatus(Enum):
    """Статусы workflow"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class WorkflowState:
    """Состояние workflow"""
    task_id: str
    task_description: str
    current_step: str = ""
    current_role: str = ""
    status: WorkflowStatus = WorkflowStatus.PENDING
    results: Dict[str, Any] = field(default_factory=dict)
    skipped_stages: List[str] = field(default_factory=list)
    human_feedback: Optional[str] = None
    progress: float = 0.0

@dataclass
class WorkflowStep:
    """Шаг workflow"""
    name: str
    roles: List[str]
    skippable: bool = True
    description: str = ""
    timeout: int = 30  # Таймаут в секундах, по умолчанию 30

class BaseWorkflow:
    """Базовый класс workflow"""
    
    def __init__(self, config: Dict, agent_manager, tools):
        self.config = config
        self.agent_manager = agent_manager
        self.tools = tools
        self.state = None
        self.steps = self._load_steps()
        self.current_step_index = 0
    
    def _load_steps(self) -> List[WorkflowStep]:
        """Загрузить шаги из конфигурации"""
        steps = []
        for step_config in self.config.get("stages", []):
            step = WorkflowStep(
                name=step_config["name"],
                roles=step_config["roles"],
                skippable=step_config.get("skippable", True),
                description=step_config.get("description", "")
            )
            steps.append(step)
        return steps
    
    def start(self, task_id: str, task_description: str) -> WorkflowState:
        """Запустить workflow"""
        self.state = WorkflowState(
            task_id=task_id,
            task_description=task_description,
            status=WorkflowStatus.RUNNING
        )
        
        if self.steps:
            self.state.current_step = self.steps[0].name
            self.state.current_role = self.steps[0].roles[0] if self.steps[0].roles else ""
        
        return self.state
    
    def next_step(self) -> bool:
        """Перейти к следующему шагу"""
        if self.current_step_index < len(self.steps) - 1:
            self.current_step_index += 1
            current_step = self.steps[self.current_step_index]
            
            self.state.current_step = current_step.name
            self.state.current_role = current_step.roles[0] if current_step.roles else ""
            self.state.progress = (self.current_step_index + 1) / len(self.steps)
            
            return True
        else:
            self.state.status = WorkflowStatus.COMPLETED
            self.state.progress = 1.0
            return False
    
    def skip_step(self, step_name: str) -> bool:
        """Пропустить шаг"""
        for i, step in enumerate(self.steps):
            if step.name == step_name and step.skippable:
                if step_name not in self.state.skipped_stages:
                    self.state.skipped_stages.append(step_name)
                
                # Если это текущий шаг, перейти к следующему
                if i == self.current_step_index:
                    return self.next_step()
                return True
        return False
    
    def pause(self):
        """Приостановить workflow"""
        self.state.status = WorkflowStatus.PAUSED
    
    def resume(self):
        """Возобновить workflow"""
        self.state.status = WorkflowStatus.RUNNING
    
    def get_current_step(self) -> Optional[WorkflowStep]:
        """Получить текущий шаг"""
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None
    
    def get_enabled_agents(self) -> List:
        """Получить включенных агентов для workflow"""
        workflow_name = self.config.get("name", "")
        return self.agent_manager.get_enabled_agents_for_workflow(workflow_name)
    
    def execute_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Выполнить шаг workflow (базовая реализация)"""
        # Получить агентов для ролей этого шага
        enabled_agents = self.get_enabled_agents()
        step_agents = [
            agent for agent in enabled_agents 
            if agent.role.lower().replace(" ", "_") in [role.lower() for role in step.roles]
        ]
        
        result = {
            "step_name": step.name,
            "agents_used": [agent.name for agent in step_agents],
            "status": "completed",
            "output": f"Выполнен шаг: {step.name}"
        }
        
        # Сохранить результат
        self.state.results[step.name] = result
        
        return result
