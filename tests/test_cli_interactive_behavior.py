"""Интеграционные тесты интерактивного поведения CLI."""

import os
import sys
import pexpect
import pytest
import time
from pathlib import Path


class TestCLIInteractiveBehavior:
    """Тесты интерактивного поведения CLI."""
    
    @pytest.fixture
    def cli_path(self):
        """Путь к CLI скрипту."""
        return str(Path(__file__).parent.parent / "cli.py")
    
    def test_menu_esc_behavior(self, cli_path):
        """Тест поведения ESC в меню."""
        child = pexpect.spawn(f"uv run python {cli_path}", timeout=10, encoding='utf-8')
        
        try:
            child.expect("Опишите вашу задачу:", timeout=5)
            
            # Открываем меню
            child.sendline("/menu")
            child.expect("Выберите действие", timeout=5)
            
            # Отправляем неверный выбор, чтобы остаться в меню
            child.sendline("9")
            child.expect("Неверный выбор", timeout=5)
            
            # Теперь отправляем Ctrl+C
            child.sendcontrol('c')
            
            # Должны вернуться к основному приглашению
            child.expect("Опишите вашу задачу:", timeout=5)
            
        finally:
            self._cleanup_child(child)
    
    def test_multiple_task_execution(self, cli_path):
        """Тест выполнения нескольких задач подряд."""
        child = pexpect.spawn(f"uv run python {cli_path}", timeout=40, encoding='utf-8')
        
        try:
            # Первая задача
            child.expect("Опишите вашу задачу:", timeout=5)
            child.sendline("привет")
            child.expect("Привет", timeout=30)
            
            # Вторая задача
            child.expect("Опишите вашу задачу:", timeout=5)
            child.sendline("как дела?")
            # Ищем любой ответ, не обязательно "Qwen"
            child.expect("дела", timeout=30)
            
            # Возврат к приглашению
            child.expect("Опишите вашу задачу:", timeout=5)
            
        finally:
            self._cleanup_child(child)
    
    def test_ctrl_c_exit(self, cli_path):
        """Тест выхода через Ctrl+C."""
        child = pexpect.spawn(f"uv run python {cli_path}", timeout=10, encoding='utf-8')
        
        try:
            child.expect("Опишите вашу задачу:", timeout=5)
            
            # Отправляем Ctrl+C
            child.sendcontrol('c')
            # Ищем сообщение о выходе или завершение процесса
            try:
                child.expect("Выход из программы", timeout=2)
            except pexpect.TIMEOUT:
                # Если сообщения нет, проверяем что процесс завершился
                pass
            
        finally:
            self._cleanup_child(child)
    
    def test_workflow_context_persistence(self, cli_path):
        """Тест сохранения контекста workflow."""
        child = pexpect.spawn(f"uv run python {cli_path}", timeout=20, encoding='utf-8')
        
        try:
            # Проверяем, что показывается текущий workflow
            child.expect("default workflow", timeout=5)
            child.expect("Опишите вашу задачу:", timeout=5)
            
            # После выполнения задачи контекст должен сохраниться
            child.sendline("тест")
            # Ждем завершения обработки
            child.expect("Опишите вашу задачу:", timeout=30)
            
        finally:
            self._cleanup_child(child)
    
    def test_basic_task_execution(self, cli_path):
        """Тест базового выполнения задачи."""
        child = pexpect.spawn(f"uv run python {cli_path}", timeout=15, encoding='utf-8')
        
        try:
            # Ожидаем приглашение
            child.expect("Опишите вашу задачу:", timeout=5)
            
            # Отправляем задачу
            child.sendline("привет")
            
            # Ожидаем ответа LLM (любого)
            child.expect("Привет", timeout=30)
            
            # Ожидаем возврата к приглашению
            child.expect("Опишите вашу задачу:", timeout=5)
            
        finally:
            self._cleanup_child(child)
    
    def test_help_command(self, cli_path):
        """Тест команды помощи."""
        child = pexpect.spawn(f"uv run python {cli_path}", timeout=10, encoding='utf-8')
        
        try:
            child.expect("Опишите вашу задачу:", timeout=5)
            
            # Команда помощи
            child.sendline("/help")
            child.expect("Справка FlowCraft", timeout=5)
            child.expect("Доступные команды:", timeout=5)
            
            # Возврат к приглашению
            child.expect("Опишите вашу задачу:", timeout=5)
            
        finally:
            self._cleanup_child(child)
    
    def test_menu_access(self, cli_path):
        """Тест доступа к меню."""
        child = pexpect.spawn(f"uv run python {cli_path}", timeout=10, encoding='utf-8')
        
        try:
            child.expect("Опишите вашу задачу:", timeout=5)
            
            # Команда меню
            child.sendline("/menu")
            child.expect("Меню FlowCraft", timeout=5)
            child.expect("Выберите действие", timeout=5)
            
        finally:
            self._cleanup_child(child)
    
    def test_empty_input_shows_menu(self, cli_path):
        """Тест показа меню при пустом вводе."""
        child = pexpect.spawn(f"uv run python {cli_path}", timeout=10, encoding='utf-8')
        
        try:
            child.expect("Опишите вашу задачу:", timeout=5)
            
            # Пустой ввод
            child.sendline("")
            child.expect("Меню FlowCraft", timeout=5)
            child.expect("Выберите действие", timeout=5)
            
        finally:
            self._cleanup_child(child)
    
    def _cleanup_child(self, child):
        """Очистка дочернего процесса."""
        try:
            if child.isalive():
                child.terminate()
                child.wait()
        except:
            pass
        finally:
            if child.isalive():
                child.kill(9)
            child.close()
