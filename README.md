# FlowCraft - Мультиагентный AI CLI агент

## Содержание

1. [Описание](#описание)
2. [Установка](#установка)
3. [Быстрый старт](#быстрый-старт)
4. [Структура проекта](#структура-проекта)
5. [Конфигурация](#конфигурация)
6. [Использование](#использование)
7. [LangGraph Workflow](#langgraph-workflow)
8. [Подграфы](#подграфы)
9. [Разработка](#разработка)

## Описание

FlowCraft - это мультиагентный AI CLI агент для выполнения различных workflow:
- Разработка нового software проекта
- Разработка новой фичи SAAS микросервисов
- Анализ инцидентов
- Исправление багов

### Ключевые особенности

- **LangGraph Workflow Engine** - полноценная система выполнения workflow с состояниями
- **Динамические подграфы** - переиспользуемые компоненты для модульности
- **Human-in-the-loop** - интеграция с пользователем в процессе выполнения
- **Система checkpoints** - сохранение состояния и возможность возобновления
- Интерактивная сессия с выбором workflow
- Система доверия команд с гранулярным контролем
- Динамическое управление агентами
- Конфигурация через YAML файлы
- Поддержка различных LLM моделей

## Установка

### Требования

- Python 3.11+
- uv (рекомендуется) или pip
- Node.js (для qwen-code CLI)

### Установка зависимостей

```bash
# Рекомендуется - с uv
uv pip install -r requirements.txt

# Альтернативно - с pip
pip install -r requirements.txt
```

### Настройка qwen3-coder-plus

Для использования модели qwen3-coder-plus необходимо установить CLI утилиту:

```bash
# Установка qwen-code CLI
npm install -g @qwen-code/qwen-code@latest
```

OAuth credentials создаются CLI утилитой qwen-code и сохраняются в `~/.qwen/oauth_creds.json`. Проект автоматически обновляет истекшие токены при необходимости.

### Дополнительные инструменты (рекомендуется)

```bash
# Для оптимизированного поиска
sudo apt install ripgrep fd-find  # Ubuntu/Debian
brew install ripgrep fd           # macOS
```

## Быстрый старт

### 1. Тестирование установки

```bash
python test_cli.py
```

### 2. Запуск FlowCraft

```bash
python cli.py
```

### 3. Создание настроек

При первом запуске будет создан файл `~/.flowcraft/settings.yaml` на основе `settings.yaml.example`.

## Структура проекта

```
flowcraft/
├── src/                    # Исходный код
│   ├── core/              # Основные компоненты
│   │   ├── settings.py    # Система настроек
│   │   ├── trust.py       # Система доверия команд
│   │   └── interactive_cli.py # Интерактивный CLI
│   ├── agents/            # Управление агентами
│   │   ├── manager.py     # Менеджер агентов
│   │   └── roles.py       # Определения ролей
│   ├── workflows/         # Система workflow
│   │   ├── base.py        # Базовый класс workflow
│   │   ├── loader.py      # Загрузчик конфигураций
│   │   ├── manager.py     # Менеджер workflow
│   │   ├── engine.py      # LangGraph движок
│   │   ├── state.py       # Система состояний
│   │   ├── nodes.py       # Узлы LangGraph
│   │   ├── llm_integration.py # Интеграция с LLM
│   │   └── subgraphs/     # Динамические подграфы
│   │       ├── base.py    # Базовый класс подграфов
│   │       ├── registry.py # Реестр подграфов
│   │       └── common.py  # Стандартные подграфы
│   └── tools/             # Инструменты
│       ├── filesystem.py  # Файловые операции
│       ├── shell.py       # Системные команды
│       └── search.py      # Поиск содержимого
├── examples/              # Примеры workflow
├── tests/                 # Тесты
├── cli.py                 # Главный CLI интерфейс
├── settings.yaml.example  # Пример настроек
└── ~/.flowcraft/workflows/ # Конфигурации workflow
```

## Конфигурация

### Основные настройки (~/.flowcraft/settings.yaml)

```yaml
language: ru

llm:
  cheap_model: qwen3-coder-plus
  expensive_model: kiro-cli
  expensive_stages:
    - security_review
    - architecture_design
  # Путь к OAuth credentials для qwen-code (опционально)
  # qwen_oauth_path: ~/.qwen/oauth_creds.json

mcp_servers: []

trust_rules:
  "git status": always
  "git log": always

workflows_dir: ~/.flowcraft/workflows

agents: {}
```

### Создание workflow

Пример workflow для исправления багов (`~/.flowcraft/workflows/bug-fix.yaml`):

```yaml
name: bug-fix
description: "Workflow для исправления багов"

roles:
  - name: developer
    prompt: "Ты разработчик. Анализируй и исправляй баги. Отвечай на русском."
    expensive_model: false

stages:
  - name: analyze_bug
    roles: [developer]
    skippable: false
    description: "Анализ бага и воспроизведение проблемы"
  
  - name: implement_fix
    roles: [developer]
    skippable: false
    description: "Реализация исправления"
```

## Использование

### Запуск интерактивной сессии

```bash
python cli.py
```

### Основные функции

1. **Запуск workflow**
   - Выбор из доступных workflow
   - Ввод деталей задачи
   - Пошаговое выполнение через LangGraph

2. **Управление агентами**
   - Создание новых агентов
   - Просмотр списка агентов
   - Удаление агентов

3. **Управление этапами workflow**
   - CRUD операции с этапами
   - Включение/отключение этапов
   - Выполнение команд от LLM с подтверждением
   - Интерактивное редактирование этапов

4. **Просмотр настроек**
   - Текущая конфигурация
   - Статистика системы

### Система доверия команд

При выполнении системных команд FlowCraft запрашивает разрешение:

- `y` - разрешить один раз
- `s` - разрешить в текущей сессии
- `t` - запомнить навсегда
- `n` - отклонить

## LangGraph Workflow

FlowCraft использует LangGraph для выполнения workflow с поддержкой:

### Основные возможности

- **Состояния workflow** - полное отслеживание контекста выполнения
- **Узлы агентов** - выполнение задач через LLM провайдеры
- **Условные переходы** - динамическая логика выполнения
- **Human-in-the-loop** - запрос пользовательского ввода
- **Checkpoints** - сохранение и восстановление состояния
- **Параллельное выполнение** - одновременное выполнение независимых этапов

### Типы узлов

1. **StartNode** - инициализация workflow
2. **EndNode** - завершение workflow
3. **AgentNode** - выполнение задач агентами
4. **HumanInputNode** - запрос пользовательского ввода
5. **ConditionalNode** - условные переходы
6. **SubgraphNode** - выполнение подграфов

### Система состояний

```python
class WorkflowState:
    messages: List[BaseMessage]      # История сообщений
    context: WorkflowContext         # Контекст выполнения
    agents: Dict[str, AgentState]    # Активные агенты
    current_node: str                # Текущий узел
    finished: bool                   # Флаг завершения
    result: Optional[Dict]           # Результат выполнения
```

## Подграфы

Система динамических подграфов для переиспользования компонентов:

### Стандартные подграфы

1. **CodeAnalysisSubgraph** - анализ кода и архитектуры
2. **TestingSubgraph** - создание и выполнение тестов
3. **SecurityReviewSubgraph** - проверка безопасности
4. **DeploymentSubgraph** - развертывание приложений
5. **DocumentationSubgraph** - создание документации

### Использование в workflow

```yaml
stages:
  - name: code_analysis
    type: subgraph
    subgraph: code_analysis
    description: "Комплексный анализ кода"
    input_requirements:
      - code_path: "Путь к исходному коду"
      - project_type: "Тип проекта"
```

### Создание собственных подграфов

```python
class CustomSubgraph(BaseSubgraph):
    def define_nodes(self) -> Dict[str, BaseNode]:
        return {
            "custom_node": AgentNode(...)
        }
    
    def define_edges(self) -> List[tuple]:
        return [("start", "custom_node")]
```

## Разработка

### Текущий статус

Полностью реализованы:
- Система настроек
- Система доверия команд
- Менеджер агентов
- **LangGraph workflow engine**
- **Система динамических подграфов**
- **LLM интеграция для workflow**
- **Human-in-the-loop поддержка**
- Интерактивный CLI
- Базовые инструменты
- LLM провайдер qwen3-coder-plus с OAuth аутентификацией

### Тестирование

```bash
# Установка зависимостей для тестирования
pip install pytest pytest-asyncio

# Запуск всех тестов
pytest

# Запуск тестов LangGraph
pytest tests/test_langgraph_workflow.py

# Запуск тестов LLM
pytest tests/test_llm/

# Быстрый тест qwen3-coder-plus
python tests/test_llm/test_qwen_simple.py

# Полный интеграционный тест
python tests/test_llm/test_qwen_integration.py
```

### Добавление нового workflow

1. Создать YAML файл в `~/.flowcraft/workflows/`
2. Определить stages и roles
3. Опционально использовать подграфы
4. Workflow автоматически появится в списке

### Создание агента

```python
agent_manager.create_agent(
    name="my_agent",
    role="developer", 
    description="Мой агент",
    capabilities=["coding"],
    llm_model="qwen3-coder-plus"
)
```

### Примеры workflow

Смотрите директорию `examples/` для готовых примеров:
- `full-development-workflow.yaml` - полный цикл разработки
- `bug-fix-workflow.yaml` - исправление багов
```
