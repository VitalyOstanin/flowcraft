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
import termios
import tty

def getch():
    """Получить один символ без нажатия Enter"""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
        if ch == '\x1b':  # ESC
            return ch
        # Для цифр возвращаем сразу
        if ch.isdigit():
            sys.stdout.write(ch + '\n')
            sys.stdout.flush()
            return ch
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

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
        console.print("• /menu - показать меню управления")
        console.print("\nИспользование:")
        console.print("1. Введите задачу для выполнения через LLM или workflow")
        console.print("2. Нажмите Enter без ввода для показа меню")
        console.print("3. Используйте Ctrl+C для выхода")
        console.print("4. ESC для прерывания выполнения workflow")

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
            choice = input(f"\nВыберите workflow (номер 1-{len(workflows)}): ").strip()
            if not choice.isdigit() or not (1 <= int(choice) <= len(workflows)):
                console.print("Неверный выбор", style="red")
                return
            selected_workflow = workflows[int(choice) - 1]
            self.current_workflow = selected_workflow
            console.print(f"Выбран workflow: [bold green]{selected_workflow['name']}[/bold green]")
        except (ValueError, IndexError, KeyboardInterrupt):
            console.print("Неверный выбор", style="red")

    def clear_screen(self):
        """Очистить экран"""
        os.system('clear' if os.name == 'posix' else 'cls')
        console.clear()
    
    async def start(self):
        """Запустить интерактивную сессию"""        
        console.print("Введите '/help' для справки", style="dim")
        
        # Показать текущий workflow
        if self.current_workflow:
            console.print(f"Использование режима {self.current_workflow['name']} workflow", style="cyan")
        
        while True:
            try:
                # Основной цикл - ввод задачи
                console.print("\nОпишите вашу задачу:", style="bold")
                task_input = input("Задача: ")
                
                if task_input == "clear":
                    self.clear_screen()
                    continue
                
                if task_input.strip():
                    # Проверить команды
                    if task_input.strip() == "/help":
                        self.show_help()
                        continue
                    elif task_input.strip() == "/clear":
                        self.clear_screen()
                        continue
                    elif task_input.strip() == "/menu":
                        action = await self.show_menu()
                        if action == "exit":
                            break
                        continue
                    
                    # Обработать задачу
                    await self.process_task_with_workflow(task_input.strip())
                else:
                    # Если пустой ввод, показать меню
                    action = await self.show_menu()
                    if action == "exit":
                        break
                    
            except EOFError:
                console.print("\nВыход из программы", style="yellow")
                break
            except Exception as e:
                console.print(f"Ошибка: {e}", style="red")
    
    async def process_task_with_workflow(self, task: str):
        """Обработать задачу с использованием workflow или прямого LLM"""
        try:
            if self.current_workflow and self.current_workflow['name'] != 'default':
                # Спросить подтверждение для смены workflow
                console.print(f"Текущий workflow: {self.current_workflow['name']}")
                if not Confirm.ask("Продолжить с текущим workflow?"):
                    self.select_workflow()
                    if not self.current_workflow:
                        return
            
            if self.current_workflow and self.current_workflow['name'] == 'default':
                # Для default workflow - прямой запрос к LLM
                await self.direct_llm_execution(task)
            else:
                # Запуск полного workflow
                await self.execute_workflow(task)
                
        except KeyboardInterrupt:
            console.print("\nВыполнение прервано пользователем", style="yellow")
        except Exception as e:
            console.print(f"Ошибка выполнения: {e}", style="red")
    
    async def direct_llm_execution(self, task: str):
        """Прямое выполнение через LLM без workflow"""
        console.print("Обработка запроса...", style="yellow")
        
        try:
            from llm.qwen_code import QwenCodeProvider
            from llm.base import LLMMessage
            
            qwen_provider = QwenCodeProvider()
            
            # Создаем system prompt с языковой настройкой
            language = self.settings_manager.settings.language
            system_prompt = f"Отвечай на {language} языке." if language == "ru" else f"Respond in {language}."
            
            messages = [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=task)
            ]
            response = await qwen_provider.chat_completion(messages)
            
            console.print(f"\n{response.content}", style="green")
            
        except Exception as e:
            console.print(f"Ошибка LLM: {e}", style="red")
    
    async def execute_workflow(self, task: str):
        """Выполнить полный workflow"""
        if not self.workflow_manager:
            console.print("Менеджер workflow не инициализирован", style="red")
            return
            
        workflow_name = self.current_workflow['name']
        console.print(f"Запуск workflow: {workflow_name}", style="cyan")
        
        try:
            # Выполняем workflow через менеджер
            result = await self.workflow_manager.execute_workflow(
                workflow_name=workflow_name,
                task_description=task
            )
            
            # Обрабатываем результат
            if result.get("success", False):
                console.print("✓ Workflow выполнен успешно", style="green")
                
                completed = result.get("completed_stages", [])
                if completed:
                    console.print(f"Выполнено этапов: {len(completed)}", style="green")
                    for stage in completed:
                        console.print(f"  ✓ {stage}", style="dim green")
                
                # Показываем результат если есть
                workflow_result = result.get("result")
                if workflow_result:
                    console.print("\nРезультат workflow:", style="bold")
                    console.print(workflow_result)
                    
            else:
                console.print("✗ Ошибка выполнения workflow", style="red")
                error = result.get("error", "Неизвестная ошибка")
                console.print(f"Ошибка: {error}", style="red")
                
                failed = result.get("failed_stages", [])
                if failed:
                    console.print(f"Неудачные этапы: {len(failed)}", style="red")
                    for stage in failed:
                        console.print(f"  ✗ {stage}", style="dim red")
                        
        except Exception as e:
            console.print(f"✗ Критическая ошибка: {str(e)}", style="red")
    
    async def show_menu(self) -> str:
        """Показать меню управления"""
        console.print("\n=== Меню FlowCraft ===", style="bold blue")
        console.print("1. Сменить workflow")
        console.print("2. Управление workflow")
        console.print("3. Управление агентами")
        console.print("4. Управление MCP серверами")
        console.print("5. Показать настройки")
        console.print("6. Выход")
        console.print("ESC. Вернуться к вводу задач")
        
        try:
            sys.stdout.write("Выберите действие [1/2/3/4/5/6]: ")
            sys.stdout.flush()
            choice = getch()
            
            # Проверка на ESC
            if choice == '\x1b':
                console.print("\nВозврат к основному меню...", style="dim")
                return "continue"
                
            choice = choice.strip()
            if choice not in ["1", "2", "3", "4", "5", "6"]:
                console.print("\nНеверный выбор", style="red")
                return "continue"
        except KeyboardInterrupt:
            # Ctrl+C - возврат к основному циклу
            console.print("\nВозврат к основному меню...", style="dim")
            return "continue"
        except Exception as e:
            console.print(f"\nОшибка ввода: {e}", style="red")
            return "continue"
        
        if choice == "1":
            self.select_workflow()
        elif choice == "2":
            self.manage_workflows()
        elif choice == "3":
            self.manage_agents()
        elif choice == "4":
            await self.manage_mcp_servers()
        elif choice == "5":
            self.show_settings()
        elif choice == "6":
            return "exit"
        
    async def manage_mcp_servers(self):
        """Управление MCP серверами"""
        while True:
            console.print("\n=== Управление MCP серверами ===", style="bold blue")
            
            # Показать текущие серверы
            servers = self.settings_manager.settings.mcp_servers
            if servers:
                table = Table(title="MCP Серверы")
                table.add_column("Название", style="cyan")
                table.add_column("Команда", style="green")
                table.add_column("Статус", style="yellow")
                
                for server in servers:
                    status = "Отключен" if server.disabled else "Включен"
                    table.add_row(server.name, server.command, status)
                
                console.print(table)
            else:
                console.print("MCP серверы не настроены", style="yellow")
            
            console.print("\n1. Добавить MCP сервер")
            console.print("2. Удалить MCP сервер")
            console.print("3. Включить/отключить MCP сервер")
            console.print("4. Перезапустить MCP сервер")
            console.print("5. Назад")
            
            choice = CustomPrompt.ask("Выберите действие", choices=["1", "2", "3", "4", "5"])
            
            if choice == "1":
                self._add_mcp_server()
            elif choice == "2":
                self._remove_mcp_server()
            elif choice == "3":
                self._toggle_mcp_server()
            elif choice == "4":
                await self._restart_mcp_server()
            elif choice == "5":
                break

    def _add_mcp_server(self):
        """Добавить MCP сервер"""
        console.print("\n=== Добавление MCP сервера ===", style="bold green")
        
        name = CustomPrompt.ask("Название сервера")
        if not name:
            return
        
        command = CustomPrompt.ask("Команда запуска")
        if not command:
            return
        
        args_input = CustomPrompt.ask("Аргументы (через пробел)", default="")
        args = args_input.split() if args_input else []
        
        env = {}
        console.print("Переменные окружения (пустое название для завершения):")
        while True:
            env_name = CustomPrompt.ask("Название переменной", default="")
            if not env_name:
                break
            env_value = CustomPrompt.ask(f"Значение для {env_name}")
            env[env_name] = env_value
        
        try:
            self.settings_manager.add_mcp_server(name, command, args, env)
            console.print(f"MCP сервер '{name}' добавлен", style="green")
        except Exception as e:
            console.print(f"Ошибка добавления сервера: {e}", style="red")

    def _remove_mcp_server(self):
        """Удалить MCP сервер"""
        servers = self.settings_manager.settings.mcp_servers
        if not servers:
            console.print("Нет серверов для удаления", style="yellow")
            return
        
        server_names = [s.name for s in servers]
        name = CustomPrompt.ask("Название сервера для удаления", choices=server_names)
        
        if self.settings_manager.remove_mcp_server(name):
            console.print(f"MCP сервер '{name}' удален", style="green")
        else:
            console.print(f"Ошибка удаления сервера '{name}'", style="red")

    def _toggle_mcp_server(self):
        """Включить/отключить MCP сервер"""
        servers = self.settings_manager.settings.mcp_servers
        if not servers:
            console.print("Нет серверов для управления", style="yellow")
            return
        
        server_names = [s.name for s in servers]
        name = CustomPrompt.ask("Название сервера", choices=server_names)
        
        # Найти сервер и переключить статус
        for server in servers:
            if server.name == name:
                server.disabled = not server.disabled
                status = "отключен" if server.disabled else "включен"
                console.print(f"MCP сервер '{name}' {status}", style="green")
                self.settings_manager._save_mcp_servers()
                break

    async def _restart_mcp_server(self):
        """Перезапустить MCP сервер"""
        if not self.mcp_manager:
            console.print("MCP менеджер недоступен", style="red")
            return
        
        servers = self.settings_manager.settings.mcp_servers
        active_servers = [s.name for s in servers if not s.disabled]
        
        if not active_servers:
            console.print("Нет активных серверов для перезапуска", style="yellow")
            return
        
        name = CustomPrompt.ask("Название сервера для перезапуска", choices=active_servers)
        
        try:
            # Остановить сервер если запущен
            if name in self.mcp_manager.active_servers:
                self.mcp_manager.active_servers[name].stop()
                del self.mcp_manager.active_servers[name]
            
            # Запустить заново
            if await self.mcp_manager.start_server(name):
                console.print(f"MCP сервер '{name}' перезапущен", style="green")
            else:
                console.print(f"Ошибка перезапуска сервера '{name}'", style="red")
        except Exception as e:
            console.print(f"Ошибка перезапуска: {e}", style="red")

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
    
    def manage_workflows(self):
        """Управление workflow"""
        while True:
            console.print("\n=== Управление Workflow ===", style="bold blue")
            console.print("1. Создать workflow")
            console.print("2. Список workflow")
            console.print("3. Удалить workflow")
            console.print("4. Управление этапами workflow")
            console.print("5. Назад")
            
            choice = input("Выберите действие [1/2/3/4/5]: ").strip()
            
            if choice not in ["1", "2", "3", "4", "5"]:
                console.print("Неверный выбор", style="red")
                continue
                
            if choice == "1":
                self.create_workflow()
            elif choice == "2":
                self.list_workflows()
            elif choice == "3":
                self.delete_workflow()
            elif choice == "4":
                self.manage_workflow_stages()
            elif choice == "5":
                break

    def create_workflow(self):
        """Создать новый workflow"""
        try:
            # Предложить создание через LLM
            use_llm = Confirm.ask("Создать workflow с помощью LLM?", default=True)
            
            if use_llm:
                asyncio.run(self._create_workflow_with_llm())
            else:
                self._create_workflow_manual()
                
        except Exception as e:
            console.print(f"Ошибка создания workflow: {e}", style="red")
    
    def _create_workflow_manual(self):
        """Ручное создание workflow"""
        name = CustomPrompt.ask("Название workflow")
        if not name:
            console.print("Название не может быть пустым", style="red")
            return
            
        description = CustomPrompt.ask("Описание workflow")
        
        # Базовая конфигурация с минимальным stage
        config = {
            'roles': [
                {
                    'name': 'developer',
                    'prompt': 'Ты разработчик. Отвечай на русском.',
                    'expensive_model': False
                }
            ],
            'stages': [
                {
                    'name': 'initial_stage',
                    'roles': ['developer'],
                    'skippable': False,
                    'description': 'Начальный этап workflow'
                }
            ]
        }
        
        # Создаем workflow
        if self.workflow_manager.create_workflow(name, description, config):
            console.print(f"Workflow '{name}' создан", style="green")
        else:
            console.print(f"Workflow '{name}' уже существует", style="red")
    
    async def _create_workflow_with_llm(self):
        """Создание workflow с помощью LLM"""
        try:
            from llm.qwen_code import QwenCodeProvider
            from llm.base import LLMMessage
            
            # Запрос описания от пользователя
            user_description = CustomPrompt.ask("Опишите какой workflow вы хотите создать")
            if not user_description:
                console.print("Описание не может быть пустым", style="red")
                return
            
            console.print("Генерация workflow через LLM...", style="yellow")
            
            # LLM промпт для создания workflow
            prompt = f"""Создай конфигурацию workflow на основе описания пользователя: "{user_description}"

Верни JSON в следующем формате:
{{
    "name": "краткое_название_workflow",
    "description": "подробное описание workflow",
    "roles": [
        {{
            "name": "имя_роли",
            "prompt": "промпт для роли на русском языке",
            "expensive_model": false
        }}
    ],
    "stages": [
        {{
            "name": "название_этапа",
            "roles": ["имя_роли"],
            "skippable": false,
            "description": "описание этапа"
        }}
    ]
}}

Создай минимум 2-3 этапа и 1-2 роли. Все тексты на русском языке."""

            llm_provider = QwenCodeProvider()
            messages = [LLMMessage(role="user", content=prompt)]
            response = await llm_provider.chat_completion(messages)
            
            # Парсим ответ LLM
            import json
            try:
                # Извлекаем JSON из ответа
                response_text = response.content.strip()
                if "```json" in response_text:
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.find("```", json_start)
                    json_text = response_text[json_start:json_end].strip()
                else:
                    json_text = response_text
                
                workflow_config = json.loads(json_text)
                
                # Показываем предложенную конфигурацию
                console.print("\n=== Предложенный workflow ===", style="bold blue")
                console.print(f"Название: {workflow_config['name']}")
                console.print(f"Описание: {workflow_config['description']}")
                console.print(f"Ролей: {len(workflow_config.get('roles', []))}")
                console.print(f"Этапов: {len(workflow_config.get('stages', []))}")
                
                # Показываем детали
                console.print("\nРоли:")
                for role in workflow_config.get('roles', []):
                    console.print(f"  - {role['name']}: {role.get('prompt', '')[:50]}...")
                
                console.print("\nЭтапы:")
                for stage in workflow_config.get('stages', []):
                    console.print(f"  - {stage['name']}: {stage.get('description', '')}")
                
                # Запрашиваем подтверждение
                if Confirm.ask("\nСоздать этот workflow?"):
                    name = workflow_config['name']
                    description = workflow_config['description']
                    config = {
                        'roles': workflow_config.get('roles', []),
                        'stages': workflow_config.get('stages', [])
                    }
                    
                    if self.workflow_manager.create_workflow(name, description, config):
                        console.print(f"Workflow '{name}' создан", style="green")
                    else:
                        console.print(f"Workflow '{name}' уже существует", style="red")
                else:
                    console.print("Создание отменено", style="yellow")
                    
            except json.JSONDecodeError:
                console.print("Ошибка парсинга ответа LLM. Попробуйте ручное создание.", style="red")
                
        except Exception as e:
            console.print(f"Ошибка LLM создания: {e}", style="red")
            console.print("Переходим к ручному созданию...", style="yellow")
            self._create_workflow_manual()

    def list_workflows(self):
        """Показать список workflow"""
        if not self.workflow_manager:
            console.print("Менеджер workflow не инициализирован", style="red")
            return
            
        workflows = self.workflow_manager.list_workflows()
        if not workflows:
            console.print("Нет доступных workflow", style="yellow")
            return
            
        console.print("\n=== Список Workflow ===", style="bold blue")
        table = Table(title="Доступные Workflow")
        table.add_column("№", style="cyan")
        table.add_column("Название", style="magenta")
        table.add_column("Описание", style="green")
        table.add_column("Текущий", style="yellow")
        
        for i, workflow in enumerate(workflows, 1):
            current_mark = "✓" if self.current_workflow and workflow['name'] == self.current_workflow['name'] else ""
            table.add_row(str(i), workflow['name'], workflow['description'], current_mark)
        
        console.print(table)

    def delete_workflow(self):
        """Удалить workflow"""
        try:
            workflows = self.workflow_manager.list_workflows()
            if not workflows:
                console.print("Нет доступных workflow", style="yellow")
                return
            
            # Предложить удаление через LLM
            use_llm = Confirm.ask("Выбрать workflow для удаления с помощью LLM?", default=True)
            
            if use_llm:
                asyncio.run(self._delete_workflow_with_llm(workflows))
            else:
                self._delete_workflow_manual(workflows)
                
        except Exception as e:
            console.print(f"Ошибка удаления workflow: {e}", style="red")
    
    def _delete_workflow_manual(self, workflows):
        """Ручное удаление workflow"""
        # Показываем список workflow
        console.print("\nДоступные workflow:")
        for i, workflow in enumerate(workflows, 1):
            console.print(f"{i}. {workflow['name']} - {workflow['description']}")
        
        choice = CustomPrompt.ask("Выберите номер workflow для удаления")
        try:
            index = int(choice) - 1
            if 0 <= index < len(workflows):
                workflow_name = workflows[index]['name']
                
                # Защита от удаления default workflow
                if workflow_name == 'default':
                    console.print("Нельзя удалить системный workflow 'default'", style="red")
                    return
                
                if Confirm.ask(f"Удалить workflow '{workflow_name}'?"):
                    if self.workflow_manager.delete_workflow(workflow_name):
                        console.print(f"Workflow '{workflow_name}' удален", style="green")
                    else:
                        console.print(f"Ошибка удаления workflow '{workflow_name}'", style="red")
            else:
                console.print("Неверный номер", style="red")
        except ValueError:
            console.print("Введите корректный номер", style="red")
    
    async def _delete_workflow_with_llm(self, workflows):
        """Удаление workflow с помощью LLM"""
        try:
            from llm.qwen_code import QwenCodeProvider
            from llm.base import LLMMessage
            
            # Запрос описания от пользователя
            user_description = CustomPrompt.ask("Опишите какой workflow вы хотите удалить")
            if not user_description:
                console.print("Описание не может быть пустым", style="red")
                return
            
            console.print("Поиск workflow через LLM...", style="yellow")
            
            # Формируем список workflow для LLM
            workflow_list = "\n".join([f"{i+1}. {w['name']}: {w['description']}" 
                                      for i, w in enumerate(workflows)])
            
            prompt = f"""Пользователь хочет удалить workflow: "{user_description}"

Доступные workflow:
{workflow_list}

Выбери наиболее подходящий workflow для удаления и верни только его название (name). 
Если ничего не подходит или пользователь хочет удалить системный workflow 'default', верни "none".
Верни только название workflow без дополнительных объяснений."""

            llm_provider = QwenCodeProvider()
            messages = [LLMMessage(role="user", content=prompt)]
            response = await llm_provider.chat_completion(messages)
            
            selected_name = response.content.strip().lower()
            
            # Найти workflow по имени
            selected_workflow = None
            for workflow in workflows:
                if workflow['name'].lower() == selected_name:
                    selected_workflow = workflow
                    break
            
            if selected_workflow:
                # Защита от удаления default workflow
                if selected_workflow['name'] == 'default':
                    console.print("LLM предложил удалить системный workflow 'default' - операция отклонена", style="red")
                    return
                
                # Показываем найденный workflow и запрашиваем подтверждение
                console.print(f"\n=== LLM предлагает удалить ===", style="bold blue")
                console.print(f"Название: {selected_workflow['name']}")
                console.print(f"Описание: {selected_workflow['description']}")
                
                if Confirm.ask(f"\nУдалить workflow '{selected_workflow['name']}'?"):
                    if self.workflow_manager.delete_workflow(selected_workflow['name']):
                        console.print(f"Workflow '{selected_workflow['name']}' удален", style="green")
                    else:
                        console.print(f"Ошибка удаления workflow '{selected_workflow['name']}'", style="red")
                else:
                    console.print("Удаление отменено", style="yellow")
            else:
                console.print("LLM не смог найти подходящий workflow. Выберите вручную:", style="yellow")
                self._delete_workflow_manual(workflows)
                
        except Exception as e:
            console.print(f"Ошибка LLM удаления: {e}", style="red")
            console.print("Переходим к ручному удалению...", style="yellow")
            self._delete_workflow_manual(workflows)

    def manage_agents(self):
        """Управление агентами"""
        while True:
            console.print("\n" + "-"*30)
            console.print("Управление агентами", style="bold")
            console.print("1. Список агентов")
            console.print("2. Создать агента")
            console.print("3. Удалить агента")
            console.print("4. Назад")
            
            choice = input("Выберите действие [1/2/3/4]: ").strip()
            
            if choice not in ["1", "2", "3", "4"]:
                console.print("Неверный выбор", style="red")
                continue
            
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
        
        # Сортировка по алфавиту по имени
        agents = sorted(agents, key=lambda agent: agent.name)
        
        table = Table(title="Агенты")
        table.add_column("Имя", style="cyan")
        table.add_column("Модель", style="magenta")
        table.add_column("Описание", style="green")
        table.add_column("Статус", style="blue")
        
        for agent in agents:
            table.add_row(
                agent.name,
                agent.llm_model,
                agent.description,
                agent.status.value
            )
        
        console.print(table)
    
    def create_agent(self):
        """Создать нового агента"""
        name = CustomPrompt.ask("Имя агента (например: developer-basic)")
        system_prompt = CustomPrompt.ask("Системный промпт агента")
        description = CustomPrompt.ask("Описание агента")
        
        # Выбор модели
        model_choice = CustomPrompt.ask(
            "Модель LLM",
            choices=["qwen3-coder-plus", "kiro-cli"],
            default="qwen3-coder-plus"
        )
        
        # Ввод capabilities
        capabilities_str = CustomPrompt.ask("Возможности (через запятую)", default="coding,debugging")
        capabilities = [cap.strip() for cap in capabilities_str.split(",")]
        
        try:
            self.agent_manager.create_agent(
                name=name,
                system_prompt=system_prompt,
                description=description,
                capabilities=capabilities,
                llm_model=model_choice
            )
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
            console.print(f"{i}. {agent.name}")
        
        choice = CustomPrompt.ask(
            "Выберите агента для удаления",
            choices=[str(i) for i in range(1, len(agents) + 1)]
        )
        
        agent_name = agents[int(choice) - 1].name
        
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
            
        # Проверка на default workflow
        if not self.current_workflow or self.current_workflow.get('name') == 'default':
            console.print("Управление этапами недоступно для default workflow", style="yellow")
            console.print("Создайте собственный workflow и выберите его как текущий", style="dim")
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
            
            choice = input("Выберите действие [1/2/3/4/5/6/7/8]: ").strip()
            
            if choice not in ["1", "2", "3", "4", "5", "6", "7", "8"]:
                console.print("Неверный выбор", style="red")
                continue
            
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
