"""
Система логирования FlowCraft.
"""

import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Optional


def init_logging(logs_dir: Optional[str] = None):
    """Инициализация системы логирования."""
    if logs_dir is None:
        logs_dir = os.path.expanduser("~/.flowcraft/logs")
    
    logs_path = Path(logs_dir)
    logs_path.mkdir(parents=True, exist_ok=True)
    
    # Очистка существующих handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Настройка корневого логгера для всех модулей
    root_logger.setLevel(logging.DEBUG)
    
    # Настройка основного логгера
    logger = logging.getLogger("flowcraft")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    
    # Файловый handler
    log_file = logs_path / f"flowcraft_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    
    # Консольный handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    
    # Форматтер
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Добавляем handlers к корневому логгеру (для всех модулей)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Принудительная запись тестового сообщения
    logger.info("Система логирования инициализирована")
    logger.debug("DEBUG логирование работает")
    logger.error("ERROR логирование работает")
    file_handler.flush()


def get_logger(name: str = "flowcraft") -> logging.Logger:
    """Получить логгер."""
    return logging.getLogger(name)
