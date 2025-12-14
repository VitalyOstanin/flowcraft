#!/usr/bin/env python3
"""
Тест поведения ESC в меню
"""

import os
import sys
import pexpect

def get_test_env():
    """Получить путь к тестовому окружению"""
    return os.path.join(os.path.dirname(__file__), 'test_env')

def test_menu_esc_behavior():
    """Тест возврата из меню по ESC"""
    
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
        
        # Нажимаем ESC
        child.send('\x1b')  # ESC код
        
        # Проверяем возврат к основному меню
        child.expect("Возврат к основному меню", timeout=5)
        child.expect("Задача:", timeout=5)
        
        print("✓ ESC корректно возвращает из меню")
        
        child.sendcontrol('c')
        child.close()
        
    except pexpect.TIMEOUT as e:
        print(f"Timeout. Вывод процесса:\n{child.before}")
        raise
    finally:
        if child.isalive():
            child.terminate()

if __name__ == "__main__":
    test_menu_esc_behavior()
    print("✓ Тест ESC в меню прошел успешно")
