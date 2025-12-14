"""
Инструменты для выполнения системных команд
"""

import subprocess
from typing import Optional, Tuple
from rich.console import Console

console = Console()

class ShellTools:
    """Инструменты для выполнения системных команд"""
    
    def __init__(self, trust_manager):
        self.trust_manager = trust_manager
    
    def execute_command(self, cmd: str, cwd: Optional[str] = None) -> Tuple[bool, str, str]:
        """
        Выполнить системную команду с проверкой доверия
        
        Returns:
            Tuple[success, stdout, stderr]
        """
        # Проверка разрешения на выполнение
        if not self.trust_manager.is_command_allowed(cmd):
            console.print(f"Команда отклонена: {cmd}", style="red")
            return False, "", "Команда отклонена пользователем"
        
        try:
            console.print(f"Выполняется: [bold]{cmd}[/bold]", style="blue")
            
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300  # 5 минут таймаут
            )
            
            success = result.returncode == 0
            
            if success:
                console.print("Команда выполнена успешно", style="green")
            else:
                console.print(f"Команда завершилась с ошибкой (код {result.returncode})", style="red")
            
            return success, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            error_msg = "Команда превысила таймаут (5 минут)"
            console.print(error_msg, style="red")
            return False, "", error_msg
            
        except Exception as e:
            error_msg = f"Ошибка выполнения команды: {e}"
            console.print(error_msg, style="red")
            return False, "", error_msg
    
    def execute_safe_command(self, cmd: str, cwd: Optional[str] = None) -> Tuple[bool, str, str]:
        """
        Выполнить безопасную команду без запроса разрешения
        (только для команд чтения типа git status, ls и т.д.)
        """
        safe_commands = [
            "git status", "git log", "git diff", "git branch",
            "ls", "pwd", "whoami", "date", "cat", "head", "tail"
        ]
        
        cmd_start = cmd.split()[0] if cmd.split() else ""
        is_safe = any(cmd.startswith(safe_cmd) for safe_cmd in safe_commands)
        
        if not is_safe:
            return self.execute_command(cmd, cwd)
        
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            return result.returncode == 0, result.stdout, result.stderr
            
        except Exception as e:
            return False, "", str(e)
