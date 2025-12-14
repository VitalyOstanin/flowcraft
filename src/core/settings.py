"""
Система настроек FlowCraft
"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from dataclasses import dataclass

class LLMConfig(BaseModel):
    """Конфигурация LLM"""
    cheap_model: str = "qwen3-coder-plus"
    expensive_model: str = "kiro-cli"
    expensive_stages: List[str] = Field(default_factory=lambda: [
        "security_review", 
        "architecture_design", 
        "complex_debugging"
    ])
    qwen_oauth_path: Optional[str] = None  # Путь к OAuth credentials для qwen-code

class MCPServerConfig(BaseModel):
    """Конфигурация MCP сервера"""
    name: str
    command: str
    args: List[str] = Field(default_factory=list)

class Settings(BaseModel):
    """Основные настройки FlowCraft"""
    language: str = "ru"
    llm: LLMConfig = Field(default_factory=LLMConfig)
    mcp_servers: List[MCPServerConfig] = Field(default_factory=list)
    trust_rules: Dict[str, str] = Field(default_factory=dict)
    workflows_dir: str = "~/.flowcraft/workflows"
    agents: Dict[str, Any] = Field(default_factory=dict)

class SettingsManager:
    """Менеджер настроек"""
    
    def __init__(self, config_path: str = "~/.flowcraft/settings.yaml"):
        self.config_path = Path(config_path).expanduser()
        # Создать директорию ~/.flowcraft/ если не существует
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings: Optional[Settings] = None
        self.load_settings()
    
    def load_settings(self) -> Settings:
        """Загрузить настройки из файла"""
        if self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            self.settings = Settings(**data)
        else:
            self.settings = Settings()
            self.save_settings()
        
        # Создать директорию для workflow если не существует
        workflows_dir = Path(self.settings.workflows_dir).expanduser()
        workflows_dir.mkdir(parents=True, exist_ok=True)
        
        return self.settings
    
    def save_settings(self):
        """Сохранить настройки в файл"""
        if self.settings:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(
                    self.settings.model_dump(), 
                    f, 
                    default_flow_style=False, 
                    allow_unicode=True
                )
    
    def get_workflows_dir(self) -> Path:
        """Получить путь к директории workflow"""
        return Path(self.settings.workflows_dir).expanduser()
    
    def add_mcp_server(self, name: str, command: str, args: List[str] = None):
        """Добавить MCP сервер"""
        server = MCPServerConfig(
            name=name,
            command=command,
            args=args or []
        )
        self.settings.mcp_servers.append(server)
        self.save_settings()
    
    def remove_mcp_server(self, name: str) -> bool:
        """Удалить MCP сервер"""
        original_count = len(self.settings.mcp_servers)
        self.settings.mcp_servers = [
            s for s in self.settings.mcp_servers 
            if s.name != name
        ]
        
        if len(self.settings.mcp_servers) < original_count:
            self.save_settings()
            return True
        return False
    
    def add_trust_rule(self, pattern: str, level: str):
        """Добавить правило доверия"""
        self.settings.trust_rules[pattern] = level
        self.save_settings()
    
    def get_trust_level(self, pattern: str) -> Optional[str]:
        """Получить уровень доверия для паттерна"""
        return self.settings.trust_rules.get(pattern)
