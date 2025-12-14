# Менеджер агентов для FlowCraft - Резюме изменений

## Добавленные компоненты

### 1. Класс Agent и AgentManager
- **Agent** - dataclass с полями: name, role, description, capabilities, llm_model, status, workflow_enabled
- **AgentManager** - полный CRUD для агентов с сохранением в settings.yaml
- **AgentStatus** - enum для статусов (enabled/disabled)

### 2. CRUD операции
- `create_agent()` - создание нового агента
- `get_agent()` - получение агента по имени  
- `update_agent()` - обновление свойств агента
- `delete_agent()` - удаление агента
- `list_agents()` - список агентов с фильтрацией

### 3. Управление включением/отключением
- `enable_agent_globally()` - глобальное включение
- `disable_agent_globally()` - глобальное отключение (очищает все workflow)
- `enable_agent_for_workflow()` - включение для конкретного workflow
- `disable_agent_for_workflow()` - отключение для конкретного workflow
- `get_enabled_agents_for_workflow()` - получение активных агентов

### 4. Команды CLI
```bash
/agent create <name> --role <role> --desc "<description>" --model <llm_model>
/agent list [--status enabled|disabled]
/agent show <name>
/agent update <name> --role <role> --desc "<desc>"
/agent delete <name>
/agent enable <name> [--workflow <workflow>]
/agent disable <name> [--workflow <workflow>]
```

### 5. LLM-инициированные команды
LLM может предлагать создание и управление агентами с подтверждением пользователя:
```
USER: нужен агент для код-ревью
LLM: Предлагаю создать агента:
     /agent create code-reviewer --role "Code Reviewer" --desc "Анализ кода" --model qwen3-coder-plus
     Подтвердить создание? [y/n/modify]
```

### 6. Интеграция с workflow
- Агенты интегрируются в workflow через `get_enabled_agents_for_workflow()`
- Workflow может использовать специализированных агентов для конкретных задач
- Автоматический выбор LLM модели на основе настроек агента

## Архитектурные изменения

### Структура проекта
```
src/agents/manager.py  # Новый файл с AgentManager
```

### Обновленные файлы
- `flowcraft-architecture.md` - добавлен раздел "Менеджер агентов"
- Команды CLI расширены поддержкой `/agent`
- InteractiveCLI получил agent_manager и обработчик команд
- Автодополнение команд включает `/agent`

### Пример конфигурации
Создан `agents-example.yaml` с примерами агентов:
- code-reviewer (Code Reviewer)
- security-analyst (Security Analyst) 
- test-engineer (Test Engineer)
- devops-engineer (DevOps Engineer)
- documentation-writer (Documentation Writer)
- performance-analyst (Performance Analyst)

## Ключевые особенности

1. **Гибкое управление** - агенты можно включать/отключать глобально и по workflow
2. **Персистентность** - настройки сохраняются в settings.yaml
3. **LLM интеграция** - LLM может предлагать команды управления агентами
4. **Безопасность** - глобально отключенные агенты нельзя включить в workflow
5. **Модульность** - агенты легко добавлять/удалять без изменения кода workflow

## Преимущества

- **Динамическое управление** - изменение состава агентов без перезапуска
- **Специализация** - разные агенты для разных ролей и задач
- **Оптимизация ресурсов** - включение только нужных агентов
- **Гибкость workflow** - разные наборы агентов для разных сценариев
- **Простота использования** - интуитивные команды CLI с поддержкой LLM
