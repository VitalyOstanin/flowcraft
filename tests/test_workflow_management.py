#!/usr/bin/env python3
"""
Тест управления workflow
"""

import os
import sys
import pexpect

def get_test_env():
    """Получить путь к тестовому окружению"""
    return os.path.join(os.path.dirname(__file__), 'test_env')

def test_workflow_management_menu():
    """Тест меню управления workflow"""
    
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
        # Переходим в меню
        child.expect("Задача:", timeout=5)
        child.sendline("/menu")
        child.expect("Выберите действие", timeout=5)
        
        # Выбираем пункт 2 (управление workflow)
        child.send("2")
        
        # Ждем появления подменю
        child.expect("=== Управление Workflow ===", timeout=5)
        child.expect("Создать workflow", timeout=5)
        child.expect("Управление этапами workflow", timeout=5)
        child.expect("Выберите действие", timeout=5)
        
        print("✓ Меню управления workflow работает")
        
        # Выбираем список workflow
        child.sendline("2")
        child.expect("=== Список Workflow ===", timeout=5)
        
        print("✓ Список workflow отображается")
        
        child.sendcontrol('c')
        child.close()
        
    except pexpect.TIMEOUT as e:
        print(f"Timeout. Вывод процесса:\n{child.before}")
        raise
    finally:
        if child.isalive():
            child.terminate()

def test_workflow_stages_restriction():
    """Тест ограничения управления этапами для default workflow"""
    
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
        # Переходим в управление workflow -> управление этапами
        child.expect("Задача:", timeout=5)
        child.sendline("/menu")
        child.expect("Выберите действие", timeout=5)
        child.send("2")  # Управление workflow
        child.expect("Выберите действие", timeout=5)
        child.sendline("4")  # Управление этапами
        
        # Проверяем сообщение об ограничении
        child.expect("недоступно для default workflow", timeout=5)
        child.expect("Создайте собственный workflow", timeout=5)
        
        print("✓ Ограничение для default workflow работает")
        
        child.sendcontrol('c')
        child.close()
        
    except pexpect.TIMEOUT as e:
        print(f"Timeout. Вывод процесса:\n{child.before}")
        raise
    finally:
        if child.isalive():
            child.terminate()

if __name__ == "__main__":
    test_workflow_management_menu()
    print("✓ Тест меню управления workflow прошел")
    
    test_workflow_stages_restriction()
    print("✓ Тест ограничения этапов прошел")
    
    print("✓ Все тесты управления workflow прошли успешно")
