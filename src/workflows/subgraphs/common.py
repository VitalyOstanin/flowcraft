"""
Общие переиспользуемые подграфы для различных workflow.
"""

from typing import Dict, Any, List, Set
from ..nodes import BaseNode, AgentNode, ConditionalNode, create_node
from .base import BaseSubgraph


class CodeAnalysisSubgraph(BaseSubgraph):
    """Подграф для анализа кода."""
    
    def __init__(self, name: str = "code_analysis", description: str = ""):
        super().__init__(
            name, 
            description or "Анализ кода: структура, качество, потенциальные проблемы"
        )
    
    def define_nodes(self) -> Dict[str, BaseNode]:
        return {
            "analyze_structure": AgentNode(
                "analyze_structure",
                "developer",
                {
                    "description": "Анализ структуры кода и архитектуры",
                    "roles": [{"name": "developer", "prompt": "Ты архитектор. Анализируй структуру кода."}]
                },
                None  # agent_manager будет передан при выполнении
            ),
            "check_quality": AgentNode(
                "check_quality",
                "reviewer",
                {
                    "description": "Проверка качества кода и соответствия стандартам",
                    "roles": [{"name": "reviewer", "prompt": "Ты код-ревьюер. Проверяй качество кода."}]
                },
                None
            ),
            "identify_issues": AgentNode(
                "identify_issues",
                "developer",
                {
                    "description": "Выявление потенциальных проблем и багов",
                    "roles": [{"name": "developer", "prompt": "Ты эксперт по отладке. Ищи проблемы в коде."}]
                },
                None
            )
        }
    
    def define_edges(self) -> List[tuple]:
        return [
            ("analyze_structure", "check_quality"),
            ("check_quality", "identify_issues")
        ]
    
    def get_input_requirements(self) -> Set[str]:
        return {"code_path", "project_type"}
    
    def get_output_keys(self) -> Set[str]:
        return {"structure_analysis", "quality_report", "identified_issues"}


class TestingSubgraph(BaseSubgraph):
    """Подграф для тестирования."""
    
    def __init__(self, name: str = "testing", description: str = ""):
        super().__init__(
            name,
            description or "Создание и выполнение тестов"
        )
    
    def define_nodes(self) -> Dict[str, BaseNode]:
        return {
            "create_unit_tests": AgentNode(
                "create_unit_tests",
                "tester",
                {
                    "description": "Создание unit тестов",
                    "roles": [{"name": "tester", "prompt": "Ты тестировщик. Создавай unit тесты."}]
                },
                None
            ),
            "create_integration_tests": AgentNode(
                "create_integration_tests",
                "tester",
                {
                    "description": "Создание интеграционных тестов",
                    "roles": [{"name": "tester", "prompt": "Ты тестировщик. Создавай интеграционные тесты."}]
                },
                None
            ),
            "run_tests": AgentNode(
                "run_tests",
                "developer",
                {
                    "description": "Запуск тестов и анализ результатов",
                    "roles": [{"name": "developer", "prompt": "Ты разработчик. Запускай и анализируй тесты."}]
                },
                None
            )
        }
    
    def define_edges(self) -> List[tuple]:
        return [
            ("create_unit_tests", "create_integration_tests"),
            ("create_integration_tests", "run_tests")
        ]
    
    def get_input_requirements(self) -> Set[str]:
        return {"code_path", "test_framework"}
    
    def get_output_keys(self) -> Set[str]:
        return {"unit_tests", "integration_tests", "test_results"}


class SecurityReviewSubgraph(BaseSubgraph):
    """Подграф для проверки безопасности."""
    
    def __init__(self, name: str = "security_review", description: str = ""):
        super().__init__(
            name,
            description or "Анализ безопасности кода и конфигураций"
        )
    
    def define_nodes(self) -> Dict[str, BaseNode]:
        return {
            "scan_vulnerabilities": AgentNode(
                "scan_vulnerabilities",
                "security_expert",
                {
                    "description": "Сканирование уязвимостей в коде",
                    "roles": [{"name": "security_expert", "prompt": "Ты эксперт по безопасности. Ищи уязвимости."}],
                    "expensive_model": True
                },
                None
            ),
            "check_dependencies": AgentNode(
                "check_dependencies",
                "security_expert",
                {
                    "description": "Проверка безопасности зависимостей",
                    "roles": [{"name": "security_expert", "prompt": "Ты эксперт по безопасности. Проверяй зависимости."}]
                },
                None
            ),
            "review_configs": AgentNode(
                "review_configs",
                "security_expert",
                {
                    "description": "Проверка конфигураций безопасности",
                    "roles": [{"name": "security_expert", "prompt": "Ты эксперт по безопасности. Проверяй конфигурации."}]
                },
                None
            )
        }
    
    def define_edges(self) -> List[tuple]:
        return [
            ("scan_vulnerabilities", "check_dependencies"),
            ("check_dependencies", "review_configs")
        ]
    
    def get_input_requirements(self) -> Set[str]:
        return {"code_path", "config_path"}
    
    def get_output_keys(self) -> Set[str]:
        return {"vulnerability_report", "dependency_report", "config_review"}


