"""
Kiro CLI LLM провайдер для FlowCraft.
Интеграция с kiro-cli в неинтерактивном режиме.
"""

import subprocess
import json
import tempfile
import os
from typing import Dict, Any, List, Optional, Iterator
from .base import BaseLLMProvider


class KiroCliProvider(BaseLLMProvider):
    """LLM провайдер для kiro-cli."""
    
    def __init__(self, model_name: str = "kiro-cli", **kwargs):
        """Инициализация провайдера."""
        super().__init__(model_name, **kwargs)
        self.name = "kiro-cli"
        self._check_availability()
    
    @property
    def provider_name(self) -> str:
        """Имя провайдера."""
        return "kiro-cli"
    
    def _check_availability(self) -> None:
        """Проверка доступности kiro-cli."""
        try:
            result = subprocess.run(
                ["kiro-cli", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                raise RuntimeError(f"kiro-cli недоступен: {result.stderr}")
        except FileNotFoundError:
            raise RuntimeError("kiro-cli не установлен")
        except subprocess.TimeoutExpired:
            raise RuntimeError("kiro-cli не отвечает")
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Выполнение chat completion через kiro-cli.
        
        Args:
            messages: Список сообщений в формате OpenAI
            **kwargs: Дополнительные параметры
            
        Returns:
            Ответ в формате OpenAI API
        """
        # Создаем временный файл с промптом
        prompt = self._format_messages(messages)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(prompt)
            temp_file = f.name
        
        try:
            # Запускаем kiro-cli в неинтерактивном режиме
            cmd = [
                "kiro-cli", "chat",
                "--input-file", temp_file,
                "--non-interactive"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 минут таймаут
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"Ошибка kiro-cli: {result.stderr}")
            
            # Форматируем ответ в стиле OpenAI API
            return {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": result.stdout.strip()
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": len(prompt.split()),
                    "completion_tokens": len(result.stdout.split()),
                    "total_tokens": len(prompt.split()) + len(result.stdout.split())
                }
            }
            
        finally:
            # Удаляем временный файл
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def stream_completion(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Iterator[Dict[str, Any]]:
        """
        Потоковое выполнение chat completion.
        
        Args:
            messages: Список сообщений в формате OpenAI
            **kwargs: Дополнительные параметры
            
        Yields:
            Чанки ответа в формате OpenAI API
        """
        # kiro-cli не поддерживает потоковый режим,
        # поэтому эмулируем его через обычный запрос
        response = self.chat_completion(messages, **kwargs)
        content = response["choices"][0]["message"]["content"]
        
        # Разбиваем ответ на чанки по словам
        words = content.split()
        for i, word in enumerate(words):
            chunk = {
                "choices": [{
                    "delta": {
                        "content": word + (" " if i < len(words) - 1 else "")
                    },
                    "finish_reason": None if i < len(words) - 1 else "stop"
                }]
            }
            yield chunk
    
    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """
        Форматирование сообщений в промпт для kiro-cli.
        
        Args:
            messages: Список сообщений
            
        Returns:
            Отформатированный промпт
        """
        prompt_parts = []
        
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
        
        return "\n\n".join(prompt_parts)
