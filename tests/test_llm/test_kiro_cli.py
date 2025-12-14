"""Тесты для kiro-cli провайдера."""

import pytest
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Добавить src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from llm.kiro_cli import KiroCliProvider


class TestKiroCliProvider:
    """Тесты для KiroCliProvider."""
    
    @patch('subprocess.run')
    def test_check_availability_success(self, mock_run):
        """Тест успешной проверки доступности kiro-cli."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        
        # Не должно выбросить исключение
        provider = KiroCliProvider()
        assert provider.name == "kiro-cli"
    
    @patch('subprocess.run')
    def test_check_availability_not_found(self, mock_run):
        """Тест недоступности kiro-cli."""
        mock_run.side_effect = FileNotFoundError()
        
        with pytest.raises(RuntimeError, match="kiro-cli не установлен"):
            KiroCliProvider()
    
    @patch('subprocess.run')
    def test_check_availability_error(self, mock_run):
        """Тест ошибки kiro-cli."""
        mock_run.return_value = MagicMock(returncode=1, stderr="Error")
        
        with pytest.raises(RuntimeError, match="kiro-cli недоступен"):
            KiroCliProvider()
    
    @patch('subprocess.run')
    def test_chat_completion_success(self, mock_run):
        """Тест успешного chat completion."""
        # Мокаем проверку доступности
        mock_run.side_effect = [
            MagicMock(returncode=0, stderr=""),  # Проверка версии
            MagicMock(returncode=0, stdout="Тестовый ответ", stderr="")  # Chat completion
        ]
        
        provider = KiroCliProvider()
        messages = [{"role": "user", "content": "Привет"}]
        
        response = provider.chat_completion(messages)
        
        assert "choices" in response
        assert response["choices"][0]["message"]["content"] == "Тестовый ответ"
        assert response["choices"][0]["finish_reason"] == "stop"
        assert "usage" in response
    
    @patch('subprocess.run')
    def test_chat_completion_error(self, mock_run):
        """Тест ошибки chat completion."""
        # Мокаем проверку доступности и ошибку выполнения
        mock_run.side_effect = [
            MagicMock(returncode=0, stderr=""),  # Проверка версии
            MagicMock(returncode=1, stderr="Ошибка выполнения")  # Chat completion
        ]
        
        provider = KiroCliProvider()
        messages = [{"role": "user", "content": "Привет"}]
        
        with pytest.raises(RuntimeError, match="Ошибка kiro-cli"):
            provider.chat_completion(messages)
    
    @patch('subprocess.run')
    def test_stream_completion(self, mock_run):
        """Тест потокового completion."""
        # Мокаем проверку доступности
        mock_run.side_effect = [
            MagicMock(returncode=0, stderr=""),  # Проверка версии
            MagicMock(returncode=0, stdout="Привет мир", stderr="")  # Chat completion
        ]
        
        provider = KiroCliProvider()
        messages = [{"role": "user", "content": "Привет"}]
        
        chunks = list(provider.stream_completion(messages))
        
        assert len(chunks) == 2  # "Привет" и "мир"
        assert chunks[0]["choices"][0]["delta"]["content"] == "Привет "
        assert chunks[0]["choices"][0]["finish_reason"] is None
        assert chunks[1]["choices"][0]["delta"]["content"] == "мир"
        assert chunks[1]["choices"][0]["finish_reason"] == "stop"
    
    def test_format_messages(self):
        """Тест форматирования сообщений."""
        provider = KiroCliProvider.__new__(KiroCliProvider)  # Создаем без __init__
        
        messages = [
            {"role": "system", "content": "Ты помощник"},
            {"role": "user", "content": "Привет"},
            {"role": "assistant", "content": "Привет!"},
            {"role": "user", "content": "Как дела?"}
        ]
        
        prompt = provider._format_messages(messages)
        
        expected = "System: Ты помощник\n\nUser: Привет\n\nAssistant: Привет!\n\nUser: Как дела?"
        assert prompt == expected
