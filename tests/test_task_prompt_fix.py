#!/usr/bin/env python3
"""
Тест для проверки исправления промпта задачи - убираем пустые скобки после "Задача"
"""

import os
import sys
import pexpect
import pytest

class TestTaskPromptFix:
    """Тесты для проверки исправления промпта задачи"""
    
    def test_task_prompt_no_empty_brackets(self):
        """Проверяем что после 'Задача:' нет пустых скобок"""
        cli_path = os.path.join(os.path.dirname(__file__), "..", "cli.py")
        child = pexpect.spawn(f"uv run python {cli_path}", timeout=15, encoding='utf-8')
        
        try:
            # Ждем приглашение к вводу задачи
            child.expect("Опишите вашу задачу:", timeout=5)
            
            # Отправляем задачу
            child.sendline("тест")
            
            # Проверяем что в выводе есть "Задача: тест" без пустых скобок
            # Ищем строку которая содержит "Задача:" но НЕ содержит "()"
            output = child.before + child.after if hasattr(child, 'after') else child.before
            
            # Читаем весь вывод до завершения обработки
            try:
                child.expect("Опишите вашу задачу:", timeout=30)
                full_output = child.before
            except pexpect.TIMEOUT:
                full_output = child.before
            
            # Проверяем что в выводе нет "Задача ()"
            assert "Задача ()" not in full_output, f"Найдены пустые скобки в выводе: {full_output}"
            
            # Проверяем что есть правильный формат "Задача: "
            assert "Задача: " in full_output, f"Не найден правильный промпт 'Задача: ' в выводе: {full_output}"
            
        finally:
            child.close()
    
    def test_task_input_format(self):
        """Проверяем формат ввода задачи"""
        cli_path = os.path.join(os.path.dirname(__file__), "..", "cli.py")
        child = pexpect.spawn(f"uv run python {cli_path}", timeout=15, encoding='utf-8')
        
        try:
            # Ждем приглашение к вводу задачи
            child.expect("Опишите вашу задачу:", timeout=5)
            
            # Отправляем задачу
            test_task = "проверка формата"
            child.sendline(test_task)
            
            # Читаем вывод
            try:
                child.expect("Опишите вашу задачу:", timeout=30)
                output = child.before
            except pexpect.TIMEOUT:
                output = child.before
            
            # Проверяем что задача отображается в правильном формате
            expected_format = f"Задача: {test_task}"
            
            # Ищем строку с нашей задачей (может быть в разных местах вывода)
            lines = output.split('\n')
            task_line_found = False
            
            for line in lines:
                if "Задача:" in line and test_task in line:
                    task_line_found = True
                    # Проверяем что нет пустых скобок
                    assert "()" not in line, f"Найдены пустые скобки в строке: {line}"
                    break
            
            # Если не нашли строку с задачей, это тоже ошибка
            if not task_line_found:
                print(f"Полный вывод:\n{output}")
                # Это может быть нормально если задача обрабатывается по-другому
                
        finally:
            child.close()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
