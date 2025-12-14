#!/usr/bin/env python3
"""
Интеграционный тест для проверки смены workflow
"""

import os
import sys
import pexpect
import pytest
from pathlib import Path

def get_test_env():
    """Получить путь к тестовому окружению"""
    return os.path.join(os.path.dirname(__file__), 'test_env')

def test_workflow_selection_menu():
    """Тест выбора workflow через меню"""
    
    # Настраиваем окружение для теста
    env = os.environ.copy()
    env['HOME'] = get_test_env()
    
    # Запускаем процесс
    child = pexpect.spawn(
        'uv', 
        ['run', 'python', os.path.join(os.path.dirname(__file__), '..', 'cli.py')],
        env=env,
        timeout=10,
        encoding='utf-8'
    )
    
    try:
        # Ждем приглашение ввода задачи
        child.expect("Задача:")
        
        # Вводим команду меню
        child.sendline("/menu")
        
        # Ждем появления меню
        child.expect("=== Меню FlowCraft ===")
        child.expect("Сменить workflow")  # Убираем номер из-за ANSI кодов
        child.expect("Выберите действие")
        
        # Выбираем пункт 1 (сменить workflow)
        child.send("1")
        
        # Ждем появления списка workflow
        child.expect("=== Выбор Workflow ===", timeout=5)
        child.expect("Доступные Workflow")  # Ищем заголовок таблицы
        child.expect("Выберите workflow")
        
        # Выбираем workflow номер 1
        child.sendline("1")
        
        # Проверяем подтверждение выбора
        child.expect("Выбран workflow", timeout=5)
        
        # Проверяем возврат к основному циклу
        child.expect("Опишите вашу задачу", timeout=5)
        
        # Завершаем процесс
        child.sendcontrol('c')
        child.close()
        
    except pexpect.TIMEOUT:
        print(f"Timeout. Вывод процесса:\n{child.before}")
        print(f"После:\n{child.after}")
        raise
    except pexpect.EOF:
        print(f"Неожиданное завершение. Вывод:\n{child.before}")
        raise
    finally:
        if child.isalive():
            child.terminate()

def test_workflow_selection_invalid_choice():
    """Тест обработки неверного выбора workflow"""
    
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
        child.expect("Задача:")
        child.sendline("/menu")
        child.expect("Выберите действие")
        child.send("1")
        
        # Ждем список workflow
        child.expect("Выберите workflow")
        
        # Вводим неверный номер
        child.sendline("999")
        
        # Проверяем сообщение об ошибке
        child.expect("Неверный выбор", timeout=5)
        
        child.sendcontrol('c')
        child.close()
        
    except pexpect.TIMEOUT:
        print(f"Timeout. Вывод процесса:\n{child.before}")
        raise
    finally:
        if child.isalive():
            child.terminate()

def test_workflow_selection_esc_return():
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
        child.expect("Задача:")
        child.sendline("/menu")
        child.expect("Выберите действие")
        
        # Нажимаем ESC
        child.send('\x1b')  # ESC код
        
        # Проверяем возврат к основному меню
        child.expect("Возврат к основному меню", timeout=5)
        child.expect("Задача:", timeout=5)
        
        child.sendcontrol('c')
        child.close()
        
    except pexpect.TIMEOUT:
        print(f"Timeout. Вывод процесса:\n{child.before}")
        raise
    finally:
        if child.isalive():
            child.terminate()

if __name__ == "__main__":
    # Запуск отдельных тестов для отладки
    test_workflow_selection_menu()
    print("✓ Тест выбора workflow через меню прошел")
    
    test_workflow_selection_invalid_choice()
    print("✓ Тест неверного выбора прошел")
    
    test_workflow_selection_esc_return()
    print("✓ Тест возврата по ESC прошел")
    
    print("✓ Все тесты смены workflow прошли успешно")
