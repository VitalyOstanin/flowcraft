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
    system_prompt: str
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
        self.agents_dir = Path(settings_manager.config_path.parent / "agents")
        self.agents_dir.mkdir(exist_ok=True)
        self.load_agents()
    
    def get_agent_file_path(self, agent_name: str) -> Path:
        """Получить путь к файлу агента"""
        return self.agents_dir / f"{agent_name}.yaml"
    
    def save_agent_to_file(self, agent: Agent):
        """Сохранить агента в отдельный файл"""
        agent_data = {
            'name': agent.name,
            'system_prompt': agent.system_prompt,
            'description': agent.description,
            'capabilities': agent.capabilities,
            'llm_model': agent.llm_model,
            'status': agent.status.value,
            'workflow_enabled': list(agent.workflow_enabled)
        }
        
        file_path = self.get_agent_file_path(agent.name)
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(agent_data, f, default_flow_style=False, allow_unicode=True)
    
    def load_agent_from_file(self, agent_name: str) -> Optional[Agent]:
        """Загрузить агента из файла"""
        file_path = self.get_agent_file_path(agent_name)
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            return Agent(
                name=data['name'],
                system_prompt=data['system_prompt'],
                description=data['description'],
                capabilities=data['capabilities'],
                llm_model=data['llm_model'],
                status=AgentStatus(data.get('status', 'enabled')),
                workflow_enabled=set(data.get('workflow_enabled', []))
            )
        except Exception as e:
            print(f"Ошибка загрузки агента {agent_name}: {e}")
            return None
    
    def create_agent(self, name: str, system_prompt: str, description: str, 
                    capabilities: List[str], llm_model: str) -> Agent:
        """Создать нового агента"""
        if name in self.agents:
            raise ValueError(f"Агент {name} уже существует")
        
        agent = Agent(
            name=name,
            system_prompt=system_prompt,
            description=description,
            capabilities=capabilities,
            llm_model=llm_model
        )
        
        self.agents[name] = agent
        self.save_agent_to_file(agent)
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
        
        self.save_agent_to_file(agent)
        return agent
    
    def delete_agent(self, name: str) -> bool:
        """Удалить агента"""
        if name not in self.agents:
            return False
        
        # Удалить из памяти
        del self.agents[name]
        
        # Удалить файл
        file_path = self.get_agent_file_path(name)
        if file_path.exists():
            file_path.unlink()
        
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
        self.save_agent_to_file(self.agents[name])
        return True
    
    def disable_agent_globally(self, name: str) -> bool:
        """Глобально отключить агента"""
        if name not in self.agents:
            return False
        
        self.agents[name].status = AgentStatus.DISABLED
        # Отключить во всех workflow
        self.agents[name].workflow_enabled.clear()
        self.save_agent_to_file(self.agents[name])
        return True
    
    def enable_agent_for_workflow(self, agent_name: str, workflow_name: str) -> bool:
        """Включить агента для конкретного workflow"""
        if agent_name not in self.agents:
            return False
        
        agent = self.agents[agent_name]
        if agent.status == AgentStatus.DISABLED:
            return False  # Нельзя включить в workflow если глобально отключен
        
        agent.workflow_enabled.add(workflow_name)
        self.save_agent_to_file(agent)
        return True
    
    def disable_agent_for_workflow(self, agent_name: str, workflow_name: str) -> bool:
        """Отключить агента для конкретного workflow"""
        if agent_name not in self.agents:
            return False
        
        self.agents[agent_name].workflow_enabled.discard(workflow_name)
        self.save_agent_to_file(self.agents[agent_name])
        return True
    
    async def _create_agent_with_llm(self, user_request: str, llm_router) -> Optional[dict]:
        """Создать агента с помощью LLM"""
        prompt = f"""
Пользователь просит создать агента: "{user_request}"

Создай конфигурацию агента в JSON формате:
{{
    "name": "agent-name",
    "system_prompt": "Системный промпт агента на русском языке",
    "description": "Описание агента",
    "capabilities": ["список", "возможностей"],
    "llm_model": "qwen3-coder-plus или kiro-cli"
}}

Правила:
- Имя агента на английском в формате "специализация-уровень" (например: developer-basic, architect-advanced)
- Системный промпт должен определять личность и стиль работы агента
- Для сложных задач используй kiro-cli, для простых qwen3-coder-plus
- Capabilities должны отражать навыки агента

Верни только JSON без дополнительного текста.
"""
        
        try:
            response = await llm_router.generate_response(prompt, "qwen3-coder-plus")
            
            # Парсинг JSON ответа
            import json
            agent_config = json.loads(response.strip())
            
            return agent_config
            
        except Exception as e:
            print(f"Ошибка создания агента через LLM: {e}")
            return None
    
    def _confirm_agent_action(self, action: str, agent_data: dict) -> bool:
        """Запросить подтверждение пользователя для действия с агентом"""
        print(f"\n🤖 LLM предлагает {action} агента:")
        print("=" * 50)
        
        if action == "создать":
            print(f"Имя: {agent_data.get('name', 'N/A')}")
            print(f"Описание: {agent_data.get('description', 'N/A')}")
            print(f"Модель: {agent_data.get('llm_model', 'N/A')}")
            print(f"Возможности: {', '.join(agent_data.get('capabilities', []))}")
            print(f"Системный промпт: {agent_data.get('system_prompt', 'N/A')[:100]}...")
        
        print("=" * 50)
        
        while True:
            choice = input("Подтвердить действие? (y/n): ").lower().strip()
            if choice in ['y', 'yes', 'да', 'д']:
                return True
            elif choice in ['n', 'no', 'нет', 'н']:
                return False
            else:
                print("Пожалуйста, введите y (да) или n (нет)")
    
    async def create_agent_with_llm_confirmation(self, user_request: str, llm_router) -> Optional[Agent]:
        """Создать агента через LLM с подтверждением пользователя"""
        print(f"🔄 Генерирую конфигурацию агента для запроса: {user_request}")
        
        agent_config = await self._create_agent_with_llm(user_request, llm_router)
        if not agent_config:
            print("❌ Не удалось сгенерировать конфигурацию агента")
            return None
        
        # Запросить подтверждение
        if not self._confirm_agent_action("создать", agent_config):
            print("❌ Создание агента отменено пользователем")
            return None
        
        try:
            # Создать агента
            agent = self.create_agent(
                name=agent_config['name'],
                system_prompt=agent_config['system_prompt'],
                description=agent_config['description'],
                capabilities=agent_config['capabilities'],
                llm_model=agent_config['llm_model']
            )
            
            print(f"✅ Агент '{agent.name}' создан успешно")
            return agent
            
        except Exception as e:
            print(f"❌ Ошибка создания агента: {e}")
            return None
    
    def get_enabled_agents_for_workflow(self, workflow_name: str) -> List[Agent]:
        """Получить список включенных агентов для workflow"""
        return [
            agent for agent in self.agents.values()
            if agent.status == AgentStatus.ENABLED and 
               workflow_name in agent.workflow_enabled
        ]
    
    def load_agents(self):
        """Загрузить всех агентов из файлов"""
        if not self.agents_dir.exists():
            return
        
        for agent_file in self.agents_dir.glob("*.yaml"):
            agent_name = agent_file.stem
            agent = self.load_agent_from_file(agent_name)
            if agent:
                self.agents[agent_name] = agent
    
    def save_agents(self):
        """Сохранить всех агентов в файлы"""
        for agent in self.agents.values():
            self.save_agent_to_file(agent)
