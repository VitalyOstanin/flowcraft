"""
LLM Router для автоматического выбора модели на основе сложности задачи.
"""

from typing import List, Dict, Any, Optional, Iterator
from .base import BaseLLMProvider
from .factory import LLMProviderFactory


class LLMRouter:
    """
    Роутер для автоматического выбора LLM модели.
    Выбирает между дешевой и дорогой моделью на основе контекста.
    """
    
    def __init__(
        self,
        cheap_model: str,
        expensive_model: str,
        expensive_stages: Optional[List[str]] = None
    ):
        """
        Инициализация роутера.
        
        Args:
            cheap_model: Имя дешевой модели
            expensive_model: Имя дорогой модели
            expensive_stages: Список этапов, требующих дорогую модель
        """
        self.cheap_model = cheap_model
        self.expensive_model = expensive_model
        self.expensive_stages = expensive_stages or []
        
        # Создаем провайдеры
        self._cheap_provider = LLMProviderFactory.create_provider(cheap_model)
        self._expensive_provider = LLMProviderFactory.create_provider(expensive_model)
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        stage: Optional[str] = None,
        force_expensive: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Выполнение chat completion с автоматическим выбором модели.
        
        Args:
            messages: Список сообщений
            stage: Текущий этап workflow
            force_expensive: Принудительно использовать дорогую модель
            **kwargs: Дополнительные параметры
            
        Returns:
            Ответ от выбранной модели
        """
        provider = self._select_provider(messages, stage, force_expensive)
        return provider.chat_completion(messages, **kwargs)
    
    def stream_completion(
        self,
        messages: List[Dict[str, str]],
        stage: Optional[str] = None,
        force_expensive: bool = False,
        **kwargs
    ) -> Iterator[Dict[str, Any]]:
        """
        Потоковое выполнение chat completion с автоматическим выбором модели.
        
        Args:
            messages: Список сообщений
            stage: Текущий этап workflow
            force_expensive: Принудительно использовать дорогую модель
            **kwargs: Дополнительные параметры
            
        Yields:
            Чанки ответа от выбранной модели
        """
        provider = self._select_provider(messages, stage, force_expensive)
        yield from provider.stream_completion(messages, **kwargs)
    
    def _select_provider(
        self,
        messages: List[Dict[str, str]],
        stage: Optional[str] = None,
        force_expensive: bool = False
    ) -> BaseLLMProvider:
        """
        Выбор провайдера на основе контекста.
        
        Args:
            messages: Список сообщений
            stage: Текущий этап workflow
            force_expensive: Принудительно использовать дорогую модель
            
        Returns:
            Выбранный провайдер
        """
        # Принудительное использование дорогой модели
        if force_expensive:
            return self._expensive_provider
        
        # Проверка этапа workflow
        if stage and stage in self.expensive_stages:
            return self._expensive_provider
        
        # Анализ сложности задачи по содержимому
        if self._is_complex_task(messages):
            return self._expensive_provider
        
        # По умолчанию используем дешевую модель
        return self._cheap_provider
    
    def _is_complex_task(self, messages: List[Dict[str, str]]) -> bool:
        """
        Определение сложности задачи по содержимому сообщений.
        
        Args:
            messages: Список сообщений
            
        Returns:
            True если задача сложная
        """
        # Объединяем все сообщения в один текст
        text = " ".join(msg.get("content", "") for msg in messages).lower()
        
        # Ключевые слова, указывающие на сложные задачи
        complex_keywords = [
            "архитектура", "architecture", "дизайн", "design",
            "безопасность", "security", "уязвимость", "vulnerability",
            "производительность", "performance", "оптимизация", "optimization",
            "рефакторинг", "refactoring", "миграция", "migration",
            "интеграция", "integration", "api", "база данных", "database",
            "алгоритм", "algorithm", "структура данных", "data structure",
            "паттерн", "pattern", "solid", "принципы", "principles",
            "спроектируй", "проектирование", "проект"
        ]
        
        # Проверяем наличие ключевых слов
        for keyword in complex_keywords:
            if keyword in text:
                return True
        
        # Проверяем длину текста (длинные задачи обычно сложнее)
        if len(text) > 1000:
            return True
        
        # Проверяем количество сообщений (длинный диалог = сложная задача)
        if len(messages) > 5:
            return True
        
        return False
    
    def get_current_provider_name(
        self,
        messages: List[Dict[str, str]],
        stage: Optional[str] = None,
        force_expensive: bool = False
    ) -> str:
        """
        Получить имя провайдера, который будет использован.
        
        Args:
            messages: Список сообщений
            stage: Текущий этап workflow
            force_expensive: Принудительно использовать дорогую модель
            
        Returns:
            Имя провайдера
        """
        provider = self._select_provider(messages, stage, force_expensive)
        return provider.name
