"""Интеграционные тесты для CLI с использованием pexpect."""

import os
import sys
import pexpect
import pytest
from pathlib import Path


class TestCLIIntegration:
    """Интеграционные тесты CLI приложения."""
    
    @pytest.fixture
    def cli_path(self):
        """Путь к CLI скрипту."""
        return str(Path(__file__).parent.parent / "cli.py")
    
    def test_cli_starts_and_shows_menu(self, cli_path):
        """Тест запуска CLI и отображения меню."""
        # Запускаем CLI через uv с UTF-8 кодировкой
        child = pexpect.spawn(f"uv run python {cli_path}", timeout=10, encoding='utf-8')
        
        try:
            # Ожидаем появления интерфейса
            child.expect("FlowCraft", timeout=5)
            child.expect("Опишите вашу задачу:", timeout=5)
            
            # Завершаем процесс
            child.terminate()
            child.wait()
            
        finally:
            if child.isalive():
                child.kill(9)
            child.close()
    
    def test_cli_help_command(self, cli_path):
        """Тест команды помощи."""
        child = pexpect.spawn(f"uv run python {cli_path}", timeout=10, encoding='utf-8')
        
        try:
            child.expect("Опишите вашу задачу:", timeout=5)
            
            # Вводим /help
            child.sendline("/help")
            child.expect("Доступные команды:", timeout=5)
            
            # Завершаем процесс
            child.terminate()
            child.wait()
            
        finally:
            if child.isalive():
                child.kill(9)
            child.close()
    
    def test_cli_pipe_input(self, cli_path):
        """Тест pipe ввода."""
        # Тестируем pipe функциональность
        child = pexpect.spawn(f"echo 'тестовый запрос' | uv run python {cli_path}", timeout=10, encoding='utf-8')
        
        try:
            # Ожидаем обработки pipe ввода
            child.expect(pexpect.EOF, timeout=10)
            
        finally:
            child.close()
    
    @pytest.mark.skipif(sys.platform == "win32", reason="pexpect не поддерживается на Windows")
    def test_cli_interactive_session(self, cli_path):
        """Тест интерактивной сессии."""
        child = pexpect.spawn(f"uv run python {cli_path}", timeout=10, encoding='utf-8')
        
        try:
            child.expect("Опишите вашу задачу:", timeout=5)
            
            # Отправляем простой запрос
            child.sendline("привет")
            
            # Ожидаем ответа от LLM
            child.expect("Привет", timeout=30)
            
            # Завершаем процесс
            child.terminate()
            child.wait()
            
        finally:
            if child.isalive():
                child.kill(9)
            child.close()
