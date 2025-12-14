"""Тесты для LLM Router."""

import pytest
from unittest.mock import patch, MagicMock
from src.llm.router import LLMRouter


class TestLLMRouter:
    """Тесты для LLMRouter."""
    
    @patch('src.llm.factory.LLMProviderFactory.create_provider')
    def test_init(self, mock_create_provider):
        """Тест инициализации роутера."""
        mock_cheap = MagicMock()
        mock_expensive = MagicMock()
        mock_create_provider.side_effect = [mock_cheap, mock_expensive]
        
        router = LLMRouter(
            cheap_model="qwen-code",
            expensive_model="kiro-cli",
            expensive_stages=["security_review", "architecture_design"]
        )
        
        assert router.cheap_model == "qwen-code"
        assert router.expensive_model == "kiro-cli"
        assert router.expensive_stages == ["security_review", "architecture_design"]
        assert mock_create_provider.call_count == 2
    
    @patch('src.llm.factory.LLMProviderFactory.create_provider')
    def test_select_provider_force_expensive(self, mock_create_provider):
        """Тест принудительного выбора дорогой модели."""
        mock_cheap = MagicMock()
        mock_expensive = MagicMock()
        mock_create_provider.side_effect = [mock_cheap, mock_expensive]
        
        router = LLMRouter("qwen-code", "kiro-cli")
        messages = [{"role": "user", "content": "Простой вопрос"}]
        
        provider = router._select_provider(messages, force_expensive=True)
        assert provider == mock_expensive
    
    @patch('src.llm.factory.LLMProviderFactory.create_provider')
    def test_select_provider_expensive_stage(self, mock_create_provider):
        """Тест выбора дорогой модели для дорогого этапа."""
        mock_cheap = MagicMock()
        mock_expensive = MagicMock()
        mock_create_provider.side_effect = [mock_cheap, mock_expensive]
        
        router = LLMRouter(
            "qwen-code", 
            "kiro-cli",
            expensive_stages=["security_review"]
        )
        messages = [{"role": "user", "content": "Простой вопрос"}]
        
        provider = router._select_provider(messages, stage="security_review")
        assert provider == mock_expensive
    
    @patch('src.llm.factory.LLMProviderFactory.create_provider')
    def test_select_provider_cheap_stage(self, mock_create_provider):
        """Тест выбора дешевой модели для обычного этапа."""
        mock_cheap = MagicMock()
        mock_expensive = MagicMock()
        mock_create_provider.side_effect = [mock_cheap, mock_expensive]
        
        router = LLMRouter(
            "qwen-code", 
            "kiro-cli",
            expensive_stages=["security_review"]
        )
        messages = [{"role": "user", "content": "Простой вопрос"}]
        
        provider = router._select_provider(messages, stage="simple_task")
        assert provider == mock_cheap
    
    def test_is_complex_task_keywords(self):
        """Тест определения сложной задачи по ключевым словам."""
        router = LLMRouter.__new__(LLMRouter)  # Создаем без __init__
        
        # Сложная задача с ключевыми словами
        messages = [{"role": "user", "content": "Спроектируй архитектуру системы"}]
        assert router._is_complex_task(messages) is True
        
        # Простая задача
        messages = [{"role": "user", "content": "Привет, как дела?"}]
        assert router._is_complex_task(messages) is False
    
    def test_is_complex_task_length(self):
        """Тест определения сложной задачи по длине."""
        router = LLMRouter.__new__(LLMRouter)  # Создаем без __init__
        
        # Длинная задача
        long_content = "Очень длинный текст " * 100  # > 1000 символов
        messages = [{"role": "user", "content": long_content}]
        assert router._is_complex_task(messages) is True
    
    def test_is_complex_task_message_count(self):
        """Тест определения сложной задачи по количеству сообщений."""
        router = LLMRouter.__new__(LLMRouter)  # Создаем без __init__
        
        # Много сообщений
        messages = [{"role": "user", "content": f"Сообщение {i}"} for i in range(10)]
        assert router._is_complex_task(messages) is True
    
    @patch('src.llm.factory.LLMProviderFactory.create_provider')
    def test_chat_completion(self, mock_create_provider):
        """Тест chat completion через роутер."""
        mock_cheap = MagicMock()
        mock_expensive = MagicMock()
        mock_cheap.chat_completion.return_value = {"test": "cheap_response"}
        mock_expensive.chat_completion.return_value = {"test": "expensive_response"}
        mock_create_provider.side_effect = [mock_cheap, mock_expensive]
        
        router = LLMRouter("qwen-code", "kiro-cli")
        messages = [{"role": "user", "content": "Простой вопрос"}]
        
        # Дешевая модель
        response = router.chat_completion(messages)
        assert response == {"test": "cheap_response"}
        mock_cheap.chat_completion.assert_called_once_with(messages)
        
        # Дорогая модель
        response = router.chat_completion(messages, force_expensive=True)
        assert response == {"test": "expensive_response"}
        mock_expensive.chat_completion.assert_called_once_with(messages)
    
    @patch('src.llm.factory.LLMProviderFactory.create_provider')
    def test_get_current_provider_name(self, mock_create_provider):
        """Тест получения имени текущего провайдера."""
        mock_cheap = MagicMock()
        mock_expensive = MagicMock()
        mock_cheap.name = "qwen-code"
        mock_expensive.name = "kiro-cli"
        mock_create_provider.side_effect = [mock_cheap, mock_expensive]
        
        router = LLMRouter("qwen-code", "kiro-cli")
        messages = [{"role": "user", "content": "Простой вопрос"}]
        
        # Дешевая модель
        name = router.get_current_provider_name(messages)
        assert name == "qwen-code"
        
        # Дорогая модель
        name = router.get_current_provider_name(messages, force_expensive=True)
        assert name == "kiro-cli"
