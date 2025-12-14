# FlowCraft - Мультиагентный AI CLI агент

## Содержание

1. [Описание](#описание)
2. [Установка](#установка)
3. [Быстрый старт](#быстрый-старт)
4. [Структура проекта](#структура-проекта)
5. [Конфигурация](#конфигурация)
6. [Использование](#использование)
7. [Разработка](#разработка)

## Описание

FlowCraft - это мультиагентный AI CLI агент для выполнения различных workflow:
- Разработка нового software проекта
- Разработка новой фичи SAAS микросервисов
- Анализ инцидентов
- Исправление багов

### Ключевые особенности

- Интерактивная сессия с выбором workflow
- Система доверия команд с гранулярным контролем
- Динамическое управление агентами
- Конфигурация через YAML файлы
- Поддержка различных LLM моделей

## Установка

### Требования

- Python 3.11+
- uv (рекомендуется) или pip

### Установка зависимостей

```bash
# Рекомендуется - с uv
uv pip install -r requirements.txt

# Альтернативно - с pip
pip install -r requirements.txt
```

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

При первом запуске будет создан файл `settings.yaml` на основе `settings.yaml.example`.

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
│   │   └── loader.py      # Загрузчик конфигураций
│   └── tools/             # Инструменты
│       ├── filesystem.py  # Файловые операции
│       ├── shell.py       # Системные команды
│       └── search.py      # Поиск содержимого
├── cli.py                 # Главный CLI интерфейс
├── settings.yaml.example  # Пример настроек
└── ~/.flowcraft/workflows/ # Конфигурации workflow
```

## Конфигурация

### Основные настройки (settings.yaml)

```yaml
language: ru

llm:
  cheap_model: qwen-code
  expensive_model: kiro-cli
  expensive_stages:
    - security_review
    - architecture_design

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
   - Пошаговое выполнение

2. **Управление агентами**
   - Создание новых агентов
   - Просмотр списка агентов
   - Удаление агентов

3. **Просмотр настроек**
   - Текущая конфигурация
   - Статистика системы

### Система доверия команд

При выполнении системных команд FlowCraft запрашивает разрешение:

- `y` - разрешить один раз
- `s` - разрешить в текущей сессии
- `t` - запомнить навсегда
- `n` - отклонить

## Разработка

### Текущий статус

Реализованы базовые компоненты:
- Система настроек
- Система доверия команд
- Менеджер агентов
- Базовая система workflow
- Интерактивный CLI
- Базовые инструменты

### TODO

Сложные компоненты для будущей реализации:
- MCP интеграция
- LLM провайдеры (qwen-code, kiro-cli)
- LangGraph workflow с состояниями
- Система команд управления
- Автодополнение CLI

### Тестирование

```bash
# Базовый тест функциональности
python test_cli.py

# Запуск с отладкой
python cli.py --debug
```

### Добавление нового workflow

1. Создать YAML файл в `~/.flowcraft/workflows/`
2. Определить stages и roles
3. Workflow автоматически появится в списке

### Создание агента

```python
agent_manager.create_agent(
    name="my_agent",
    role="developer", 
    description="Мой агент",
    capabilities=["coding"],
    llm_model="qwen-code"
)
```
