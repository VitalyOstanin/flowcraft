"""
Простой интерактивный CLI для FlowCraft
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from typing import Dict, Optional
import asyncio
import os
import sys

console = Console()

class CustomPrompt(Prompt):
    """Кастомный prompt с поддержкой команды clear"""
    
    @classmethod
    def ask(cls, prompt="", *, console=None, password=False, choices=None, show_default=True, show_choices=True, default=..., stream=None):
        """Переопределенный ask с обработкой команды clear"""
        while True:
            try:
                result = super().ask(prompt, console=console, password=password, choices=choices, 
                                   show_default=show_default, show_choices=show_choices, 
                                   default=default, stream=stream)
                
                # Проверяем специальные команды
                if result == "clear" or result == "cls":
                    return "clear"
                
                return result
                
            except KeyboardInterrupt:
                raise
            except EOFError:
                raise

class SimpleInteractiveCLI:
    """Простой интерактивный CLI"""
    
    def __init__(self, settings_manager, agent_manager, workflow_loader, mcp_manager=None, workflow_manager=None):
        self.settings_manager = settings_manager
        self.agent_manager = agent_manager
        self.workflow_loader = workflow_loader
        self.workflow_manager = workflow_manager
        self.mcp_manager = mcp_manager
        self.current_workflow = None
        
        # Автоматически выбрать default workflow при запуске
        if workflow_manager:
            workflows = workflow_manager.list_workflows()
            default_workflow = next((w for w in workflows if w['name'] == 'default'), None)
            if default_workflow:
                self.current_workflow = default_workflow
        
        # Инициализация обработчика команд
        if mcp_manager:
            from .commands import CommandHandler
            self.command_handler = CommandHandler(
                settings_manager.settings,
                agent_manager,
                mcp_manager
            )
        else:
            self.command_handler = None
    
    async def direct_llm_query(self):
        """Прямой запрос к LLM без workflow"""
        console.print("\n=== Прямой запрос к LLM ===", style="bold blue")
        
        query = CustomPrompt.ask("Введите ваш запрос")
        if not query.strip():
            return
            
        try:
            from llm.qwen_code import QwenCodeProvider
            from llm.base import LLMMessage
            
            console.print("Обработка запроса...", style="yellow")
            
            qwen_provider = QwenCodeProvider()
            messages = [LLMMessage(role="user", content=query)]
            response = await qwen_provider.chat_completion(messages)
            
            console.print(f"\n{response.content}", style="green")
            
        except Exception as e:
            console.print(f"Ошибка: {e}", style="red")
        
        input("\nНажмите Enter для продолжения...")

    def show_help(self):
        """Показать справку"""
        console.print("\n=== Справка FlowCraft ===", style="bold blue")
        console.print("Доступные команды:")
        console.print("• /help - показать эту справку")
        console.print("• /clear - очистить экран")
        console.print("\nВарианты использования:")
        console.print("1. Введите задачу в поле 'Задача' для запуска workflow")
        console.print("2. Выберите пункт меню для других действий:")
        console.print("   - 1: Запустить workflow")
        console.print("   - 2: Управление агентами") 
        console.print("   - 3: Управление этапами workflow")
        console.print("   - 4: Показать настройки")
        console.print("   - 5: Прямой запрос к LLM (без workflow)")
        console.print("   - 6: Режим команд (если доступен)")
        console.print("   - 7: Выход")
        input("\nНажмите Enter для продолжения...")

    def select_workflow(self):
        """Выбрать workflow"""
        if not self.workflow_manager:
            console.print("Менеджер workflow не инициализирован", style="red")
            return
            
        workflows = self.workflow_manager.list_workflows()
        if not workflows:
            console.print("Нет доступных workflow", style="yellow")
            return
            
        console.print("\n=== Выбор Workflow ===", style="bold blue")
        table = Table(title="Доступные Workflow")
        table.add_column("№", style="cyan")
        table.add_column("Название", style="magenta")
        table.add_column("Описание", style="green")
        table.add_column("Текущий", style="yellow")
        
        for i, workflow in enumerate(workflows, 1):
            current_mark = "✓" if self.current_workflow and workflow['name'] == self.current_workflow['name'] else ""
            table.add_row(str(i), workflow['name'], workflow['description'], current_mark)
        
        console.print(table)
        
        try:
            choice = CustomPrompt.ask("Выберите workflow (номер)", choices=[str(i) for i in range(1, len(workflows) + 1)])
            selected_workflow = workflows[int(choice) - 1]
            self.current_workflow = selected_workflow
            console.print(f"Выбран workflow: [bold green]{selected_workflow['name']}[/bold green]")
        except (ValueError, IndexError):
            console.print("Неверный выбор", style="red")

    def clear_screen(self):
        """Очистить экран"""
        os.system('clear' if os.name == 'posix' else 'cls')
        console.clear()
    
    def start(self):
        """Запустить интерактивную сессию"""        
        console.print("Введите '/help' для справки", style="dim")
        
        while True:
            try:
                action = self.show_main_menu()
                
                if action == "clear":
                    self.clear_screen()
                    continue
                elif action == "task_processed" or action == "help_shown":
                    continue  # Задача обработана или справка показана, показать меню снова
                elif action == "1":
                    self.start_workflow()
                elif action == "2":
                    self.select_workflow()
                elif action == "3":
                    self.manage_agents()
                elif action == "4":
                    self.manage_workflow_stages()
                elif action == "5":
                    self.show_settings()
                elif action == "6":
                    asyncio.run(self.direct_llm_query())
                elif action == "7":
                    if self.command_handler:
                        asyncio.run(self.command_mode())
                    else:
                        console.print("До свидания!", style="green")
                        break
                elif action == "8":
                    console.print("До свидания!", style="green")
                    break
                elif action == "clear":
                    self.clear_screen()
                    continue
                else:
                    console.print("Неверный выбор", style="red")
                    
            except KeyboardInterrupt:
                console.print("\nВыход из программы", style="yellow")
                break
            except EOFError:
                # Ctrl-D
                console.print("\nВыход из программы", style="yellow")
                break
            except Exception as e:
                console.print(f"Ошибка: {e}", style="red")
    
    def show_main_menu(self) -> str:
        """Показать главное меню с доступными workflow и полем ввода задачи"""
        console.print("\n" + "="*50)
        
        # Показать текущий выбранный workflow
        if self.current_workflow:
            console.print(f"Текущий workflow: [bold green]{self.current_workflow['name']}[/bold green] - {self.current_workflow['description']}")
        else:
            console.print("Workflow не выбран", style="yellow")
        
        # Показать доступные workflow сразу
        if self.workflow_manager:
            workflows = self.workflow_manager.list_workflows()
            if workflows:
                table = Table(title="Доступные Workflow")
                table.add_column("№", style="cyan")
                table.add_column("Название", style="magenta")
                table.add_column("Описание", style="green")
                
                for i, workflow in enumerate(workflows, 1):
                    table.add_row(str(i), workflow['name'], workflow['description'])
                
                console.print(table)
            else:
                console.print("Нет доступных workflow", style="yellow")
        
        # Поле ввода задачи
        console.print("\nОпишите вашу задачу:", style="bold")
        task_input = CustomPrompt.ask("Задача", default="")
        
        if task_input == "clear":
            self.clear_screen()
            return "clear"
        
        if task_input.strip():
            # Проверить команды
            if task_input.strip() == "/help":
                self.show_help()
                return "help_shown"
            elif task_input.strip() == "/clear":
                self.clear_screen()
                return "clear"
            
            # Обработать задачу
            asyncio.run(self.process_task(task_input.strip()))
            return "task_processed"
        
        console.print("\nГлавное меню FlowCraft", style="bold")
        console.print("1. Запустить workflow")
        console.print("2. Сменить workflow")
        console.print("3. Управление агентами")
        console.print("4. Управление этапами workflow")
        console.print("5. Показать настройки")
        console.print("6. Прямой запрос к LLM")
        console.print("clear. Очистить экран")
        if self.command_handler:
            console.print("7. Режим команд")
            console.print("8. Выход")
            return CustomPrompt.ask("Выберите действие", choices=["1", "2", "3", "4", "5", "6", "7", "8", "clear"])
        else:
            console.print("7. Выход")
            return CustomPrompt.ask("Выберите действие", choices=["1", "2", "3", "4", "5", "6", "7", "clear"])
    
    async def process_task(self, task_description: str):
        """Обработать задачу пользователя с автоматическим выбором workflow"""
        if not self.workflow_manager:
            console.print("Менеджер workflow не инициализирован", style="red")
            return
            
        workflows = self.workflow_manager.list_workflows()
        selected_workflow = None
        
        # Использовать текущий выбранный workflow
        if self.current_workflow:
            selected_workflow = self.current_workflow['name']
            console.print(f"Использование режима {selected_workflow} workflow")
        
        # Попытка выбора через LLM если есть workflow и не выбран текущий
        if workflows:
            try:
                from llm.qwen_code import QwenCodeProvider
                llm_provider = QwenCodeProvider()
                
                selected_workflow = self.workflow_manager.select_workflow_by_description(task_description, llm_provider)
                
                if selected_workflow:
                    workflow_info = next((w for w in workflows if w['name'] == selected_workflow), None)
                    if workflow_info:
                        console.print(f"\nПредлагаемый workflow: [bold]{selected_workflow}[/bold]")
                        console.print(f"Описание: {workflow_info['description']}")
                        
                        if not Confirm.ask("Подтвердить выбор?"):
                            selected_workflow = None
                            
            except Exception as e:
                console.print(f"Ошибка при автоматическом выборе: {e}", style="yellow")
        
        # Если не выбран workflow, использовать default режим
        if not selected_workflow:
            console.print("Использование режима default workflow", style="cyan")
            selected_workflow = "default"
        
        # Запрос ID задачи
        task_id = CustomPrompt.ask("ID задачи", default="auto")
        
        console.print(f"Запуск workflow: [bold]{selected_workflow}[/bold]", style="green")
        console.print(f"Задача: {task_id} - {task_description}")
        
        # Реальный запуск workflow через LangGraph
        try:
            result = await self.workflow_manager.execute_workflow(
                workflow_name=selected_workflow,
                task_description=task_description,
                thread_id=task_id if task_id != "auto" else None
            )
            
            if result.get("success", False):
                console.print("Workflow завершен успешно!", style="green")
                
                # Показываем результаты
                completed = result.get("completed_stages", [])
                if completed:
                    console.print(f"Завершенные этапы: {', '.join(completed)}")
                
            else:
                console.print("Workflow завершен с ошибками", style="red")
                error = result.get("error", "Неизвестная ошибка")
                console.print(f"Ошибка: {error}")
                
                failed = result.get("failed_stages", [])
                if failed:
                    console.print(f"Неуспешные этапы: {', '.join(failed)}")
        
        except Exception as e:
            console.print(f"Критическая ошибка: {str(e)}", style="red")

    async def command_mode(self):
        """Режим команд"""
        console.print(Panel("Режим команд (введите 'exit' для выхода)", style="cyan"))
        console.print("Введите /help для справки", style="dim")
        
        while True:
            try:
                command = CustomPrompt.ask("[bold cyan]>[/bold cyan]", default="")
                
                if command.lower() in ["exit", "quit", "q"]:
                    break
                
                if command.startswith("/"):
                    result = await self.command_handler.handle_command(command)
                    console.print(result)
                else:
                    console.print("Команды должны начинаться с '/'", style="yellow")
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                console.print(f"Ошибка выполнения команды: {e}", style="red")
    
    def start_workflow(self):
        """Запустить workflow с выбором через естественный язык"""
        if not self.workflow_manager:
            console.print("Менеджер workflow не инициализирован", style="red")
            return
            
        workflows = self.workflow_manager.list_workflows()
        
        if not workflows:
            console.print("Нет доступных workflow", style="yellow")
            return
        
        # Запрос описания задачи от пользователя
        user_input = CustomPrompt.ask("Опишите что вы хотите сделать")
        
        # Попытка выбора через LLM
        try:
            from llm.qwen_code import QwenCodeProvider
            llm_provider = QwenCodeProvider()
            
            selected_workflow = self.workflow_manager.select_workflow_by_description(user_input, llm_provider)
            
            if selected_workflow:
                # Подтверждение выбора
                workflow_info = next((w for w in workflows if w['name'] == selected_workflow), None)
                if workflow_info:
                    console.print(f"\nПредлагаемый workflow: [bold]{selected_workflow}[/bold]")
                    console.print(f"Описание: {workflow_info['description']}")
                    
                    if Confirm.ask("Подтвердить выбор?"):
                        # Запрос ID задачи
                        task_id = CustomPrompt.ask("ID задачи")
                        
                        console.print(f"Запуск workflow: {selected_workflow}", style="green")
                        console.print(f"Задача: {task_id} - {user_input}")
                        
                        # TODO: Реальный запуск workflow
                        console.print("Workflow запущен (заглушка)", style="yellow")
                        return
            
            # Если LLM не смог выбрать, показать ручной выбор
            console.print("Не удалось автоматически выбрать workflow. Выберите вручную:", style="yellow")
            
        except Exception as e:
            console.print(f"Ошибка при автоматическом выборе: {e}", style="yellow")
            console.print("Выберите workflow вручную:")
        
        # Ручной выбор
        for i, workflow in enumerate(workflows, 1):
            console.print(f"{i}. {workflow['name']}: {workflow['description']}")
        
        choice = CustomPrompt.ask(
            "Выберите workflow", 
            choices=[str(i) for i in range(1, len(workflows) + 1)]
        )
        
        selected_workflow = workflows[int(choice) - 1]['name']
        task_id = CustomPrompt.ask("ID задачи")
        
        console.print(f"Запуск workflow: {selected_workflow}", style="green")
        console.print(f"Задача: {task_id} - {user_input}")
        
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
            
            choice = CustomPrompt.ask("Выберите действие", choices=["1", "2", "3", "4"])
            
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
        table.add_column("Описание", style="green")
        
        for agent in agents:
            table.add_row(
                agent.get("name", ""),
                agent.get("role", ""),
                agent.get("description", "")
            )
        
        console.print(table)
    
    def create_agent(self):
        """Создать нового агента"""
        name = CustomPrompt.ask("Имя агента")
        role = CustomPrompt.ask("Роль агента")
        description = CustomPrompt.ask("Описание агента")
        
        try:
            self.agent_manager.create_agent(name, role, description)
            console.print(f"Агент '{name}' создан", style="green")
        except Exception as e:
            console.print(f"Ошибка создания агента: {e}", style="red")
    
    def delete_agent(self):
        """Удалить агента"""
        agents = self.agent_manager.list_agents()
        
        if not agents:
            console.print("Нет агентов для удаления", style="yellow")
            return
        
        # Показать список для выбора
        for i, agent in enumerate(agents, 1):
            console.print(f"{i}. {agent.get('name', '')}")
        
        choice = CustomPrompt.ask(
            "Выберите агента для удаления",
            choices=[str(i) for i in range(1, len(agents) + 1)]
        )
        
        agent_name = agents[int(choice) - 1].get("name", "")
        
        if Confirm.ask(f"Удалить агента '{agent_name}'?"):
            try:
                self.agent_manager.delete_agent(agent_name)
                console.print(f"Агент '{agent_name}' удален", style="green")
            except Exception as e:
                console.print(f"Ошибка удаления агента: {e}", style="red")
    
    def manage_workflow_stages(self):
        """Управление этапами workflow"""
        if not self.workflow_manager:
            console.print("Менеджер workflow не инициализирован", style="red")
            return
        
        while True:
            console.print("\n" + "-"*30)
            console.print("Управление этапами workflow", style="bold")
            console.print("1. Выбрать workflow")
            console.print("2. Список этапов")
            console.print("3. Создать этап")
            console.print("4. Обновить этап")
            console.print("5. Удалить этап")
            console.print("6. Включить/отключить этап")
            console.print("7. Выполнить команду")
            console.print("8. Назад")
            
            choice = CustomPrompt.ask("Выберите действие", choices=["1", "2", "3", "4", "5", "6", "7", "8"])
            
            if choice == "1":
                self._select_workflow_for_stages()
            elif choice == "2":
                self._list_workflow_stages()
            elif choice == "3":
                self._create_workflow_stage()
            elif choice == "4":
                self._update_workflow_stage()
            elif choice == "5":
                self._delete_workflow_stage()
            elif choice == "6":
                self._toggle_workflow_stage()
            elif choice == "7":
                self._execute_stage_command()
            elif choice == "8":
                break
    
    def _select_workflow_for_stages(self):
        """Выбрать workflow для управления этапами"""
        workflows = self.workflow_manager.list_workflows()
        if not workflows:
            console.print("Нет доступных workflow", style="yellow")
            return
        
        table = Table(title="Доступные Workflow")
        table.add_column("№", style="cyan")
        table.add_column("Название", style="magenta")
        table.add_column("Описание", style="green")
        
        for i, workflow in enumerate(workflows, 1):
            table.add_row(str(i), workflow['name'], workflow['description'])
        
        console.print(table)
        
        try:
            choice = int(CustomPrompt.ask("Выберите workflow (номер)")) - 1
            if 0 <= choice < len(workflows):
                self.current_workflow = workflows[choice]['name']
                console.print(f"Выбран workflow: {self.current_workflow}", style="green")
            else:
                console.print("Неверный номер", style="red")
        except ValueError:
            console.print("Введите число", style="red")
    
    def _list_workflow_stages(self):
        """Показать список этапов текущего workflow"""
        if not self.current_workflow:
            console.print("Сначала выберите workflow", style="yellow")
            return
        
        try:
            stages = self.workflow_manager.list_workflow_stages(self.current_workflow)
            
            if not stages:
                console.print("Нет этапов в workflow", style="yellow")
                return
            
            table = Table(title=f"Этапы workflow '{self.current_workflow}'")
            table.add_column("Название", style="cyan")
            table.add_column("Описание", style="green")
            table.add_column("Роли", style="magenta")
            table.add_column("Статус", style="yellow")
            
            for stage in stages:
                status = "✓ Включен" if stage.enabled else "✗ Отключен"
                roles_str = ", ".join(stage.roles)
                table.add_row(stage.name, stage.description, roles_str, status)
            
            console.print(table)
            
        except Exception as e:
            console.print(f"Ошибка получения этапов: {e}", style="red")
    
    def _create_workflow_stage(self):
        """Создать новый этап"""
        if not self.current_workflow:
            console.print("Сначала выберите workflow", style="yellow")
            return
        
        try:
            from workflows.stage_manager import WorkflowStage
            
            name = CustomPrompt.ask("Название этапа")
            description = CustomPrompt.ask("Описание этапа")
            roles_input = CustomPrompt.ask("Роли (через запятую)")
            roles = [role.strip() for role in roles_input.split(",") if role.strip()]
            skippable = Confirm.ask("Этап можно пропустить?", default=False)
            
            stage = WorkflowStage(
                name=name,
                description=description,
                roles=roles,
                skippable=skippable
            )
            
            self.workflow_manager.create_workflow_stage(self.current_workflow, stage)
            console.print(f"Этап '{name}' создан", style="green")
            
        except Exception as e:
            console.print(f"Ошибка создания этапа: {e}", style="red")
    
    def _update_workflow_stage(self):
        """Обновить этап"""
        if not self.current_workflow:
            console.print("Сначала выберите workflow", style="yellow")
            return
        
        try:
            stage_name = CustomPrompt.ask("Название этапа для обновления")
            
            # Получить текущий этап
            current_stage = self.workflow_manager.get_workflow_stage(self.current_workflow, stage_name)
            if not current_stage:
                console.print("Этап не найден", style="red")
                return
            
            console.print(f"Текущие значения для этапа '{stage_name}':")
            console.print(f"Описание: {current_stage.description}")
            console.print(f"Роли: {', '.join(current_stage.roles)}")
            console.print(f"Можно пропустить: {current_stage.skippable}")
            
            updates = {}
            
            new_description = CustomPrompt.ask("Новое описание (Enter - оставить текущее)", default="")
            if new_description:
                updates['description'] = new_description
            
            new_roles_input = CustomPrompt.ask("Новые роли через запятую (Enter - оставить текущие)", default="")
            if new_roles_input:
                updates['roles'] = [role.strip() for role in new_roles_input.split(",") if role.strip()]
            
            if Confirm.ask("Изменить настройку 'можно пропустить'?", default=False):
                updates['skippable'] = Confirm.ask("Этап можно пропустить?", default=current_stage.skippable)
            
            if updates:
                self.workflow_manager.update_workflow_stage(self.current_workflow, stage_name, updates)
                console.print(f"Этап '{stage_name}' обновлен", style="green")
            else:
                console.print("Изменения не внесены", style="yellow")
                
        except Exception as e:
            console.print(f"Ошибка обновления этапа: {e}", style="red")
    
    def _delete_workflow_stage(self):
        """Удалить этап"""
        if not self.current_workflow:
            console.print("Сначала выберите workflow", style="yellow")
            return
        
        stage_name = CustomPrompt.ask("Название этапа для удаления")
        
        if Confirm.ask(f"Удалить этап '{stage_name}'?"):
            try:
                self.workflow_manager.delete_workflow_stage(self.current_workflow, stage_name)
                console.print(f"Этап '{stage_name}' удален", style="green")
            except Exception as e:
                console.print(f"Ошибка удаления этапа: {e}", style="red")
    
    def _toggle_workflow_stage(self):
        """Включить/отключить этап"""
        if not self.current_workflow:
            console.print("Сначала выберите workflow", style="yellow")
            return
        
        try:
            stage_name = CustomPrompt.ask("Название этапа")
            
            # Получить текущий статус
            stage = self.workflow_manager.get_workflow_stage(self.current_workflow, stage_name)
            if not stage:
                console.print("Этап не найден", style="red")
                return
            
            current_status = "включен" if stage.enabled else "отключен"
            new_action = "отключить" if stage.enabled else "включить"
            
            console.print(f"Этап '{stage_name}' сейчас {current_status}")
            
            if Confirm.ask(f"{new_action.capitalize()} этап?"):
                if stage.enabled:
                    self.workflow_manager.disable_workflow_stage(self.current_workflow, stage_name)
                    console.print(f"Этап '{stage_name}' отключен", style="green")
                else:
                    self.workflow_manager.enable_workflow_stage(self.current_workflow, stage_name)
                    console.print(f"Этап '{stage_name}' включен", style="green")
                    
        except Exception as e:
            console.print(f"Ошибка изменения статуса этапа: {e}", style="red")
    
    def _execute_stage_command(self):
        """Выполнить команду управления этапами"""
        if not self.current_workflow:
            console.print("Сначала выберите workflow", style="yellow")
            return
        
        console.print("\nПримеры команд:")
        console.print("list_stages")
        console.print("create_stage name='test' description='Test stage' roles=['developer']")
        console.print("update_stage name='test' description='Updated description'")
        console.print("delete_stage name='test'")
        console.print("enable_stage name='test'")
        console.print("disable_stage name='test'")
        
        command = CustomPrompt.ask("Введите команду")
        
        def confirm_callback(message):
            return Confirm.ask(message)
        
        try:
            result = self.workflow_manager.process_stage_command(
                command, 
                self.current_workflow, 
                confirm_callback
            )
            
            if result['success']:
                console.print(result['message'], style="green")
                if 'data' in result:
                    console.print(f"Данные: {result['data']}")
            else:
                console.print(result['message'], style="red")
                
        except Exception as e:
            console.print(f"Ошибка выполнения команды: {e}", style="red")
    
    def show_settings(self):
        """Показать настройки"""
        settings = self.settings_manager.settings
        
        console.print("\n" + "="*30)
        console.print("Настройки FlowCraft", style="bold")
        console.print(f"Язык: {settings.language}")
        console.print(f"Дешевая модель: {settings.llm.cheap_model}")
        console.print(f"Дорогая модель: {settings.llm.expensive_model}")
        console.print(f"Каталог workflow: {settings.workflows_dir}")
        console.print(f"MCP серверов: {len(settings.mcp_servers)}")
        console.print(f"Агентов: {len(self.agent_manager.agents)}")
