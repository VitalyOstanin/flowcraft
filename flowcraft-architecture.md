# FlowCraft - Мультиагентный AI CLI агент

## Содержание

1. [Архитектура проекта](#архитектура-проекта)
2. [Структура проекта](#структура-проекта)
3. [Технологический стек](#технологический-стек)
4. [Ключевые компоненты](#ключевые-компоненты)
5. [Система настроек](#система-настроек)
6. [Система доверия команд](#система-доверия-команд)
7. [Workflow как граф состояний](#workflow-как-граф-состояний)
8. [MCP менеджер](#mcp-менеджер)
9. [Интерактивный CLI](#интерактивный-cli)
10. [Система команд управления](#система-команд-управления)
11. [Преимущества архитектуры](#преимущества-архитектуры)
12. [Пример workflow](#пример-workflow)
13. [Исходная постановка задачи](#исходная-постановка-задачи)

## Архитектура проекта

FlowCraft построен на основе LangGraph для обеспечения сложных workflow с условными переходами и интеграцией human-in-the-loop.

## Структура проекта

```
flowcraft/
├── src/
│   ├── core/
│   │   ├── session.py          # Управление сессиями с LangGraph checkpointers
│   │   ├── settings.py         # Работа с settings.yaml
│   │   ├── commands.py         # Система команд управления (/mcp, /trust, etc)
│   │   └── trust.py            # Система доверия команд
│   ├── workflows/
│   │   ├── base.py             # Базовый класс workflow
│   │   ├── loader.py           # Загрузка YAML конфигураций
│   │   ├── subgraphs/          # Переиспользуемые модули
│   │   │   ├── code_review.py  # Subgraph для код-ревью
│   │   │   ├── testing.py      # Subgraph для тестирования
│   │   │   └── deployment.py   # Subgraph для деплоя
│   │   ├── software_dev.py     # Разработка ПО
│   │   ├── feature_dev.py      # Разработка фичей
│   │   ├── incident_analysis.py # Анализ инцидентов
│   │   └── bug_fix.py          # Исправление багов
│   ├── agents/
│   │   ├── roles.py            # Определение ролей
│   │   ├── coordinator.py      # Координация агентов
│   │   └── llm_router.py       # Выбор модели по сложности
│   ├── tools/
│   │   ├── filesystem.py       # Файловые операции
│   │   ├── shell.py            # Системные команды с trust
│   │   └── search.py           # Поиск (rg, fdfind)
│   ├── mcp/
│   │   ├── manager.py          # Управление MCP серверами
│   │   └── client.py           # MCP клиент
│   └── llm/
│       ├── providers.py        # LLM провайдеры
│       ├── qwen.py             # Qwen-code интеграция
│       └── kiro_cli.py         # Интеграция с kiro-cli
├── cli.py                      # Главный CLI интерфейс
├── settings.yaml.example       # Пример настроек
├── ~/.flowcraft/
│   └── workflows/              # YAML конфигурации workflow
│       ├── feature-dev.yaml
│       ├── bug-fix.yaml
│       └── incident-analysis.yaml
└── requirements.txt
```

## Технологический стек

- **LangGraph** - основа для workflow управления с checkpointers для состояния
- **LangChain** - инструменты и интеграции
- **Python 3.11+** - основной язык
- **MCP (Model Context Protocol)** - для расширения возможностей
- **prompt_toolkit** - интерактивный CLI с автодополнением
- **rich** - красивое форматирование вывода
- **PyYAML** - работа с конфигурациями
- **Pydantic** - валидация настроек

## Ключевые компоненты

### Система настроек

Файл `settings.yaml` содержит все конфигурации:

```yaml
language: ru

llm:
  cheap_model:
    name: qwen-code
    api_endpoint: https://api.example.com/qwen3-coder-plus
    api_key: ${QWEN_API_KEY}
  expensive_model: kiro-cli
  expensive_stages:
    - security_review
    - architecture_design
    - complex_debugging

# Глобальные MCP серверы (доступны всем workflow)
mcp_servers:
  - name: filesystem
    command: mcp-server-filesystem
    args: ["--root", "/workspace"]
  - name: git
    command: mcp-server-git
  - name: db-prod
    command: mcp-server-postgres
    args: ["--host", "prod.db.com"]
  - name: db-stage
    command: mcp-server-postgres
    args: ["--host", "stage.db.com"]

# Только команды с уровнем "always" (навсегда разрешенные)
trust_rules:
  "git status": always
  "git log": always
  "npm install": always

workflows_dir: ~/.flowcraft/workflows
```

### YAML конфигурации workflow

Каждый workflow описывается в отдельном YAML файле:

```yaml
# ~/.flowcraft/workflows/feature-dev.yaml
name: feature-development
description: "Разработка новой фичи для SAAS"

# MCP серверы для этого workflow
mcp_servers: [filesystem, git, db-stage]

# Роли агентов
roles:
  - name: architect
    prompt: "Ты архитектор SaaS-системы. Отвечай на {{language}}."
    expensive_model: true
  - name: developer
    prompt: "Ты fullstack-разработчик. Используй TypeScript. Отвечай на {{language}}."
    expensive_model: false
  - name: reviewer
    prompt: "Ты код-ревьюер. Фокусируйся на безопасности. Отвечай на {{language}}."
    expensive_model: true

# Инструменты
tools:
  - file_crud
  - shell
  - search

# Этапы workflow
stages:
  - name: analyze_requirements
    roles: [architect]
    skippable: true
  - name: design_architecture
    roles: [architect]
    skippable: true
  - name: implement_feature
    roles: [developer]
    skippable: false
  - name: code_review
    roles: [reviewer]
    skippable: false
  - name: security_review
    roles: [reviewer]
    skippable: true
```

### Система доверия команд

```python
from enum import Enum
from typing import Dict, Set

class TrustLevel(Enum):
    ONCE = "once"        # y - разрешить один раз
    SESSION = "session"  # s - разрешить в сессии (не сохраняется)
    ALWAYS = "always"    # t - запомнить навсегда
    DENY = "deny"        # n - отклонить

class TrustManager:
    def __init__(self, settings: Dict):
        self.trust_rules = settings.get("trust_rules", {})
        self.session_permissions: Set[str] = set()  # Не сохраняется между сессиями
    
    def check_command(self, cmd: str) -> TrustLevel:
        # Проверка постоянных правил
        for pattern, level in self.trust_rules.items():
            if self._matches_pattern(cmd, pattern):
                return TrustLevel.ALWAYS
        
        # Проверка сессионных разрешений
        if cmd in self.session_permissions:
            return TrustLevel.SESSION
            
        return TrustLevel.ONCE
    
    def prompt_user(self, cmd: str) -> str:
        print(f"Выполнить команду: {cmd}")
        print("y - разрешить один раз")
        print("s - разрешить в сессии") 
        print("t - запомнить навсегда")
        print("n - отклонить")
        return input("Выбор: ").lower()
    
    def handle_response(self, cmd: str, response: str):
        if response == 't':
            # Добавить в постоянные правила и сохранить в settings.yaml
            self.trust_rules[cmd] = "always"
            self.save_settings()
        elif response == 's':
            # Добавить в сессионные разрешения
            self.session_permissions.add(cmd)
```

### Workflow как граф состояний

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from typing import TypedDict, List, Dict, Optional

class WorkflowState(TypedDict):
    version: str                    # Версия для миграций
    task: str
    current_step: str
    results: Dict
    agents: List[str]
    human_feedback: Optional[str]
    skipped_stages: List[str]       # Пропущенные этапы
    active_mcp_servers: List[str]   # Активные MCP для workflow

class BaseWorkflow:
    def __init__(self, config: Dict, thread_id: str):
        self.config = config
        self.thread_id = thread_id
        self.checkpointer = SqliteSaver.from_conn_string("checkpoints.db")
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(WorkflowState)
        
        # Базовые узлы
        workflow.add_node("analyze", self.analyze_task)
        workflow.add_node("plan", self.create_plan)
        workflow.add_node("execute", self.execute_step)
        workflow.add_node("review", self.review_result)
        workflow.add_node("human_input", self.get_human_input)
        workflow.add_node("llm_stage_planner", self.plan_stages)
        
        # Добавление subgraphs
        workflow.add_node("code_review", self.get_code_review_subgraph())
        workflow.add_node("testing", self.get_testing_subgraph())
        
        workflow.set_entry_point("llm_stage_planner")  # LLM планирует этапы
        workflow.add_edge("llm_stage_planner", "analyze")
        workflow.add_edge("analyze", "plan")
        workflow.add_conditional_edges(
            "plan",
            self.should_skip_to_execution,
            {"skip": "execute", "continue": "execute"}
        )
        
        return workflow.compile(checkpointer=self.checkpointer)
    
    def plan_stages(self, state: WorkflowState) -> WorkflowState:
        """LLM анализирует задачу и предлагает пропустить этапы"""
        task_description = state["task"]
        
        # LLM анализ для определения пропускаемых этапов
        llm_analysis = self.llm_router.analyze_task_complexity(task_description)
        
        suggested_skips = llm_analysis.get("suggested_skips", [])
        if suggested_skips:
            # Запрос подтверждения у пользователя
            confirmation = self.request_stage_skip_confirmation(suggested_skips)
            if confirmation:
                state["skipped_stages"].extend(suggested_skips)
        
        return state
    
    def resume_from_checkpoint(self, checkpoint_id: str):
        """Восстановление сессии из чекпоинта"""
        config = {"configurable": {"thread_id": self.thread_id}}
        
        # LangGraph автоматически восстанавливает состояние
        for chunk in self.graph.stream(None, config=config):
            yield chunk
    
    def save_checkpoint(self, name: str):
        """Сохранение именованного чекпоинта"""
        # Реализация через LangGraph checkpointer
        pass
```

### MCP менеджер

```python
import subprocess
from typing import Dict, List, Set

class MCPManager:
    def __init__(self, settings: Dict):
        self.global_servers = settings.get("mcp_servers", [])
        self.running_servers = {}
        self.workflow_server_mapping = {}  # workflow -> active servers
    
    def start_servers_for_workflow(self, workflow_name: str, server_names: List[str]):
        """Запуск MCP серверов для конкретного workflow"""
        active_servers = []
        
        for server_name in server_names:
            server_config = self._find_server_config(server_name)
            if server_config and server_name not in self.running_servers:
                self.start_server(server_config)
            active_servers.append(server_name)
        
        self.workflow_server_mapping[workflow_name] = active_servers
    
    def start_server(self, server_config: Dict):
        name = server_config["name"]
        process = subprocess.Popen(
            [server_config["command"]] + server_config.get("args", [])
        )
        self.running_servers[name] = process
    
    def stop_server(self, name: str):
        if name in self.running_servers:
            self.running_servers[name].terminate()
            del self.running_servers[name]
    
    def restart_server(self, name: str):
        server_config = self._find_server_config(name)
        self.stop_server(name)
        self.start_server(server_config)
    
    def enable_server_for_workflow(self, server_name: str, workflow_name: str):
        """Включить MCP сервер для конкретного workflow"""
        if workflow_name not in self.workflow_server_mapping:
            self.workflow_server_mapping[workflow_name] = []
        
        if server_name not in self.workflow_server_mapping[workflow_name]:
            self.workflow_server_mapping[workflow_name].append(server_name)
            
            # Запустить сервер если он не запущен
            if server_name not in self.running_servers:
                server_config = self._find_server_config(server_name)
                self.start_server(server_config)
    
    def disable_server_for_workflow(self, server_name: str, workflow_name: str):
        """Отключить MCP сервер для конкретного workflow"""
        if workflow_name in self.workflow_server_mapping:
            if server_name in self.workflow_server_mapping[workflow_name]:
                self.workflow_server_mapping[workflow_name].remove(server_name)
        
        # Проверить, используется ли сервер другими workflow
        still_used = any(
            server_name in servers 
            for servers in self.workflow_server_mapping.values()
        )
        
        # Остановить сервер если он больше не используется
        if not still_used:
            self.stop_server(server_name)
    
    def add_server(self, name: str, command: str, args: List[str] = None):
        """Добавить новый MCP сервер в глобальные настройки"""
        new_server = {
            "name": name,
            "command": command,
            "args": args or []
        }
        self.global_servers.append(new_server)
        # Сохранить в settings.yaml
        self._save_settings()
    
    def remove_server(self, name: str):
        """Удалить MCP сервер из глобальных настроек"""
        self.stop_server(name)
        self.global_servers = [s for s in self.global_servers if s["name"] != name]
        
        # Удалить из всех workflow
        for workflow_servers in self.workflow_server_mapping.values():
            if name in workflow_servers:
                workflow_servers.remove(name)
        
        self._save_settings()
    
    def _find_server_config(self, name: str) -> Dict:
        return next((s for s in self.global_servers if s["name"] == name), None)
```

### Интерактивный CLI

```python
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import InMemoryHistory
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from typing import Dict

class InteractiveCLI:
    def __init__(self):
        self.console = Console()
        self.session = None
        self.workflows = {}
        self.command_history = InMemoryHistory()
        self.mcp_manager = MCPManager()
        self.llm_router = LLMRouter()
        
        # Автодополнение для команд
        self.command_completer = WordCompleter([
            '/mcp', '/trust', '/workflow', '/session', '/help', '/quit'
        ])
    
    def start_session(self):
        self.console.print(Panel("Добро пожаловать в FlowCraft!", style="bold blue"))
        
        workflow_type = self.select_workflow()
        task_details = self.gather_task_details()
        
        workflow = self.workflows[workflow_type](task_details)
        self.execute_workflow(workflow)
    
    def select_workflow(self) -> str:
        workflows = list(self.workflows.keys())
        
        table = Table(title="Доступные Workflow")
        table.add_column("№", style="cyan")
        table.add_column("Название", style="magenta")
        table.add_column("Описание", style="green")
        
        for i, wf in enumerate(workflows, 1):
            config = self.load_workflow_config(wf)
            table.add_row(str(i), wf, config.get("description", ""))
        
        self.console.print(table)
        
        choice = prompt("Выберите workflow: ", completer=WordCompleter([str(i) for i in range(1, len(workflows)+1)]))
        return workflows[int(choice) - 1]
    
    def gather_task_details(self) -> Dict:
        task_id = prompt("ID задачи: ", history=self.command_history)
        description = prompt("Описание задачи: ", history=self.command_history)
        
        return {
            "task_id": task_id,
            "description": description
        }
    
    def execute_workflow(self, workflow):
        """Выполнение workflow с поддержкой команд управления"""
        for step in workflow.run():
            # Отображение текущего состояния
            self.display_workflow_status(step)
            
            # Проверка на команды управления
            if step.get("human_input_required"):
                user_input = prompt(
                    "Ваш ответ (или команда /help): ", 
                    completer=self.command_completer,
                    history=self.command_history
                )
                
                if user_input.startswith('/'):
                    self.handle_command(user_input, workflow)
                else:
                    workflow.provide_feedback(user_input)
    
    def handle_command(self, command: str, workflow):
        """Обработка команд управления"""
        parts = command.split()
        cmd = parts[0]
        
        if cmd == '/mcp':
            self.handle_mcp_command(parts[1:], workflow)
        elif cmd == '/trust':
            self.handle_trust_command(parts[1:])
        elif cmd == '/workflow':
            self.handle_workflow_command(parts[1:], workflow)
        elif cmd == '/session':
            self.handle_session_command(parts[1:], workflow)
        elif cmd == '/help':
            self.show_help()
    
    def handle_mcp_command(self, args: List[str], workflow):
        """Обработка команд MCP"""
        if not args:
            return
            
        action = args[0]
        
        if action == 'add':
            # /mcp add db-test --command mcp-server-postgres --args "--host test.db.com"
            name = args[1]
            command = args[args.index('--command') + 1]
            args_start = args.index('--args') + 1 if '--args' in args else None
            server_args = args[args_start:] if args_start else []
            
            self.mcp_manager.add_server(name, command, server_args)
            self.console.print(f"✅ MCP сервер {name} добавлен", style="green")
            
        elif action == 'enable':
            # /mcp enable db-prod --workflow incident-analysis
            server_name = args[1]
            workflow_name = args[args.index('--workflow') + 1] if '--workflow' in args else None
            
            if workflow_name:
                self.mcp_manager.enable_server_for_workflow(server_name, workflow_name)
                self.console.print(f"✅ MCP {server_name} включен для {workflow_name}", style="green")
            else:
                self.mcp_manager.start_server(self.mcp_manager._find_server_config(server_name))
                self.console.print(f"✅ MCP {server_name} запущен", style="green")
    
    def handle_llm_command_suggestion(self, user_input: str, workflow):
        """LLM предлагает команду на основе пользовательского ввода"""
        
        # LLM анализирует ввод и предлагает команду
        suggested_command = self.llm_router.suggest_command(user_input)
        
        if suggested_command:
            self.console.print(Panel(
                f"Предлагаю выполнить команду:\n{suggested_command}",
                title="LLM предложение",
                style="yellow"
            ))
            
            confirmation = prompt("Подтвердить выполнение? [y/n/modify]: ")
            
            if confirmation.lower() == 'y':
                self.handle_command(suggested_command, workflow)
            elif confirmation.lower() == 'modify':
                modified_command = prompt(f"Измените команду: ", default=suggested_command)
                self.handle_command(modified_command, workflow)
    
    def display_workflow_status(self, step: Dict):
        """Отображение статуса workflow с помощью rich"""
        status_panel = Panel(
            f"Этап: {step.get('current_step', 'N/A')}\n"
            f"Роль: {step.get('current_role', 'N/A')}\n"
            f"Прогресс: {step.get('progress', 'N/A')}",
            title="Статус Workflow",
            style="blue"
        )
        self.console.print(status_panel)
```

### Система команд управления

FlowCraft поддерживает команды управления во время выполнения workflow:

#### Команды MCP управления
```bash
/mcp add <name> --command <cmd> --args "<args>"     # Добавить MCP сервер
/mcp remove <name>                                  # Удалить MCP сервер
/mcp restart <name>                                 # Перезапустить MCP сервер
/mcp enable <name> --workflow <workflow>            # Включить MCP для workflow
/mcp disable <name> --workflow <workflow>           # Отключить MCP для workflow
```

#### Команды доверия
```bash
/trust add "<pattern>" --level always               # Добавить доверенную команду
```

#### Команды workflow
```bash
/workflow skip-stage <stage_name>                   # Пропустить этап
/workflow from-stage <stage_name>                   # Начать с этапа
```

#### Команды сессии
```bash
/session save <checkpoint_name>                     # Сохранить чекпоинт
/session resume <checkpoint_name>                   # Восстановить чекпоинт
/session list                                       # Список сессий
```

#### LLM-инициированные команды

LLM может предлагать команды управления с обязательным подтверждением:

```
USER: добавь базу данных для тестирования
LLM: Предлагаю выполнить команду:
     /mcp add db-test --command mcp-server-postgres --args "--host test.db.com --port 5432"
     Подтвердить выполнение? [y/n/modify]
USER: y
SYSTEM: ✅ MCP сервер db-test добавлен и запущен
```

### Subgraphs для модульности

```python
# Переиспользуемые модули workflow
def create_code_review_subgraph():
    review_graph = StateGraph(ReviewState)
    review_graph.add_node("static_analysis", static_analysis_node)
    review_graph.add_node("security_check", security_check_node)
    review_graph.add_node("performance_check", performance_check_node)
    return review_graph.compile()

def create_testing_subgraph():
    test_graph = StateGraph(TestState)
    test_graph.add_node("unit_tests", unit_test_node)
    test_graph.add_node("integration_tests", integration_test_node)
    return test_graph.compile()

# Использование в workflow
class FeatureDevWorkflow(BaseWorkflow):
    def _build_graph(self):
        workflow = StateGraph(WorkflowState)
        
        # Добавление переиспользуемых subgraphs
        workflow.add_node("code_review", create_code_review_subgraph())
        workflow.add_node("testing", create_testing_subgraph())
        
        return workflow.compile()
```

## Преимущества архитектуры

1. **Модульность** - каждый компонент независим и может быть заменен
2. **Расширяемость** - легко добавлять новые workflow, роли и инструменты через YAML конфигурации
3. **Гибкость** - настраиваемые MCP серверы на уровне workflow, переиспользуемые subgraphs
4. **Безопасность** - система доверия команд с гранулярным контролем и сессионными разрешениями
5. **Персистентность** - LangGraph checkpointers с автоматическим сохранением состояния
6. **Интерактивность** - human-in-the-loop на каждом этапе с rich CLI интерфейсом
7. **Производительность** - использование оптимизированных инструментов (rg, fdfind)
8. **Экономичность** - автоматический выбор модели по сложности задачи
9. **Управляемость** - команды управления во время выполнения с LLM предложениями
10. **Надежность** - версионирование состояния для безопасных обновлений

## Пример workflow

### Workflow разработки фичи

```python
class FeatureDevWorkflow(BaseWorkflow):
    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(WorkflowState)
        
        # Этапы разработки
        workflow.add_node("analyze_requirements", self.analyze_requirements)
        workflow.add_node("design_architecture", self.design_architecture)
        workflow.add_node("implement_feature", self.implement_feature)
        workflow.add_node("write_tests", self.write_tests)
        workflow.add_node("code_review", self.code_review)
        workflow.add_node("security_review", self.security_review)
        workflow.add_node("performance_review", self.performance_review)
        
        # Граф переходов
        workflow.set_entry_point("analyze_requirements")
        workflow.add_edge("analyze_requirements", "design_architecture")
        workflow.add_edge("design_architecture", "implement_feature")
        workflow.add_edge("implement_feature", "write_tests")
        
        # Условные переходы для ревью
        workflow.add_conditional_edges(
            "write_tests",
            self.should_do_reviews,
            {
                "code_review": "code_review",
                "security_review": "security_review",
                "performance_review": "performance_review",
                "complete": END
            }
        )
        
        # Итеративные улучшения
        workflow.add_conditional_edges(
            "code_review",
            self.needs_iteration,
            {"iterate": "implement_feature", "next": "security_review"}
        )
        
        return workflow.compile()
    
    def analyze_requirements(self, state: WorkflowState) -> WorkflowState:
        # Роль: аналитик
        # Инструменты: поиск файлов, чтение документации
        pass
    
    def implement_feature(self, state: WorkflowState) -> WorkflowState:
        # Роль: разработчик
        # Инструменты: файловые операции, git команды
        pass
```

## Заключение

Обновленная архитектура FlowCraft включает все согласованные улучшения:

### Ключевые нововведения

1. **LangGraph checkpointers** - надежное сохранение состояния с версионированием
2. **YAML конфигурации** - декларативное описание workflow и настроек
3. **Rich CLI интерфейс** - красивый вывод и автодополнение команд
4. **LLM Router** - автоматический выбор модели по сложности (qwen3-coder-plus vs kiro-cli)
5. **Интеллектуальное планирование** - LLM предлагает пропуск этапов
6. **Система команд управления** - динамическое управление MCP и workflow
7. **LLM-инициированные команды** - AI предлагает команды с подтверждением
8. **Переиспользуемые subgraphs** - модульные компоненты workflow
9. **Workflow-специфичные MCP** - разные наборы серверов для разных задач
10. **Улучшенная система доверия** - сессионные разрешения без сохранения

### Технические преимущества

- Минимальная сложность реализации при максимальной функциональности
- Стандартные инструменты LangGraph/LangChain экосистемы
- Безопасность через систему доверия команд
- Экономичность через умный выбор LLM модели
- Расширяемость через YAML конфигурации и MCP протокол

Архитектура готова к реализации и обеспечивает все требуемые возможности мультиагентного AI CLI агента.

## Исходная постановка задачи

### Цель проекта
Создать мультиагентный AI CLI агент для выполнения разных workflows:
- разработка нового software проекта
- разработка новой фичи SAAS микросервисов
- анализ инцидентов
- исправление багов
- анализ и фильтрация данных из источников данных и пересылка в новые источники данных

### Основные требования

#### Интерактивная сессия
CLI агент должен работать в интерактивной сессии, где сессия начинается с выбора workflow и уточнения деталей задачи.

#### Память и настройки
- Stateful память с сохранением на fs между перезапусками
- Единый файл settings.json (под .gitignore) для хранения всех настроек, включая mcp серверы
- Настройка языка общения по умолчанию (ru/en, default=ru)
- Все промпты в LLM должны содержать явное указание языка общения

#### Инструменты
Проект должен поддерживать tools для:
- поиска, чтения, создания и записи файлов
- выполнения системных команд с подтверждением от пользователя
- использование оптимизированных системных инструментов: fdfind для поиска файлов, ripgrep (rg) для поиска содержимого

#### Система доверия команд
Уровни доверия для команд:
- `y` - разрешить один раз (yes)
- `s` - разрешить в текущей сессии (yes for session)
- `t` - запомнить навсегда (yes and trust)
- `n` - отклонить (no)

Настройка префиксов команд:
- `git worktree add *`
- `git worktree *`
- `git *`

#### Workflow требования
Каждый workflow должен поддерживать:
1. Настраиваемый набор mcp серверов
2. Настраиваемый набор ролей агентов (аналитик, разработчик, reviewer, тестировщик, DB performance review, code performance review, security review)
3. Настраиваемый набор инструментов
4. Возможность работы не с первого этапа (пропуск части этапов)

#### LLM поддержка
- Поддержка LLM qwen-code
- Запуск внешних cli агентов в неинтерактивном режиме
- Определение этапов, требующих дорогих моделей
- Human-in-the-loop поддержка

#### MCP управление
Поддержка изменения набора mcp серверов без перезапуска сессии:
- добавление, удаление mcp
- включение, отключение mcp
- перезапуск mcp

#### Пример использования
```
USER: начни работу над задачей TASK-NNNN
AGENT: предлагаю workflow такой-то, этапы такие-то, команда из таких-то ролей
USER: корректировка предложения, подтверждение
AGENT: начинаю выполнение такой-то части задания: этап такой-то, роль такая-то
```
