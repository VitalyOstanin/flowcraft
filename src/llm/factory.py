"""Фабрика для создания LLM провайдеров."""

from typing import Dict, Type, Any
from .base import BaseLLMProvider
from .qwen_code import QwenCodeProvider


class LLMProviderFactory:
    """Фабрика для создания LLM провайдеров."""
    
    _providers: Dict[str, Type[BaseLLMProvider]] = {
        "qwen-code": QwenCodeProvider,
    }
    
    @classmethod
    def create_provider(cls, provider_name: str, **kwargs) -> BaseLLMProvider:
        """Создать провайдер по имени."""
        if provider_name not in cls._providers:
            raise ValueError(f"Неизвестный провайдер: {provider_name}. Доступные: {list(cls._providers.keys())}")
        
        provider_class = cls._providers[provider_name]
        return provider_class(**kwargs)
    
    @classmethod
    def register_provider(cls, name: str, provider_class: Type[BaseLLMProvider]):
        """Зарегистрировать новый провайдер."""
        cls._providers[name] = provider_class
    
    @classmethod
    def get_available_providers(cls) -> list[str]:
        """Получить список доступных провайдеров."""
        return list(cls._providers.keys())
