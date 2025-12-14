#!/usr/bin/env python3
"""
Точка входа для FlowCraft CLI
"""
import sys
import os
from pathlib import Path

# Добавить src в путь и изменить рабочую директорию
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))
os.chdir(src_path)

# Импортировать и запустить main
from cli import main

if __name__ == "__main__":
    main()
