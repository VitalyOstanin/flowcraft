"""Интеграция LLM провайдеров с системой агентов."""

from typing import List, Optional, Dict, Any, Iterator
from core.settings import SettingsManager
from .router import LLMRouter


class LLMIntegration:
    """Интеграция LLM провайдеров с FlowCraft."""
    
    def __init__(self, settings_manager: SettingsManager):
        self.settings_manager = settings_manager
        self._router: Optional[LLMRouter] = None
    
    def _get_router(self) -> LLMRouter:
        """Получить LLM роутер."""
        if not self._router:
            settings = self.settings_manager.settings
            self._router = LLMRouter(
                cheap_model=settings.llm.cheap_model,
                expensive_model=settings.llm.expensive_model,
                expensive_stages=settings.llm.expensive_stages
            )
        return self._router
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        stage: Optional[str] = None,
        force_expensive: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Выполнить chat completion с автоматическим выбором модели.
        
        Args:
            messages: Список сообщений в формате OpenAI
            stage: Текущий этап workflow
            force_expensive: Принудительно использовать дорогую модель
            **kwargs: Дополнительные параметры
            
        Returns:
            Ответ в формате OpenAI API
        """
        router = self._get_router()
        return router.chat_completion(
            messages=messages,
            stage=stage,
            force_expensive=force_expensive,
            **kwargs
        )
    
    def stream_completion(
        self,
        messages: List[Dict[str, str]],
        stage: Optional[str] = None,
        force_expensive: bool = False,
        **kwargs
    ) -> Iterator[Dict[str, Any]]:
        """
        Выполнить streaming completion с автоматическим выбором модели.
        
        Args:
            messages: Список сообщений в формате OpenAI
            stage: Текущий этап workflow
            force_expensive: Принудительно использовать дорогую модель
            **kwargs: Дополнительные параметры
            
        Yields:
            Чанки ответа в формате OpenAI API
        """
        router = self._get_router()
        yield from router.stream_completion(
            messages=messages,
            stage=stage,
            force_expensive=force_expensive,
            **kwargs
        )
    
    def get_current_model_info(
        self,
        messages: List[Dict[str, str]],
        stage: Optional[str] = None,
        force_expensive: bool = False
    ) -> Dict[str, str]:
        """
        Получить информацию о модели, которая будет использована.
        
        Args:
            messages: Список сообщений
            stage: Текущий этап workflow
            force_expensive: Принудительно использовать дорогую модель
            
        Returns:
            Информация о модели
        """
        router = self._get_router()
        provider_name = router.get_current_provider_name(
            messages=messages,
            stage=stage,
            force_expensive=force_expensive
        )
        
        settings = self.settings_manager.settings
        if provider_name == settings.llm.cheap_model:
            model_type = "cheap"
        else:
            model_type = "expensive"
        
        return {
            "provider": provider_name,
            "type": model_type,
            "stage": stage or "unknown"
        }
