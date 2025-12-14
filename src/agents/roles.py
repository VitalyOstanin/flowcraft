"""
Определения ролей агентов FlowCraft
"""

from typing import Dict, List

class AgentRoles:
    """Стандартные роли агентов"""
    
    ROLES = {
        "architect": {
            "name": "Архитектор",
            "description": "Проектирование архитектуры системы и принятие технических решений",
            "capabilities": [
                "system_design",
                "architecture_review",
                "technology_selection",
                "scalability_planning"
            ],
            "prompt_template": "Ты архитектор {system_type}. Отвечай на {language}. {context}"
        },
        
        "developer": {
            "name": "Разработчик",
            "description": "Реализация функциональности и написание кода",
            "capabilities": [
                "code_implementation",
                "debugging",
                "refactoring",
                "unit_testing"
            ],
            "prompt_template": "Ты {stack} разработчик. Отвечай на {language}. {context}"
        },
        
        "code_reviewer": {
            "name": "Код-ревьюер",
            "description": "Анализ кода на качество, безопасность и соответствие стандартам",
            "capabilities": [
                "static_analysis",
                "security_check",
                "performance_analysis",
                "code_style_check"
            ],
            "prompt_template": "Ты код-ревьюер. Фокусируйся на {focus_areas}. Отвечай на {language}. {context}"
        },
        
        "security_analyst": {
            "name": "Аналитик безопасности",
            "description": "Анализ безопасности кода и инфраструктуры",
            "capabilities": [
                "vulnerability_scan",
                "dependency_check",
                "security_best_practices",
                "threat_modeling"
            ],
            "prompt_template": "Ты аналитик безопасности. Отвечай на {language}. {context}"
        },
        
        "test_engineer": {
            "name": "Инженер тестирования",
            "description": "Создание и выполнение тестов",
            "capabilities": [
                "unit_testing",
                "integration_testing",
                "test_automation",
                "coverage_analysis"
            ],
            "prompt_template": "Ты инженер тестирования. Отвечай на {language}. {context}"
        },
        
        "devops_engineer": {
            "name": "DevOps инженер",
            "description": "Управление инфраструктурой и процессами деплоя",
            "capabilities": [
                "infrastructure_as_code",
                "ci_cd_pipeline",
                "monitoring_setup",
                "deployment_automation"
            ],
            "prompt_template": "Ты DevOps инженер. Отвечай на {language}. {context}"
        },
        
        "performance_analyst": {
            "name": "Аналитик производительности",
            "description": "Анализ и оптимизация производительности",
            "capabilities": [
                "performance_profiling",
                "bottleneck_analysis",
                "optimization_suggestions",
                "load_testing"
            ],
            "prompt_template": "Ты аналитик производительности. Отвечай на {language}. {context}"
        },
        
        "documentation_writer": {
            "name": "Технический писатель",
            "description": "Создание и поддержка документации",
            "capabilities": [
                "api_documentation",
                "user_guides",
                "technical_writing",
                "markdown_formatting"
            ],
            "prompt_template": "Ты технический писатель. Отвечай на {language}. {context}"
        }
    }
    
    @classmethod
    def get_role_info(cls, role_key: str) -> Dict:
        """Получить информацию о роли"""
        return cls.ROLES.get(role_key, {})
    
    @classmethod
    def get_all_roles(cls) -> List[str]:
        """Получить список всех ролей"""
        return list(cls.ROLES.keys())
    
    @classmethod
    def get_role_capabilities(cls, role_key: str) -> List[str]:
        """Получить возможности роли"""
        role_info = cls.get_role_info(role_key)
        return role_info.get("capabilities", [])
    
    @classmethod
    def format_prompt(cls, role_key: str, **kwargs) -> str:
        """Форматировать промпт для роли"""
        role_info = cls.get_role_info(role_key)
        template = role_info.get("prompt_template", "")
        
        # Установить значения по умолчанию
        defaults = {
            "language": "русском",
            "system_type": "SaaS-системы",
            "stack": "fullstack",
            "focus_areas": "безопасности и производительности",
            "context": ""
        }
        
        # Объединить с переданными параметрами
        format_kwargs = {**defaults, **kwargs}
        
        try:
            return template.format(**format_kwargs)
        except KeyError as e:
            return f"Ошибка форматирования промпта для роли {role_key}: {e}"
