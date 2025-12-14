# Changelog

Все значимые изменения в проекте FlowCraft документируются в этом файле.

## [Unreleased] - 2025-12-14

### Добавлено

#### LangGraph Workflow Engine
- Полноценная система выполнения workflow на базе LangGraph
- Система состояний WorkflowState с поддержкой TypedDict
- Базовые узлы: StartNode, EndNode, AgentNode, HumanInputNode, ConditionalNode
- WorkflowEngine для управления выполнением workflow
- Интеграция с checkpointer для сохранения состояния

#### Система динамических подграфов
- BaseSubgraph - базовый класс для переиспользуемых компонентов
- SubgraphRegistry - реестр для управления подграфами
- CompositeSubgraph - композитные подграфы из других подграфов
- Стандартные подграфы:
  - CodeAnalysisSubgraph - анализ кода и архитектуры
  - TestingSubgraph - создание и выполнение тестов
  - SecurityReviewSubgraph - проверка безопасности
  - DeploymentSubgraph - развертывание приложений
  - DocumentationSubgraph - создание документации

#### LLM интеграция для workflow
- WorkflowLLMManager для управления LLM провайдерами в workflow
- Автоматический выбор модели на основе настроек и типа stage
- Подготовка контекста и промптов для агентов
- Валидация ответов LLM

#### Human-in-the-loop поддержка
- HumanInputNode для запроса пользовательского ввода
- Интеграция с системой доверия команд
- Поддержка пользовательского подтверждения в критических этапах

#### Обновления WorkflowManager
- Интеграция с WorkflowEngine для реального выполнения workflow
- Валидация конфигураций workflow с проверкой подграфов
- Создание workflow из шаблонов
- Анализ зависимостей workflow

#### Примеры и тестирование
- Полный пример workflow с подграфами (full-development-workflow.yaml)
- Простой пример для исправления багов (bug-fix-workflow.yaml)
- Комплексные тесты для всех компонентов LangGraph системы
- Интеграционные тесты workflow

#### Обновления CLI
- Реальное выполнение workflow вместо заглушки
- Отображение результатов выполнения
- Инициализация всех LangGraph компонентов при запуске
- Регистрация стандартных подграфов

### Изменено

#### Соответствие rules.md
- Убраны все эмодзи из кода согласно правилам проекта
- Обновлена документация (README.md, TODO.md)
- Создан Changelog.md для отслеживания изменений

#### Структура проекта
- Расширена директория workflows/ новыми модулями
- Добавлена поддержка подграфов в subgraphs/
- Обновлены зависимости в requirements.txt

### Технические детали

#### Архитектура LangGraph
- Использование StateGraph для создания workflow графов
- TypedDict для типизированных состояний
- Поддержка условных переходов и параллельного выполнения
- Система checkpoints для персистентности

#### Модульность подграфов
- Переиспользуемые компоненты workflow
- Валидация входных и выходных данных
- Композиция сложных workflow из простых блоков
- Автоматическое управление зависимостями

#### Интеграция с существующей системой
- Совместимость с текущим WorkflowManager
- Использование существующих AgentManager и TrustManager
- Сохранение обратной совместимости API

### Файлы

#### Новые файлы
- `src/workflows/state.py` - система состояний
- `src/workflows/nodes.py` - узлы LangGraph
- `src/workflows/engine.py` - движок workflow
- `src/workflows/llm_integration.py` - LLM интеграция
- `src/workflows/subgraphs/__init__.py` - инициализация подграфов
- `src/workflows/subgraphs/base.py` - базовые классы подграфов
- `src/workflows/subgraphs/registry.py` - реестр подграфов
- `src/workflows/subgraphs/common.py` - стандартные подграфы
- `tests/test_langgraph_workflow.py` - тесты LangGraph системы
- `examples/full-development-workflow.yaml` - полный пример workflow
- `examples/bug-fix-workflow.yaml` - пример workflow для багов
- `Changelog.md` - этот файл

#### Обновленные файлы
- `src/workflows/manager.py` - интеграция с LangGraph engine
- `src/core/interactive_cli.py` - реальное выполнение workflow
- `cli.py` - инициализация LangGraph компонентов
- `README.md` - документация по LangGraph и подграфам
- `TODO.md` - отметка выполненных задач
- `rules.md` - добавлено правило об обновлении документации

### Статистика

- Добавлено: ~2000 строк кода
- Новых файлов: 11
- Обновленных файлов: 6
- Тестов: 15+ новых тестовых методов
- Подграфов: 5 стандартных реализаций
