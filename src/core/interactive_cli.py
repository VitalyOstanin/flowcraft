"""
Простой интерактивный CLI для FlowCraft
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from typing import Dict, Optional

console = Console()

class SimpleInteractiveCLI:
    """Простой интерактивный CLI"""
    
    def __init__(self, settings_manager, agent_manager, workflow_loader):
        self.settings_manager = settings_manager
        self.agent_manager = agent_manager
        self.workflow_loader = workflow_loader
        self.current_workflow = None
    
    def start(self):
        """Запустить интерактивную сессию"""
        console.print(Panel("Добро пожаловать в FlowCraft!", style="bold blue"))
        
        while True:
            try:
                action = self.show_main_menu()
                
                if action == "1":
                    self.start_workflow()
                elif action == "2":
                    self.manage_agents()
                elif action == "3":
                    self.show_settings()
                elif action == "4":
                    console.print("До свидания!", style="green")
                    break
                else:
                    console.print("Неверный выбор", style="red")
                    
            except KeyboardInterrupt:
                console.print("\nВыход из программы", style="yellow")
                break
            except Exception as e:
                console.print(f"Ошибка: {e}", style="red")
    
    def show_main_menu(self) -> str:
        """Показать главное меню"""
        console.print("\n" + "="*50)
        console.print("Главное меню FlowCraft", style="bold")
        console.print("1. Запустить workflow")
        console.print("2. Управление агентами")
        console.print("3. Показать настройки")
        console.print("4. Выход")
        
        return Prompt.ask("Выберите действие", choices=["1", "2", "3", "4"])
    
    def start_workflow(self):
        """Запустить workflow"""
        workflows = self.workflow_loader.list_workflows()
        
        if not workflows:
            console.print("Нет доступных workflow", style="yellow")
            return
        
        # Показать доступные workflow
        table = Table(title="Доступные Workflow")
        table.add_column("№", style="cyan")
        table.add_column("Название", style="magenta")
        table.add_column("Описание", style="green")
        
        for i, workflow_name in enumerate(workflows, 1):
            info = self.workflow_loader.get_workflow_info(workflow_name)
            description = info.get("description", "") if info else ""
            table.add_row(str(i), workflow_name, description)
        
        console.print(table)
        
        # Выбор workflow
        choice = Prompt.ask(
            "Выберите workflow", 
            choices=[str(i) for i in range(1, len(workflows) + 1)]
        )
        
        selected_workflow = workflows[int(choice) - 1]
        
        # Запрос деталей задачи
        task_id = Prompt.ask("ID задачи")
        task_description = Prompt.ask("Описание задачи")
        
        console.print(f"Запуск workflow: {selected_workflow}", style="green")
        console.print(f"Задача: {task_id} - {task_description}")
        
        # TODO: Реальный запуск workflow
        console.print("Workflow запущен (заглушка)", style="yellow")
    
    def manage_agents(self):
        """Управление агентами"""
        while True:
            console.print("\n" + "-"*30)
            console.print("Управление агентами", style="bold")
            console.print("1. Список агентов")
            console.print("2. Создать агента")
            console.print("3. Удалить агента")
            console.print("4. Назад")
            
            choice = Prompt.ask("Выберите действие", choices=["1", "2", "3", "4"])
            
            if choice == "1":
                self.list_agents()
            elif choice == "2":
                self.create_agent()
            elif choice == "3":
                self.delete_agent()
            elif choice == "4":
                break
    
    def list_agents(self):
        """Показать список агентов"""
        agents = self.agent_manager.list_agents()
        
        if not agents:
            console.print("Нет созданных агентов", style="yellow")
            return
        
        table = Table(title="Агенты")
        table.add_column("Имя", style="cyan")
        table.add_column("Роль", style="magenta")
        table.add_column("Статус", style="green")
        table.add_column("Модель", style="blue")
        
        for agent in agents:
            table.add_row(
                agent.name,
                agent.role,
                agent.status.value,
                agent.llm_model
            )
        
        console.print(table)
    
    def create_agent(self):
        """Создать нового агента"""
        console.print("Создание нового агента", style="bold")
        
        name = Prompt.ask("Имя агента")
        role = Prompt.ask("Роль агента")
        description = Prompt.ask("Описание агента")
        llm_model = Prompt.ask("LLM модель", default="qwen-code")
        
        try:
            agent = self.agent_manager.create_agent(
                name=name,
                role=role,
                description=description,
                capabilities=[],
                llm_model=llm_model
            )
            console.print(f"Агент {name} создан успешно", style="green")
        except ValueError as e:
            console.print(f"Ошибка создания агента: {e}", style="red")
    
    def delete_agent(self):
        """Удалить агента"""
        agents = self.agent_manager.list_agents()
        
        if not agents:
            console.print("Нет агентов для удаления", style="yellow")
            return
        
        console.print("Доступные агенты:")
        for i, agent in enumerate(agents, 1):
            console.print(f"{i}. {agent.name} ({agent.role})")
        
        choice = Prompt.ask(
            "Выберите агента для удаления",
            choices=[str(i) for i in range(1, len(agents) + 1)]
        )
        
        agent_to_delete = agents[int(choice) - 1]
        
        if Confirm.ask(f"Удалить агента {agent_to_delete.name}?"):
            if self.agent_manager.delete_agent(agent_to_delete.name):
                console.print(f"Агент {agent_to_delete.name} удален", style="green")
            else:
                console.print("Ошибка удаления агента", style="red")
    
    def show_settings(self):
        """Показать настройки"""
        settings = self.settings_manager.settings
        
        console.print(Panel("Текущие настройки", style="blue"))
        console.print(f"Язык: {settings.language}")
        console.print(f"Дешевая модель: {settings.llm.cheap_model}")
        console.print(f"Дорогая модель: {settings.llm.expensive_model}")
        console.print(f"Директория workflow: {settings.workflows_dir}")
        console.print(f"MCP серверов: {len(settings.mcp_servers)}")
        console.print(f"Правил доверия: {len(settings.trust_rules)}")
        console.print(f"Агентов: {len(settings.agents)}")
