#!/usr/bin/env python3

import asyncio
import sys
import os
import pytest

# Добавляем src в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

@pytest.mark.asyncio
async def test_workflow():
    """Простой тест workflow."""
    
    from workflows.state import create_initial_state
    from workflows.nodes import StartNode, EndNode
    
    print("Тестирование узлов workflow...")
    
    # Создаем начальное состояние
    state = create_initial_state("тестовая задача", "test")
    print(f"Начальное состояние: {type(state)}")
    
    # Тестируем StartNode
    start_node = StartNode()
    state = await start_node.execute(state)
    print(f"После StartNode: current_node = {state.get('current_node')}")
    
    # Тестируем EndNode
    end_node = EndNode()
    state = await end_node.execute(state)
    print(f"После EndNode: finished = {state.get('finished')}")
    print(f"Результат: {state.get('result')}")
    
    print("Тест завершен успешно!")

if __name__ == "__main__":
    asyncio.run(test_workflow())
