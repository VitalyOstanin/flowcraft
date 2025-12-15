#!/usr/bin/env python3
"""
Тест исправлений: логирование, таймауты, имена агентов
"""

import sys
from pathlib import Path

# Добавить src в путь
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from core.logging import get_logger, init_logging
from workflows.base import WorkflowStep
from workflows.nodes import AgentNode
from workflows.state import create_initial_state

def test_logging():
    """Тест системы логирования"""
    print("=== Тест логирования ===")
    
    init_logging()
    logger = get_logger("test")
    
    logger.info("Тестовое сообщение INFO")
    logger.warning("Тестовое сообщение WARNING")
    logger.error("Тестовое сообщение ERROR")
    
    print("✓ Логирование работает")

def test_workflow_step_timeout():
    """Тест поддержки таймаутов в WorkflowStep"""
    print("\n=== Тест таймаутов ===")
    
    # Тест с дефолтным таймаутом
    step1 = WorkflowStep(name="test1", roles=["analyst"])
    assert step1.timeout == 30, f"Ожидался таймаут 30, получен {step1.timeout}"
    
    # Тест с кастомным таймаутом
    step2 = WorkflowStep(name="test2", roles=["analyst"], timeout=60)
    assert step2.timeout == 60, f"Ожидался таймаут 60, получен {step2.timeout}"
    
    print("✓ Таймауты в WorkflowStep работают")

def test_agent_naming():
    """Тест правильного именования агентов"""
    print("\n=== Тест именования агентов ===")
    
    # Создаем mock agent manager
    class MockAgentManager:
        def get_agent_config(self, name):
            return {"name": name, "system_prompt": f"Ты {name}"}
    
    # Создаем AgentNode
    stage_config = {"description": "Test stage", "timeout": 30}
    agent_node = AgentNode(
        name="test_stage",
        agent_name="analyst",
        stage_config=stage_config,
        agent_manager=MockAgentManager()
    )
    
    assert agent_node.agent_name == "analyst", f"Ожидалось 'analyst', получено '{agent_node.agent_name}'"
    
    print("✓ Именование агентов исправлено")

def main():
    """Запуск всех тестов"""
    print("Тестирование исправлений FlowCraft\n")
    
    try:
        test_logging()
        test_workflow_step_timeout()
        test_agent_naming()
        
        print("\n🎉 Все тесты прошли успешно!")
        
    except Exception as e:
        print(f"\n❌ Ошибка в тестах: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
