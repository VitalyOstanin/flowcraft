"""
Менеджер агентов FlowCraft
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import yaml
from pathlib import Path

class AgentStatus(Enum):
    """Статусы агентов"""
    ENABLED = "enabled"
    DISABLED = "disabled"

@dataclass
class Agent:
    """Агент FlowCraft"""
    name: str
    role: str
    description: str
    capabilities: List[str]
    llm_model: str
    status: AgentStatus = AgentStatus.ENABLED
    workflow_enabled: Set[str] = field(default_factory=set)

class AgentManager:
    """Менеджер агентов"""
    
    def __init__(self, settings_manager):
        self.settings_manager = settings_manager
        self.agents: Dict[str, Agent] = {}
        self.load_agents()
    
    def create_agent(self, name: str, role: str, description: str, 
                    capabilities: List[str], llm_model: str) -> Agent:
        """Создать нового агента"""
        if name in self.agents:
            raise ValueError(f"Агент {name} уже существует")
        
        agent = Agent(
            name=name,
            role=role, 
            description=description,
            capabilities=capabilities,
            llm_model=llm_model
        )
        
        self.agents[name] = agent
        self.save_agents()
        return agent
    
    def get_agent(self, name: str) -> Optional[Agent]:
        """Получить агента по имени"""
        return self.agents.get(name)
    
    def update_agent(self, name: str, **kwargs) -> Agent:
        """Обновить агента"""
        if name not in self.agents:
            raise ValueError(f"Агент {name} не найден")
        
        agent = self.agents[name]
        for key, value in kwargs.items():
            if hasattr(agent, key):
                if key == 'workflow_enabled' and isinstance(value, list):
                    setattr(agent, key, set(value))
                else:
                    setattr(agent, key, value)
        
        self.save_agents()
        return agent
    
    def delete_agent(self, name: str) -> bool:
        """Удалить агента"""
        if name not in self.agents:
            return False
        
        del self.agents[name]
        self.save_agents()
        return True
    
    def list_agents(self, status: Optional[AgentStatus] = None) -> List[Agent]:
        """Список агентов с фильтрацией по статусу"""
        agents = list(self.agents.values())
        if status:
            agents = [a for a in agents if a.status == status]
        return agents
    
    def enable_agent_globally(self, name: str) -> bool:
        """Глобально включить агента"""
        if name not in self.agents:
            return False
        
        self.agents[name].status = AgentStatus.ENABLED
        self.save_agents()
        return True
    
    def disable_agent_globally(self, name: str) -> bool:
        """Глобально отключить агента"""
        if name not in self.agents:
            return False
        
        self.agents[name].status = AgentStatus.DISABLED
        # Отключить во всех workflow
        self.agents[name].workflow_enabled.clear()
        self.save_agents()
        return True
    
    def enable_agent_for_workflow(self, agent_name: str, workflow_name: str) -> bool:
        """Включить агента для конкретного workflow"""
        if agent_name not in self.agents:
            return False
        
        agent = self.agents[agent_name]
        if agent.status == AgentStatus.DISABLED:
            return False  # Нельзя включить в workflow если глобально отключен
        
        agent.workflow_enabled.add(workflow_name)
        self.save_agents()
        return True
    
    def disable_agent_for_workflow(self, agent_name: str, workflow_name: str) -> bool:
        """Отключить агента для конкретного workflow"""
        if agent_name not in self.agents:
            return False
        
        self.agents[agent_name].workflow_enabled.discard(workflow_name)
        self.save_agents()
        return True
    
    def get_enabled_agents_for_workflow(self, workflow_name: str) -> List[Agent]:
        """Получить список включенных агентов для workflow"""
        return [
            agent for agent in self.agents.values()
            if agent.status == AgentStatus.ENABLED and 
               workflow_name in agent.workflow_enabled
        ]
    
    def load_agents(self):
        """Загрузить агентов из настроек"""
        agents_data = self.settings_manager.settings.agents
        
        for name, data in agents_data.items():
            self.agents[name] = Agent(
                name=name,
                role=data['role'],
                description=data['description'],
                capabilities=data['capabilities'],
                llm_model=data['llm_model'],
                status=AgentStatus(data.get('status', 'enabled')),
                workflow_enabled=set(data.get('workflow_enabled', []))
            )
    
    def save_agents(self):
        """Сохранить агентов в настройки"""
        agents_data = {}
        for name, agent in self.agents.items():
            agents_data[name] = {
                'role': agent.role,
                'description': agent.description,
                'capabilities': agent.capabilities,
                'llm_model': agent.llm_model,
                'status': agent.status.value,
                'workflow_enabled': list(agent.workflow_enabled)
            }
        
        self.settings_manager.settings.agents = agents_data
        self.settings_manager.save_settings()
