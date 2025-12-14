#!/usr/bin/env python3
"""
Интеграционный тест новой структуры меню с изолированной средой
"""

import os
import sys
import pexpect

def get_test_env():
    """Получить путь к тестовому окружению"""
    return os.path.join(os.path.dirname(__file__), 'test_env')

def test_new_menu_structure():
    """Тест новой структуры меню с тестовым каталогом"""
    
    env = os.environ.copy()
    env['HOME'] = get_test_env()
    
    child = pexpect.spawn(
        'uv', 
        ['run', 'python', os.path.join(os.path.dirname(__file__), '..', 'cli.py')],
        env=env,
        timeout=15,
        encoding='utf-8'
    )
    
    try:
        # Проверяем основное меню
        child.expect("Задача:", timeout=5)
        child.sendline("/menu")
        
        # Проверяем новую структуру меню
        child.expect("=== Меню FlowCraft ===", timeout=5)
        child.expect("Сменить workflow", timeout=5)
        child.expect("Управление workflow", timeout=5)
        child.expect("Управление агентами", timeout=5)
        child.expect("Показать настройки", timeout=5)
        child.expect("Выход", timeout=5)
        child.expect("Выберите действие", timeout=5)
        
        print("✓ Новая структура меню корректна")
        
        # Тестируем управление workflow
        child.send("2")
        child.expect("=== Управление Workflow ===", timeout=5)
        child.expect("Создать workflow", timeout=5)
        child.expect("Список workflow", timeout=5)
        child.expect("Удалить workflow", timeout=5)
        child.expect("Управление этапами workflow", timeout=5)
        child.expect("Назад", timeout=5)
        
        print("✓ Подменю управления workflow работает")
        
        # Тестируем ограничение этапов
        child.sendline("4")
        child.expect("недоступно для default workflow", timeout=5)
        
        print("✓ Ограничение этапов для default workflow работает")
        
        # Возвращаемся назад
        child.sendline("5")
        child.expect("Выберите действие", timeout=5)
        
        print("✓ Возврат из подменю работает")
        
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
    test_new_menu_structure()
    print("✓ Тест новой структуры меню прошел успешно")
