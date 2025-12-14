"""Интеграционный тест для полной LLM системы."""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Добавить src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.settings import SettingsManager, Settings, LLMConfig
from llm.integration import LLMIntegration


class TestLLMIntegrationFull:
    """Интеграционные тесты для LLM системы."""
    
    def setup_method(self):
        """Настройка для каждого теста."""
        # Создаем мок настроек
        self.mock_settings = Settings(
            language="ru",
            llm=LLMConfig(
                cheap_model="qwen-code",
                expensive_model="kiro-cli",
                expensive_stages=["security_review", "architecture_design"]
            ),
            mcp_servers=[],
            trust_rules={},
            workflows_dir="~/.flowcraft/workflows",
            agents={}
        )
        
        self.mock_settings_manager = MagicMock(spec=SettingsManager)
        self.mock_settings_manager.settings = self.mock_settings
    
    @patch('src.llm.factory.LLMProviderFactory.create_provider')
    def test_integration_cheap_model_selection(self, mock_create_provider):
        """Тест выбора дешевой модели через интеграцию."""
        # Настраиваем моки провайдеров
        mock_cheap = MagicMock()
        mock_expensive = MagicMock()
        mock_cheap.name = "qwen-code"
        mock_expensive.name = "kiro-cli"
        mock_cheap.chat_completion.return_value = {
            "choices": [{"message": {"content": "Ответ от дешевой модели"}}]
        }
        mock_create_provider.side_effect = [mock_cheap, mock_expensive]
        
        # Создаем интеграцию
        integration = LLMIntegration(self.mock_settings_manager)
        
        # Простое сообщение должно использовать дешевую модель
        messages = [{"role": "user", "content": "Привет"}]
        response = integration.chat_completion(messages)
        
        assert response["choices"][0]["message"]["content"] == "Ответ от дешевой модели"
        mock_cheap.chat_completion.assert_called_once()
        mock_expensive.chat_completion.assert_not_called()
    
    @patch('src.llm.factory.LLMProviderFactory.create_provider')
    def test_integration_expensive_model_selection(self, mock_create_provider):
        """Тест выбора дорогой модели через интеграцию."""
        # Настраиваем моки провайдеров
        mock_cheap = MagicMock()
        mock_expensive = MagicMock()
        mock_cheap.name = "qwen-code"
        mock_expensive.name = "kiro-cli"
        mock_expensive.chat_completion.return_value = {
            "choices": [{"message": {"content": "Ответ от дорогой модели"}}]
        }
        mock_create_provider.side_effect = [mock_cheap, mock_expensive]
        
        # Создаем интеграцию
        integration = LLMIntegration(self.mock_settings_manager)
        
        # Этап security_review должен использовать дорогую модель
        messages = [{"role": "user", "content": "Проверь безопасность"}]
        response = integration.chat_completion(messages, stage="security_review")
        
        assert response["choices"][0]["message"]["content"] == "Ответ от дорогой модели"
        mock_expensive.chat_completion.assert_called_once()
        mock_cheap.chat_completion.assert_not_called()
    
    @patch('src.llm.factory.LLMProviderFactory.create_provider')
    def test_integration_force_expensive(self, mock_create_provider):
        """Тест принудительного использования дорогой модели."""
        # Настраиваем моки провайдеров
        mock_cheap = MagicMock()
        mock_expensive = MagicMock()
        mock_cheap.name = "qwen-code"
        mock_expensive.name = "kiro-cli"
        mock_expensive.chat_completion.return_value = {
            "choices": [{"message": {"content": "Принудительно дорогая модель"}}]
        }
        mock_create_provider.side_effect = [mock_cheap, mock_expensive]
        
        # Создаем интеграцию
        integration = LLMIntegration(self.mock_settings_manager)
        
        # Простое сообщение с force_expensive=True
        messages = [{"role": "user", "content": "Простой вопрос"}]
        response = integration.chat_completion(messages, force_expensive=True)
        
        assert response["choices"][0]["message"]["content"] == "Принудительно дорогая модель"
        mock_expensive.chat_completion.assert_called_once()
        mock_cheap.chat_completion.assert_not_called()
    
    @patch('src.llm.factory.LLMProviderFactory.create_provider')
    def test_integration_model_info(self, mock_create_provider):
        """Тест получения информации о модели."""
        # Настраиваем моки провайдеров
        mock_cheap = MagicMock()
        mock_expensive = MagicMock()
        mock_cheap.name = "qwen-code"
        mock_expensive.name = "kiro-cli"
        mock_create_provider.side_effect = [mock_cheap, mock_expensive]
        
        # Создаем интеграцию
        integration = LLMIntegration(self.mock_settings_manager)
        
        # Информация для дешевой модели
        messages = [{"role": "user", "content": "Простой вопрос"}]
        info = integration.get_current_model_info(messages)
        
        assert info["provider"] == "qwen-code"
        assert info["type"] == "cheap"
        
        # Информация для дорогой модели
        info = integration.get_current_model_info(messages, stage="security_review")
        
        assert info["provider"] == "kiro-cli"
        assert info["type"] == "expensive"
        assert info["stage"] == "security_review"
    
    @patch('src.llm.factory.LLMProviderFactory.create_provider')
    def test_integration_stream_completion(self, mock_create_provider):
        """Тест потокового completion через интеграцию."""
        # Настраиваем моки провайдеров
        mock_cheap = MagicMock()
        mock_expensive = MagicMock()
        mock_cheap.name = "qwen-code"
        mock_expensive.name = "kiro-cli"
        
        # Мокаем потоковый ответ
        mock_chunks = [
            {"choices": [{"delta": {"content": "Часть "}}]},
            {"choices": [{"delta": {"content": "ответа"}}]}
        ]
        mock_cheap.stream_completion.return_value = iter(mock_chunks)
        mock_create_provider.side_effect = [mock_cheap, mock_expensive]
        
        # Создаем интеграцию
        integration = LLMIntegration(self.mock_settings_manager)
        
        # Тестируем потоковый ответ
        messages = [{"role": "user", "content": "Простой вопрос"}]
        chunks = list(integration.stream_completion(messages))
        
        assert len(chunks) == 2
        assert chunks[0]["choices"][0]["delta"]["content"] == "Часть "
        assert chunks[1]["choices"][0]["delta"]["content"] == "ответа"
        mock_cheap.stream_completion.assert_called_once()
        mock_expensive.stream_completion.assert_not_called()
