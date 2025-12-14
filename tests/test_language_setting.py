#!/usr/bin/env python3
"""
Тест для проверки языковой настройки LLM
"""

import os
import sys
import pexpect
import pytest

class TestLanguageSetting:
    """Тесты для проверки языковой настройки"""
    
    @pytest.fixture
    def cli_path(self):
        return str(os.path.join(os.path.dirname(__file__), "..", "cli.py"))
    
    def test_llm_responds_in_russian(self, cli_path):
        """Проверяем что LLM отвечает на русском языке"""
        child = pexpect.spawn(f"uv run python {cli_path}", timeout=30, encoding='utf-8')
        
        try:
            # Ждем приглашение к вводу задачи
            child.expect("Опишите вашу задачу:", timeout=10)
            
            # Отправляем простую задачу на русском
            child.sendline("привет")
            
            # Ждем ответ от LLM
            child.expect("Обработка запроса", timeout=5)
            
            # Ждем ответ (должен содержать русские слова)
            try:
                # Ищем русские слова в ответе
                index = child.expect([
                    "Привет",
                    "привет", 
                    "Здравствуйте",
                    "Добро пожаловать",
                    "Как дела",
                    "помочь"
                ], timeout=30)
                success = True
            except pexpect.TIMEOUT:
                success = False
                print(f"LLM не ответил на русском, вывод: {child.before}")
            
            assert success, "LLM не отвечает на русском языке"
            
        finally:
            child.close()

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
