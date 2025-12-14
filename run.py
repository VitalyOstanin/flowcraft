#!/usr/bin/env python3
"""
Скрипт запуска FlowCraft из src директории
"""

import sys
import os
from pathlib import Path

# Добавить src в путь
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Импортировать и запустить cli
if __name__ == "__main__":
    # Изменить рабочую директорию на src
    os.chdir(src_path)
    
    # Импортировать main из cli
    sys.path.insert(0, str(Path(__file__).parent))
    from cli import main
    
    main()
