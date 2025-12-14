#!/usr/bin/env python3
"""
Простой тест смены workflow без LLM
"""

import os
import sys
import pexpect
from pathlib import Path

def get_test_env():
    """Получить путь к тестовому окружению"""
    return os.path.join(os.path.dirname(__file__), 'test_env')

def test_workflow_menu_navigation():
    """Тест навигации по меню смены workflow"""
    
    env = os.environ.copy()
    env['HOME'] = get_test_env()
    
    child = pexpect.spawn(
        'uv', 
        ['run', 'python', os.path.join(os.path.dirname(__file__), '..', 'cli.py')],
        env=env,
        timeout=10,
        encoding='utf-8'
    )
    
    try:
        # Ждем приглашение ввода задачи
        child.expect("Задача:", timeout=5)
        
        # Вводим команду меню
        child.sendline("/menu")
        
        # Ждем появления меню
        child.expect("=== Меню FlowCraft ===", timeout=5)
        child.expect("Сменить workflow", timeout=5)
        child.expect("Выберите действие", timeout=5)
        
        # Выбираем пункт 1 (сменить workflow)
        child.send("1")
        
        # Ждем появления списка workflow
        child.expect("=== Выбор Workflow ===", timeout=5)
        child.expect("Доступные Workflow", timeout=5)
        child.expect("Выберите workflow", timeout=5)
        
        print("✓ Меню смены workflow работает корректно")
        
        # Завершаем процесс
        child.sendcontrol('c')
        child.close()
        
    except pexpect.TIMEOUT as e:
        print(f"Timeout. Вывод процесса:\n{child.before}")
        print(f"После:\n{child.after}")
        raise
    finally:
        if child.isalive():
            child.terminate()

if __name__ == "__main__":
    test_workflow_menu_navigation()
    print("✓ Тест навигации по меню смены workflow прошел успешно")
