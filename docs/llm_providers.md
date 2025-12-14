# LLM Провайдеры FlowCraft

## Содержание

1. [Обзор](#обзор)
2. [Qwen3 Coder Plus](#qwen3-coder-plus)
3. [Настройка](#настройка)
4. [Использование](#использование)
5. [Разработка новых провайдеров](#разработка-новых-провайдеров)

## Обзор

FlowCraft поддерживает различные LLM провайдеры для выполнения задач разной сложности. Система автоматически выбирает подходящую модель в зависимости от типа задачи.

### Типы моделей

- **Дешевая модель** - используется для простых задач (кодирование, базовый анализ)
- **Дорогая модель** - используется для сложных задач (архитектурный дизайн, security review)

## Qwen3 Coder Plus

Основной провайдер для задач программирования с поддержкой OAuth аутентификации.

### Особенности

- Модель: qwen3-coder-plus
- Контекст: 1M токенов
- OAuth аутентификация
- Автоматическое обновление токенов
- Поддержка streaming режима

### Установка

```bash
# Установка CLI утилиты
npm install -g @qwen-code/qwen-code@latest
```

### Аутентификация

OAuth credentials создаются через CLI утилиту qwen-code и сохраняются в `~/.qwen/oauth_creds.json`.

## Настройка

### Конфигурация в settings.yaml

```yaml
llm:
  cheap_model: qwen3-coder-plus
  expensive_model: kiro-cli
  expensive_stages:
    - security_review
    - architecture_design
    - complex_debugging
  # Опционально: кастомный путь к OAuth credentials
  qwen_oauth_path: ~/.qwen/oauth_creds.json
```

### Этапы для дорогой модели

Следующие этапы workflow автоматически используют дорогую модель:
- `security_review` - анализ безопасности
- `architecture_design` - архитектурное проектирование
- `complex_debugging` - сложная отладка

## Использование

### Программный интерфейс

```python
from llm.integration import LLMIntegration
from llm.base import LLMMessage
from core.settings import SettingsManager

# Инициализация
settings_manager = SettingsManager()
llm = LLMIntegration(settings_manager)

# Создание сообщений
messages = [
    LLMMessage(role="system", content="Ты помощник программиста."),
    LLMMessage(role="user", content="Напиши функцию сортировки.")
]

# Обычный запрос (дешевая модель)
response = await llm.chat_completion(messages)

# Запрос для сложной задачи (дорогая модель)
response = await llm.chat_completion(messages, stage_name="architecture_design")

# Streaming режим
async for chunk in llm.stream_completion(messages):
    print(chunk, end="")
```

### Информация о модели

```python
# Получить информацию о текущей модели
info = llm.get_current_model_info("coding")
print(f"Провайдер: {info['provider']}")
print(f"Модель: {info['model']}")
print(f"Тип: {info['type']}")
```

## Разработка новых провайдеров

### Базовый класс

Все провайдеры должны наследоваться от `BaseLLMProvider`:

```python
from llm.base import BaseLLMProvider, LLMMessage, LLMResponse

class MyProvider(BaseLLMProvider):
    @property
    def provider_name(self) -> str:
        return "my-provider"
    
    async def chat_completion(self, messages, **kwargs) -> LLMResponse:
        # Реализация
        pass
    
    async def stream_completion(self, messages, **kwargs):
        # Реализация streaming
        pass
```

### Регистрация провайдера

```python
from llm.factory import LLMProviderFactory

LLMProviderFactory.register_provider("my-provider", MyProvider)
```

### Обработка ошибок

Провайдеры должны обрабатывать:
- Ошибки аутентификации (401)
- Превышение лимитов (429)
- Сетевые ошибки
- Истечение токенов

### Автоматическое обновление токенов

Для OAuth провайдеров рекомендуется реализовать автоматическое обновление токенов при получении ошибки 401.

## Тестирование

### Простой тест

```bash
python test_qwen_simple.py
```

### Полный тест

```bash
python test_qwen_integration.py
```

### Проверка настроек

```python
from core.settings import SettingsManager

settings = SettingsManager()
print(f"Дешевая модель: {settings.settings.llm.cheap_model}")
print(f"Дорогая модель: {settings.settings.llm.expensive_model}")
```
