"""
Инструменты для поиска содержимого
"""

import subprocess
from typing import List, Dict, Optional
from rich.console import Console

console = Console()

class SearchTools:
    """Инструменты для поиска содержимого в файлах"""
    
    def search_content(self, pattern: str, directory: str = ".", 
                      file_types: Optional[List[str]] = None) -> List[Dict[str, str]]:
        """
        Поиск содержимого в файлах используя ripgrep
        
        Returns:
            List[Dict] с полями: file, line_number, line_content
        """
        try:
            cmd = ["rg", "--line-number", "--no-heading", pattern, directory]
            
            # Добавить фильтр по типам файлов
            if file_types:
                for file_type in file_types:
                    cmd.extend(["--type", file_type])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            matches = []
            for line in result.stdout.strip().split('\n'):
                if ':' in line:
                    parts = line.split(':', 2)
                    if len(parts) >= 3:
                        matches.append({
                            'file': parts[0],
                            'line_number': parts[1],
                            'line_content': parts[2]
                        })
            
            return matches
            
        except subprocess.CalledProcessError:
            # Fallback на grep
            return self._fallback_search(pattern, directory)
        except Exception as e:
            console.print(f"Ошибка поиска: {e}", style="red")
            return []
    
    def _fallback_search(self, pattern: str, directory: str) -> List[Dict[str, str]]:
        """Fallback поиск через grep"""
        try:
            result = subprocess.run(
                ["grep", "-rn", pattern, directory],
                capture_output=True,
                text=True,
                check=True
            )
            
            matches = []
            for line in result.stdout.strip().split('\n'):
                if ':' in line:
                    parts = line.split(':', 2)
                    if len(parts) >= 3:
                        matches.append({
                            'file': parts[0],
                            'line_number': parts[1],
                            'line_content': parts[2]
                        })
            
            return matches
            
        except Exception as e:
            console.print(f"Ошибка fallback поиска: {e}", style="red")
            return []
    
    def search_files_by_content(self, pattern: str, directory: str = ".") -> List[str]:
        """Найти файлы содержащие паттерн"""
        try:
            result = subprocess.run(
                ["rg", "--files-with-matches", pattern, directory],
                capture_output=True,
                text=True,
                check=True
            )
            
            return result.stdout.strip().split('\n') if result.stdout.strip() else []
            
        except subprocess.CalledProcessError:
            # Fallback на grep
            try:
                result = subprocess.run(
                    ["grep", "-rl", pattern, directory],
                    capture_output=True,
                    text=True,
                    check=True
                )
                return result.stdout.strip().split('\n') if result.stdout.strip() else []
            except Exception:
                return []
        except Exception as e:
            console.print(f"Ошибка поиска файлов: {e}", style="red")
            return []