class DeploymentSubgraph(BaseSubgraph):
    """Подграф для развертывания."""
    
    def __init__(self, name: str = "deployment", description: str = ""):
        super().__init__(
            name,
            description or "Подготовка и выполнение развертывания"
        )
    
    def define_nodes(self) -> Dict[str, BaseNode]:
        return {
            "prepare_build": AgentNode(
                "prepare_build",
                "devops",
                {
                    "description": "Подготовка сборки для развертывания",
                    "roles": [{"name": "devops", "prompt": "Ты DevOps инженер. Готовь сборку."}]
                },
                None
            ),
            "create_deployment_config": AgentNode(
                "create_deployment_config",
                "devops",
                {
                    "description": "Создание конфигурации развертывания",
                    "roles": [{"name": "devops", "prompt": "Ты DevOps инженер. Создавай конфигурации развертывания."}]
                },
                None
            ),
            "deploy": AgentNode(
                "deploy",
                "devops",
                {
                    "description": "Выполнение развертывания",
                    "roles": [{"name": "devops", "prompt": "Ты DevOps инженер. Выполняй развертывание."}]
                },
                None
            ),
            "verify_deployment": AgentNode(
                "verify_deployment",
                "tester",
                {
                    "description": "Проверка успешности развертывания",
                    "roles": [{"name": "tester", "prompt": "Ты тестировщик. Проверяй развертывание."}]
                },
                None
            )
        }
    
    def define_edges(self) -> List[tuple]:
        return [
            ("prepare_build", "create_deployment_config"),
            ("create_deployment_config", "deploy"),
            ("deploy", "verify_deployment")
        ]
    
    def define_conditional_edges(self) -> List[Dict[str, Any]]:
        def should_rollback(state):
            # Логика определения необходимости отката
            deployment_result = state["context"].stage_outputs.get("deploy", {})
            return deployment_result.get("status") == "failed"
        
        return [
            {
                "source": "verify_deployment",
                "condition": should_rollback,
                "mapping": {
                    True: "rollback",
                    False: "end"
                }
            }
        ]
    
    def get_input_requirements(self) -> Set[str]:
        return {"build_path", "target_environment"}
    
    def get_output_keys(self) -> Set[str]:
        return {"build_artifact", "deployment_config", "deployment_result", "verification_result"}


class DocumentationSubgraph(BaseSubgraph):
    """Подграф для создания документации."""
    
    def __init__(self, name: str = "documentation", description: str = ""):
        super().__init__(
            name,
            description or "Создание и обновление документации"
        )
    
    def define_nodes(self) -> Dict[str, BaseNode]:
        return {
            "analyze_code_for_docs": AgentNode(
                "analyze_code_for_docs",
                "technical_writer",
                {
                    "description": "Анализ кода для создания документации",
                    "roles": [{"name": "technical_writer", "prompt": "Ты технический писатель. Анализируй код для документации."}]
                },
                None
            ),
            "create_api_docs": AgentNode(
                "create_api_docs",
                "technical_writer",
                {
                    "description": "Создание API документации",
                    "roles": [{"name": "technical_writer", "prompt": "Ты технический писатель. Создавай API документацию."}]
                },
                None
            ),
            "create_user_guide": AgentNode(
                "create_user_guide",
                "technical_writer",
                {
                    "description": "Создание пользовательского руководства",
                    "roles": [{"name": "technical_writer", "prompt": "Ты технический писатель. Создавай пользовательские руководства."}]
                },
                None
            ),
            "update_readme": AgentNode(
                "update_readme",
                "technical_writer",
                {
                    "description": "Обновление README файла",
                    "roles": [{"name": "technical_writer", "prompt": "Ты технический писатель. Обновляй README."}]
                },
                None
            )
        }
    
    def define_edges(self) -> List[tuple]:
        return [
            ("analyze_code_for_docs", "create_api_docs"),
            ("analyze_code_for_docs", "create_user_guide"),
            ("create_api_docs", "update_readme"),
            ("create_user_guide", "update_readme")
        ]
    
    def get_input_requirements(self) -> Set[str]:
        return {"code_path", "project_info"}
    
    def get_output_keys(self) -> Set[str]:
        return {"api_documentation", "user_guide", "updated_readme"}
