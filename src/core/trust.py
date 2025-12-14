"""
Система доверия команд FlowCraft
"""

import fnmatch
from enum import Enum
from typing import Dict, Set, Optional
from rich.console import Console
from rich.prompt import Prompt

console = Console()

class TrustLevel(Enum):
    """Уровни доверия команд"""
    ONCE = "once"        # y - разрешить один раз
    SESSION = "session"  # s - разрешить в сессии (не сохраняется)
    ALWAYS = "always"    # t - запомнить навсегда
    DENY = "deny"        # n - отклонить

class TrustManager:
    """Менеджер доверия команд"""
    
    def __init__(self, settings_manager):
        self.settings_manager = settings_manager
        self.session_permissions: Set[str] = set()
    
    def check_command(self, cmd: str) -> TrustLevel:
        """Проверить уровень доверия для команды"""
        # Проверка постоянных правил
        for pattern, level in self.settings_manager.settings.trust_rules.items():
            if self._matches_pattern(cmd, pattern):
                return TrustLevel.ALWAYS
        
        # Проверка сессионных разрешений
        if cmd in self.session_permissions:
            return TrustLevel.SESSION
            
        return TrustLevel.ONCE
    
    def _matches_pattern(self, cmd: str, pattern: str) -> bool:
        """Проверить соответствие команды паттерну"""
        return fnmatch.fnmatch(cmd, pattern)
    
    def request_permission(self, cmd: str) -> TrustLevel:
        """Запросить разрешение у пользователя"""
        console.print(f"Выполнить команду: [bold]{cmd}[/bold]")
        console.print("y - разрешить один раз")
        console.print("s - разрешить в сессии") 
        console.print("t - запомнить навсегда")
        console.print("n - отклонить")
        
        response = Prompt.ask("Выбор", choices=["y", "s", "t", "n"], default="n")
        
        if response == 'y':
            return TrustLevel.ONCE
        elif response == 's':
            self.session_permissions.add(cmd)
            return TrustLevel.SESSION
        elif response == 't':
            self.settings_manager.add_trust_rule(cmd, "always")
            return TrustLevel.ALWAYS
        else:
            return TrustLevel.DENY
    
    def is_command_allowed(self, cmd: str) -> bool:
        """Проверить разрешена ли команда"""
        trust_level = self.check_command(cmd)
        
        if trust_level in [TrustLevel.ALWAYS, TrustLevel.SESSION]:
            return True
        elif trust_level == TrustLevel.ONCE:
            permission = self.request_permission(cmd)
            return permission != TrustLevel.DENY
        else:
            return False
