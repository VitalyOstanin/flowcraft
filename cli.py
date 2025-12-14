#!/usr/bin/env python3
"""
FlowCraft - Мультиагентный AI CLI агент
"""

import click
import sys
from pathlib import Path

# Добавить src в путь для импортов
sys.path.insert(0, str(Path(__file__).parent / "src"))

from rich.console import Console
from core.settings import SettingsManager
from core.trust import TrustManager
from agents.manager import AgentManager
from workflows.loader import WorkflowLoader
from workflows.manager import WorkflowManager
from workflows.engine import WorkflowEngine
from workflows.llm_integration import WorkflowLLMManager
from workflows.subgraphs import get_registry
from workflows.subgraphs.common import (
    CodeAnalysisSubgraph, TestingSubgraph, SecurityReviewSubgraph,
    DeploymentSubgraph, DocumentationSubgraph
)
from core.interactive_cli import SimpleInteractiveCLI
from tools.filesystem import FileSystemTools
from tools.shell import ShellTools
from tools.search import SearchTools
from mcp.manager import MCPManager

console = Console()

@click.command()
@click.option('--config', default='~/.flowcraft/settings.yaml', help='Путь к файлу настроек')
@click.option('--debug', is_flag=True, help='Режим отладки')
def main(config, debug):
    """FlowCraft - Мультиагентный AI CLI агент"""
    try:
        console.print("Инициализация FlowCraft...", style="blue")
        
        # Инициализация базовых компонентов
        settings_manager = SettingsManager(config)
        trust_manager = TrustManager(settings_manager)
        agent_manager = AgentManager(settings_manager)
        workflow_loader = WorkflowLoader(settings_manager.settings.workflows_dir)
        mcp_manager = MCPManager(settings_manager.settings)
        
        # Инициализация LangGraph компонентов
        console.print("Инициализация LangGraph системы...", style="blue")
        
        # LLM менеджер для workflow
        llm_manager = WorkflowLLMManager(settings_manager.settings)
        
        # Workflow engine
        workflow_engine = WorkflowEngine(
            agent_manager=agent_manager,
            trust_manager=trust_manager,
            checkpoint_dir=str(Path("~/.flowcraft/checkpoints").expanduser())
        )
        
        # Workflow manager с engine
        workflow_manager = WorkflowManager(
            workflows_dir=settings_manager.settings.workflows_dir,
            workflow_engine=workflow_engine
        )
        
        # Регистрация стандартных подграфов
        console.print("Регистрация подграфов...", style="blue")
        subgraph_registry = get_registry()
        
        # Регистрируем классы подграфов
        subgraph_registry.register_subgraph_class("code_analysis", CodeAnalysisSubgraph)
        subgraph_registry.register_subgraph_class("testing", TestingSubgraph)
        subgraph_registry.register_subgraph_class("security_review", SecurityReviewSubgraph)
        subgraph_registry.register_subgraph_class("deployment", DeploymentSubgraph)
        subgraph_registry.register_subgraph_class("documentation", DocumentationSubgraph)
        
        # Создаем экземпляры стандартных подграфов
        subgraph_registry.register_subgraph(CodeAnalysisSubgraph())
        subgraph_registry.register_subgraph(TestingSubgraph())
        subgraph_registry.register_subgraph(SecurityReviewSubgraph())
        subgraph_registry.register_subgraph(DeploymentSubgraph())
        subgraph_registry.register_subgraph(DocumentationSubgraph())
        
        # Инициализация инструментов
        filesystem_tools = FileSystemTools()
        shell_tools = ShellTools(trust_manager)
        search_tools = SearchTools()
        
        if debug:
            console.print("Режим отладки включен", style="yellow")
            console.print(f"Конфигурация: {config}")
            console.print(f"Агентов загружено: {len(agent_manager.agents)}")
            console.print(f"Workflow доступно: {len(workflow_loader.list_workflows())}")
            console.print(f"MCP серверов: {len(mcp_manager.servers)}")
            console.print(f"LLM провайдеров: {len(llm_manager.get_available_models())}")
            console.print(f"Подграфов зарегистрировано: {len(subgraph_registry.list_subgraphs())}")
        
        # Запуск интерактивного CLI
        cli = SimpleInteractiveCLI(
            settings_manager, 
            agent_manager, 
            workflow_loader, 
            mcp_manager, 
            workflow_manager
        )
        cli.start()
        
    except Exception as e:
        console.print(f"Ошибка инициализации: {e}", style="red")
        if debug:
            import traceback
            console.print(traceback.format_exc())
        sys.exit(1)

if __name__ == '__main__':
    main()
