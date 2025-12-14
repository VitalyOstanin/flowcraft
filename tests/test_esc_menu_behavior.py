#!/usr/bin/env python3
"""
Тест для проверки поведения ESC в меню
"""

import os
import sys
import pexpect
import pytest

class TestESCMenuBehavior:
    """Тесты для проверки ESC поведения в меню"""
    
    @pytest.fixture
    def cli_path(self):
        return str(os.path.join(os.path.dirname(__file__), "..", "cli.py"))
    
    def test_esc_exits_menu(self, cli_path):
        """Проверяем что ESC выходит из меню"""
        child = pexpect.spawn(f"uv run python {cli_path}", timeout=15, encoding='utf-8')
        
        try:
            # Ждем приглашение к вводу задачи
            child.expect("Опишите вашу задачу:", timeout=10)
            
            # Открываем меню
            child.sendline("/menu")
            child.expect("Выберите действие", timeout=10)
            
            # Отправляем ESC и Enter (input() требует Enter для завершения)
            child.send('\x1b\n')
            
            # Должны увидеть сообщение о возврате и новое приглашение
            child.expect("Возврат к основному меню", timeout=5)
            child.expect("Опишите вашу задачу:", timeout=5)
            
        finally:
            child.close()
    
    def test_menu_shows_esc_option(self, cli_path):
        """Проверяем что в меню показывается опция ESC"""
        child = pexpect.spawn(f"uv run python {cli_path}", timeout=15, encoding='utf-8')
        
        try:
            # Ждем приглашение к вводу задачи
            child.expect("Опишите вашу задачу:", timeout=10)
            
            # Открываем меню
            child.sendline("/menu")
            
            # Проверяем что есть опция ESC
            child.expect("ESC. Вернуться к вводу задач", timeout=10)
            
            # Выходим из меню через ESC
            child.send('\x1b\n')
            child.expect("Возврат к основному меню", timeout=5)
            child.expect("Опишите вашу задачу:", timeout=5)
            
        finally:
            child.close()

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
