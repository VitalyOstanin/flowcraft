"""
Инструменты для работы с файловой системой
"""

import os
import subprocess
from pathlib import Path
from typing import List, Optional
from rich.console import Console

console = Console()

class FileSystemTools:
    """Инструменты для работы с файловой системой"""
    
    def read_file(self, file_path: str) -> str:
        """Прочитать файл"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            console.print(f"Ошибка чтения файла {file_path}: {e}", style="red")
            return ""
    
    def write_file(self, file_path: str, content: str) -> bool:
        """Записать файл"""
        try:
            # Создать директорию если не существует
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            console.print(f"Ошибка записи файла {file_path}: {e}", style="red")
            return False
    
    def create_directory(self, dir_path: str) -> bool:
        """Создать директорию"""
        try:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            console.print(f"Ошибка создания директории {dir_path}: {e}", style="red")
            return False
    
    def find_files(self, pattern: str, directory: str = ".") -> List[str]:
        """Найти файлы используя fdfind"""
        try:
            result = subprocess.run(
                ["fdfind", pattern, directory],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip().split('\n') if result.stdout.strip() else []
        except subprocess.CalledProcessError:
            # Fallback на обычный find
            try:
                result = subprocess.run(
                    ["find", directory, "-name", pattern],
                    capture_output=True,
                    text=True,
                    check=True
                )
                return result.stdout.strip().split('\n') if result.stdout.strip() else []
            except Exception as e:
                console.print(f"Ошибка поиска файлов: {e}", style="red")
                return []
    
    def list_directory(self, directory: str = ".") -> List[str]:
        """Список файлов в директории"""
        try:
            return [str(p) for p in Path(directory).iterdir()]
        except Exception as e:
            console.print(f"Ошибка чтения директории {directory}: {e}", style="red")
            return []
