"""Интеграция LLM провайдеров с системой агентов."""

from typing import List, Optional
from ..core.settings import SettingsManager
from .factory import LLMProviderFactory
from .base import BaseLLMProvider, LLMMessage, LLMResponse


class LLMIntegration:
    """Интеграция LLM провайдеров с FlowCraft."""
    
    def __init__(self, settings_manager: SettingsManager):
        self.settings_manager = settings_manager
        self._cheap_provider: Optional[BaseLLMProvider] = None
        self._expensive_provider: Optional[BaseLLMProvider] = None
    
    def _get_cheap_provider(self) -> BaseLLMProvider:
        """Получить дешевый провайдер."""
        if not self._cheap_provider:
            settings = self.settings_manager.settings
            model_name = settings.llm.cheap_model
            
            # Определить провайдер по имени модели
            if "qwen3-coder" in model_name or "qwen-coder" in model_name:
                provider_name = "qwen-code"
                kwargs = {
                    "model_name": model_name,
                    "oauth_path": settings.llm.qwen_oauth_path
                }
            else:
                raise ValueError(f"Неподдерживаемая модель: {model_name}")
            
            self._cheap_provider = LLMProviderFactory.create_provider(provider_name, **kwargs)
        
        return self._cheap_provider
    
    def _get_expensive_provider(self) -> BaseLLMProvider:
        """Получить дорогой провайдер."""
        if not self._expensive_provider:
            settings = self.settings_manager.settings
            model_name = settings.llm.expensive_model
            
            # Пока поддерживаем только kiro-cli как заглушку
            if model_name == "kiro-cli":
                # Используем qwen-code как fallback
                provider_name = "qwen-code"
                kwargs = {
                    "model_name": "qwen3-coder-plus",
                    "oauth_path": settings.llm.qwen_oauth_path
                }
            else:
                raise ValueError(f"Неподдерживаемая дорогая модель: {model_name}")
            
            self._expensive_provider = LLMProviderFactory.create_provider(provider_name, **kwargs)
        
        return self._expensive_provider
    
    def should_use_expensive_model(self, stage_name: str) -> bool:
        """Определить, нужно ли использовать дорогую модель для этапа."""
        settings = self.settings_manager.settings
        return stage_name in settings.llm.expensive_stages
    
    async def chat_completion(
        self,
        messages: List[LLMMessage],
        stage_name: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> LLMResponse:
        """Выполнить chat completion с автоматическим выбором модели."""
        if stage_name and self.should_use_expensive_model(stage_name):
            provider = self._get_expensive_provider()
        else:
            provider = self._get_cheap_provider()
        
        return await provider.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
    
    async def stream_completion(
        self,
        messages: List[LLMMessage],
        stage_name: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ):
        """Выполнить streaming completion с автоматическим выбором модели."""
        if stage_name and self.should_use_expensive_model(stage_name):
            provider = self._get_expensive_provider()
        else:
            provider = self._get_cheap_provider()
        
        async for chunk in provider.stream_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        ):
            yield chunk
    
    def get_current_model_info(self, stage_name: Optional[str] = None) -> dict:
        """Получить информацию о текущей модели."""
        if stage_name and self.should_use_expensive_model(stage_name):
            provider = self._get_expensive_provider()
            model_type = "expensive"
        else:
            provider = self._get_cheap_provider()
            model_type = "cheap"
        
        return {
            "provider": provider.provider_name,
            "model": provider.model_name,
            "type": model_type
        }
