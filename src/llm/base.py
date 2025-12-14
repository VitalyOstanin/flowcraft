"""Базовый класс для LLM провайдеров."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, AsyncGenerator
from pydantic import BaseModel


class LLMMessage(BaseModel):
    """Сообщение для LLM."""
    role: str  # system, user, assistant
    content: str


class LLMResponse(BaseModel):
    """Ответ от LLM."""
    content: str
    usage: Optional[Dict[str, int]] = None


class BaseLLMProvider(ABC):
    """Базовый класс для LLM провайдеров."""
    
    def __init__(self, model_name: str, **kwargs):
        self.model_name = model_name
        self.config = kwargs
    
    @abstractmethod
    async def chat_completion(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> LLMResponse:
        """Выполнить chat completion запрос."""
        pass
    
    @abstractmethod
    async def stream_completion(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Выполнить streaming chat completion запрос."""
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Имя провайдера."""
        pass
