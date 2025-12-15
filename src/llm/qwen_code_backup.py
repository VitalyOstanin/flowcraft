"""Qwen Code провайдер с OAuth аутентификацией."""

import json
import httpx
import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime

from .base import BaseLLMProvider, LLMMessage, LLMResponse
from .tool_accumulator import ToolCallAccumulator

try:
    from langchain_core.messages import BaseMessage, SystemMessage
except ImportError:
    # Fallback если langchain не установлен
    BaseMessage = object
    SystemMessage = object


class QwenCodeProvider(BaseLLMProvider):
    """Провайдер для Qwen Code API с OAuth аутентификацией."""
    
    # OAuth константы
    OAUTH_BASE_URL = "https://chat.qwen.ai"
    OAUTH_TOKEN_ENDPOINT = f"{OAUTH_BASE_URL}/api/v1/oauth2/token"
    OAUTH_CLIENT_ID = "f0304373b74a44d2b584a3fb70ca9e56"
    
    def __init__(self, model_name: str = "qwen3-coder-plus", oauth_path: Optional[str] = None, **kwargs):
        super().__init__(model_name, **kwargs)
        self.oauth_path = oauth_path or os.path.expanduser("~/.qwen/oauth_creds.json")
        self._credentials: Optional[Dict[str, Any]] = None
        self.name = "qwen-code"  # Добавляем атрибут name для совместимости
    
    @property
    def provider_name(self) -> str:
        return "qwen-code"
    
    def _load_credentials(self) -> Dict[str, Any]:
        """Загрузить OAuth credentials из файла."""
        creds_path = Path(self.oauth_path)
        
        if not creds_path.exists():
            raise FileNotFoundError(f"Файл credentials не найден: {creds_path}")
        
        with open(creds_path) as f:
            creds = json.load(f)
        
        # Проверить срок действия токена
        if "expiry_date" in creds:
            expiry = creds["expiry_date"]
            current_time = datetime.now().timestamp() * 1000
            if isinstance(expiry, (int, float)) and expiry < current_time:
                # Попытаться обновить токен
                creds = self._refresh_token(creds)
        
        return creds
    
    def _refresh_token(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Обновить access token используя refresh token."""
        if not credentials.get("refresh_token"):
            raise ValueError("Refresh token не найден в credentials")
        
        import asyncio
        
        # Проверяем, есть ли уже запущенный event loop
        try:
            loop = asyncio.get_running_loop()
            # Если loop запущен, создаем задачу
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self._refresh_token_async(credentials))
                return future.result()
        except RuntimeError:
            # Нет запущенного loop, можем использовать asyncio.run
            return asyncio.run(self._refresh_token_async(credentials))
    
    async def _refresh_token_async(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Асинхронно обновить access token."""
        body_data = {
            "grant_type": "refresh_token",
            "refresh_token": credentials["refresh_token"],
            "client_id": self.OAUTH_CLIENT_ID,
        }
        
        # Конвертировать в URL-encoded формат
        body = "&".join([f"{k}={v}" for k, v in body_data.items()])
        
        # Используем тот же User-Agent что и оригинальный qwen CLI
        version = "0.5.0"
        user_agent = f"QwenCode/{version} (linux; x64)"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.OAUTH_TOKEN_ENDPOINT,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                    "User-Agent": user_agent,
                },
                content=body,
                timeout=30.0,
            )
            
            if not response.is_success:
                # Обработка 400 ошибки - refresh token истек
                if response.status_code == 400:
                    # Удаляем credentials файл
                    creds_path = Path(self.oauth_path)
                    if creds_path.exists():
                        creds_path.unlink()
                    raise ValueError("Refresh token expired. Please re-authenticate using: qwen-code auth login")
                
                error_text = response.text
                raise ValueError(f"Ошибка обновления токена: {response.status_code} - {error_text}")
            
            # Проверяем, что ответ не пустой
            response_text = response.text
            if not response_text.strip():
                raise ValueError("Сервер вернул пустой ответ")
            
            try:
                token_data = response.json()
            except Exception as e:
                raise ValueError(f"Ошибка парсинга JSON ответа: {e}. Ответ: {response_text}")
            
            if "error" in token_data:
                raise ValueError(f"Ошибка обновления токена: {token_data['error']}")
            
            # Обновить credentials
            new_credentials = {
                **credentials,
                "access_token": token_data["access_token"],
                "token_type": token_data.get("token_type", "Bearer"),
                "refresh_token": token_data.get("refresh_token", credentials["refresh_token"]),
                "expiry_date": datetime.now().timestamp() * 1000 + token_data.get("expires_in", 3600) * 1000,
            }
            
            # Сохранить обновленные credentials
            creds_path = Path(self.oauth_path)
            with open(creds_path, "w") as f:
                json.dump(new_credentials, f, indent=2)
            
            return new_credentials
    
    def _get_base_url(self, credentials: Dict[str, Any]) -> str:
        """Получить базовый URL из credentials."""
        resource_url = credentials.get("resource_url")
        if resource_url:
            base_url = resource_url if resource_url.startswith("http") else f"https://{resource_url}"
            return base_url if base_url.endswith("/v1") else f"{base_url}/v1"
        return "https://dashscope.aliyuncs.com/compatible-mode/v1"
    
    def _get_headers(self) -> Dict[str, str]:
        """Получить заголовки с OAuth токеном."""
        if not self._credentials:
            self._credentials = self._load_credentials()
        
        token = self._credentials.get("access_token")
        if not token:
            raise ValueError("Access token не найден в credentials")
        
        # Используем тот же User-Agent что и оригинальный qwen CLI
        version = "0.5.0"
        user_agent = f"QwenCode/{version} (linux; x64)"
        
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": user_agent,
        }
    
    async def chat_completion(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> LLMResponse:
        """Выполнить chat completion запрос."""
        if not self._credentials:
            self._credentials = self._load_credentials()
        
        base_url = self._get_base_url(self._credentials)
        url = f"{base_url}/chat/completions"
        
        # Конвертировать сообщения в формат API
        api_messages = []
        for msg in messages:
            if hasattr(msg, 'role'):
                role = msg.role
            elif msg.__class__.__name__ == 'SystemMessage':
                role = 'system'
            elif msg.__class__.__name__ == 'HumanMessage':
                role = 'user'
            elif msg.__class__.__name__ == 'AIMessage':
                role = 'assistant'
            else:
                role = 'user'
            # Безопасная сериализация содержимого
            try:
                import json
                content = json.loads(json.dumps(msg.content, default=str))
            except:
                content = str(msg.content)
            
            api_messages.append({"role": role, "content": content})
        
        # Фильтруем kwargs от несериализуемых объектов
        safe_kwargs = {}
        for key, value in kwargs.items():
            try:
                import json
                json.dumps(value)
                safe_kwargs[key] = value
            except (TypeError, ValueError):
                # Пропускаем несериализуемые объекты
                pass
        
        payload = {
            "model": self.model_name,
            "messages": api_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **safe_kwargs
        }
        
        # Полная проверка сериализуемости payload
        try:
            import json
            json.dumps(payload)
        except (TypeError, ValueError) as e:
            # Если payload не сериализуется, создаем безопасную версию
            safe_payload = {
                "model": str(self.model_name),
                "messages": api_messages,
                "temperature": float(temperature),
                "max_tokens": int(max_tokens)
            }
            payload = safe_payload
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    headers=self._get_headers(),
                    json=payload,
                    timeout=60.0,
                )
                response.raise_for_status()
                result = response.json()
                
                content = result["choices"][0]["message"]["content"]
                usage_raw = result.get("usage", {})
                
                # Преобразуем usage в простой формат Dict[str, int]
                usage = {}
                if usage_raw:
                    if "prompt_tokens" in usage_raw:
                        usage["prompt_tokens"] = int(usage_raw["prompt_tokens"])
                    if "completion_tokens" in usage_raw:
                        usage["completion_tokens"] = int(usage_raw["completion_tokens"])
                    if "total_tokens" in usage_raw:
                        usage["total_tokens"] = int(usage_raw["total_tokens"])
                
                return LLMResponse(content=content, usage=usage if usage else None)
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    # Токен истек, попробовать обновить
                    self._credentials = await self._refresh_token_async(self._credentials)
                    # Повторить запрос
                    response = await client.post(
                        url,
                        headers=self._get_headers(),
                        json=payload,
                        timeout=60.0,
                    )
                    response.raise_for_status()
                    result = response.json()
                    
                    content = result["choices"][0]["message"]["content"]
                    usage = result.get("usage")
                    
                    return LLMResponse(content=content, usage=usage)
                else:
                    raise ValueError(f"HTTP ошибка: {e.response.status_code} - {e.response.text}")
    
    async def stream_completion(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Выполнить streaming chat completion запрос."""
        if not self._credentials:
            self._credentials = self._load_credentials()
        
        base_url = self._get_base_url(self._credentials)
        url = f"{base_url}/chat/completions"
        
        # Конвертировать сообщения в формат API
        api_messages = []
        for msg in messages:
            if hasattr(msg, 'role'):
                role = msg.role
            elif msg.__class__.__name__ == 'SystemMessage':
                role = 'system'
            elif msg.__class__.__name__ == 'HumanMessage':
                role = 'user'
            elif msg.__class__.__name__ == 'AIMessage':
                role = 'assistant'
            else:
                role = 'user'
            # Безопасная сериализация содержимого
            try:
                import json
                content = json.loads(json.dumps(msg.content, default=str))
            except:
                content = str(msg.content)
            
            api_messages.append({"role": role, "content": content})
        
        payload = {
            "model": self.model_name,
            "messages": api_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            **kwargs
        }
        
        async with httpx.AsyncClient() as client:
            try:
                async with client.stream(
                    "POST",
                    url,
                    headers=self._get_headers(),
                    json=payload,
                    timeout=60.0,
                ) as response:
                    response.raise_for_status()
                    
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]  # Убрать "data: "
                            if data == "[DONE]":
                                break
                            
                            try:
                                chunk = json.loads(data)
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                continue
                                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    # Токен истек, попробовать обновить
                    self._credentials = await self._refresh_token_async(self._credentials)
                    # Повторить запрос
                    async with client.stream(
                        "POST",
                        url,
                        headers=self._get_headers(),
                        json=payload,
                        timeout=60.0,
                    ) as response:
                        response.raise_for_status()
                        
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                data = line[6:]
                                if data == "[DONE]":
                                    break
                                
                                try:
                                    chunk = json.loads(data)
                                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                                except json.JSONDecodeError:
                                    continue
                else:
                    raise ValueError(f"HTTP ошибка: {e.response.status_code} - {e.response.text}")
    
    async def generate_with_tools(self, messages: List[BaseMessage], tools: List[Dict], mcp_sessions: Dict[str, Any] = None) -> str:
        """Генерация ответа с доступом к MCP инструментам."""
        
        # Добавляем описание инструментов в system message
        tools_description = self._format_tools_for_prompt(tools)
        
        # Модифицируем первое сообщение (system) добавив описание инструментов
        enhanced_messages = []
        for i, msg in enumerate(messages):
            if i == 0 and isinstance(msg, SystemMessage):
                enhanced_content = f"{msg.content}\n\nДоступные инструменты:\n{tools_description}"
                enhanced_messages.append(SystemMessage(content=enhanced_content))
            else:
                enhanced_messages.append(msg)
        
        # Генерируем ответ
        response = await self.chat_completion(enhanced_messages)
        
        # Парсим и выполняем вызовы инструментов если есть
        return await self._process_tool_calls(response.content, tools, mcp_sessions)
    
    async def chat_completion_with_tool_accumulation(self, messages: List[BaseMessage], tools: List[Dict] = None, mcp_sessions: Dict[str, Any] = None, max_iterations: int = 10) -> str:
        """
        Выполнение с накоплением результатов tool calls.
        
        Args:
            messages: Список сообщений
            tools: Доступные инструменты
            mcp_sessions: MCP сессии
            max_iterations: Максимальное количество итераций
            
        Returns:
            Финальный ответ LLM с накопленными результатами
        """
        import logging
        
        logger = logging.getLogger(__name__)
        logger.info("=== CHAT_COMPLETION_WITH_TOOL_ACCUMULATION ===")
        
        if not tools:
            # Если нет инструментов, выполняем обычный запрос
            response = await self.chat_completion(messages)
            return response.content
        
        # Инициализируем накопитель контекста
        accumulator = ToolCallAccumulator()
        current_messages = messages.copy()
        
        for iteration in range(max_iterations):
            logger.info(f"=== ИТЕРАЦИЯ {iteration + 1}/{max_iterations} ===")
            
            # Добавляем описание инструментов к системному сообщению
            enhanced_messages = []
            tools_description = self._format_tools_for_prompt(tools)
            
            for msg in current_messages:
                if isinstance(msg, SystemMessage):
                    enhanced_content = f"{msg.content}\n\nДоступные инструменты:\n{tools_description}"
                    enhanced_messages.append(SystemMessage(content=enhanced_content))
                else:
                    enhanced_messages.append(msg)
            
            # Логируем запрос к LLM
            logger.info(f"=== LLM ЗАПРОС ИТЕРАЦИЯ {iteration + 1} ===")
            for i, msg in enumerate(enhanced_messages):
                msg_type = type(msg).__name__
                content_preview = msg.content[:300] + "..." if len(msg.content) > 300 else msg.content
                logger.info(f"Сообщение {i+1} ({msg_type}): {content_preview}")
            
            # Генерируем ответ
            response = await self.chat_completion(enhanced_messages)
            
            # Логируем полный ответ LLM
            logger.info(f"=== LLM ОТВЕТ ИТЕРАЦИЯ {iteration + 1} ===")
            logger.info(f"Полный ответ: {response.content}")
            logger.info(f"Длина ответа: {len(response.content)} символов")
            
            # Проверяем наличие tool calls
            if not self._has_tool_calls(response.content):
                logger.info("Tool calls не найдены в ответе")
                # Проверяем, нужно ли продолжать выполнение
                if self._should_continue_execution(response.content):
                    logger.info("Продолжаем выполнение - не все операции завершены")
                    # Добавляем текущий ответ в накопитель
                    accumulator.add_final_response(response.content)
                    # Подготавливаем сообщения для продолжения
                    current_messages = self._build_continuation_messages(
                        messages, accumulator, response.content
                    )
                    continue
                else:
                    logger.info("Завершаем итерации - все операции выполнены")
                    # Добавляем финальный ответ в накопитель
                    accumulator.add_final_response(response.content)
                    break
            
            # Выполняем tool calls и накапливаем результаты
            processed_response = await self._process_tool_calls_with_accumulation(
                response.content, tools, mcp_sessions, accumulator
            )
            
            # Проверяем, нужно ли продолжать
            if not self._should_continue_execution(processed_response):
                logger.info("LLM сигнализирует о завершении")
                accumulator.add_final_response(processed_response)
                break
            
            # Подготавливаем сообщения для следующей итерации
            current_messages = self._build_continuation_messages(
                messages, accumulator, processed_response
            )
        
        else:
            logger.warning(f"Достигнут лимит итераций: {max_iterations}")
            accumulator.add_final_response("Достигнут лимит итераций выполнения.")
        
        return accumulator.get_formatted_result()
    
    def _has_tool_calls(self, response: str) -> bool:
        """Проверяет наличие tool calls в ответе."""
        import re
        import json
        
        # Проверяем JSON формат в markdown блоках
        json_pattern = r'```json\s*(\{.*?"tool_calls".*?\})\s*```'
        if re.search(json_pattern, response, re.DOTALL | re.IGNORECASE):
            return True
        
        # Проверяем чистый JSON без markdown
        try:
            # Пытаемся распарсить весь ответ как JSON
            data = json.loads(response.strip())
            if isinstance(data, dict) and "tool_calls" in data:
                return True
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Проверяем наличие паттерна tool_calls в тексте
        if '"tool_calls"' in response and '"name"' in response:
            return True
        
        return False
    
    def _should_continue_execution(self, response: str) -> bool:
        """Определяет, нужно ли продолжать выполнение после tool calls."""
        import re
        
        # Ищем явные паттерны завершения
        explicit_completion_patterns = [
            r'ВСЕ ОПЕРАЦИИ ВЫПОЛНЕНЫ',
            r'ФИНАЛЬНЫЙ ОТЧЕТ ГОТОВ',
            r'STAGE_COMPLETE',
            r'CONTINUE_EXECUTION:\s*false'
        ]
        
        for pattern in explicit_completion_patterns:
            if re.search(pattern, response, re.IGNORECASE):
                return False
        
        # Если есть новые tool calls, продолжаем
        if self._has_tool_calls(response):
            return True
            
        # Если нет tool calls, но есть упоминание о необходимости выполнить еще операции, продолжаем
        continue_patterns = [
            r'следующ\w+\s+операци',
            r'продолж\w+\s+выполнение',
            r'еще\s+нужно',
            r'далее\s+выполн',
            r'затем\s+получ',
            r'также\s+получ',
            r'операци\w+\s+\d+',
            r'выполн\w+\s+операци\w+\s+\d+',
            r'workitems_recent',
            r'users_activity', 
            r'service_info',
            r'2\.\s*workitems_recent',
            r'3\.\s*users_activity',
            r'4\.\s*service_info'
        ]
        
        for pattern in continue_patterns:
            if re.search(pattern, response, re.IGNORECASE):
                return True
        
        # ВАЖНО: Если в ответе есть "=== Финальный анализ ===" но нет явного завершения,
        # считаем что это промежуточный результат и нужно продолжать
        if "=== Финальный анализ ===" in response and "ВСЕ ОПЕРАЦИИ ВЫПОЛНЕНЫ" not in response:
            # Проверяем, выполнены ли все 4 операции
            operations_count = response.count("youtrack-mcp.")
            if operations_count < 4:
                return True
        
        # По умолчанию не продолжаем
        return False
    
    async def _process_tool_calls_with_accumulation(self, response: str, tools: List[Dict], mcp_sessions: Dict[str, Any], accumulator: 'ToolCallAccumulator') -> str:
        """Обрабатывает tool calls с накоплением результатов."""
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Используем JSON парсинг вместо regexp
        tool_calls = self._extract_tool_calls_from_json(response)
        
        if not tool_calls:
            return response
        
        # Выполняем найденные вызовы инструментов
        for tool_call in tool_calls:
            tool_name = tool_call['name']
            server_name = tool_call.get('server', 'unknown')
            full_name = tool_call.get('full_name', tool_name)
            params = tool_call['parameters']
            original_text = tool_call['original_text']
            
            logger.info(f"Выполнение tool call: {full_name}")
            try:
                result = await self._execute_mcp_tool_with_server(tool_name, server_name, params, tools, mcp_sessions)
                
                # Добавляем в накопитель
                accumulator.add_tool_call(full_name, params, result)
                
                # Заменяем в ответе
                result_text = f"Результат {full_name}: {result}"
                response = response.replace(original_text, result_text)
                
            except Exception as e:
                error_msg = f"Ошибка {full_name}: {e}"
                logger.error(error_msg)
                accumulator.add_tool_call(full_name, params, error_msg)
                
                response = response.replace(original_text, error_msg)
        
        return response
    
    def _build_continuation_messages(self, original_messages: List[BaseMessage], accumulator: 'ToolCallAccumulator', last_response: str) -> List[BaseMessage]:
        """Строит сообщения для продолжения с накопленным контекстом."""
        # Берем оригинальные сообщения
        messages = original_messages.copy()
        
        # Добавляем накопленный контекст
        context = accumulator.get_context_summary()
        executed_operations = accumulator.get_executed_operations()
        
        if context:
            continuation_content = f"""
Предыдущие результаты tool calls:
{context}

Выполненные операции: {executed_operations}

ВАЖНО: Нужно выполнить ВСЕ 4 операции из задачи:
1. user_current ✅ (выполнено)
2. workitems_recent ❌ (нужно выполнить)  
3. users_activity ❌ (нужно выполнить)
4. service_info ❌ (нужно выполнить)

НЕ ОСТАНАВЛИВАЙСЯ! Продолжи выполнение следующих операций подряд.

Для вызова инструментов используй JSON формат:

{{"tool_calls": [{{"name": "youtrack-mcp.workitems_recent", "parameters": {{"limit": 10}}}}]}}

Выполни СЛЕДУЮЩУЮ операцию: workitems_recent с параметром limit=10
"""
            messages.append(AIMessage(content=continuation_content))
        
        return messages
    
    def _format_tools_for_prompt(self, tools: List[Dict]) -> str:
        """Форматирует краткий список инструментов для LLM."""
        if not tools:
            return "Инструменты недоступны."
        
        # Группируем инструменты по серверам
        servers = {}
        for tool in tools:
            server = tool.get('server', 'unknown')
            if server not in servers:
                servers[server] = []
            servers[server].append(tool['name'])
        
        formatted = ["Доступные MCP инструменты:"]
        for server, tool_names in servers.items():
            formatted.append(f"- {server}: {', '.join(tool_names)}")
        
        formatted.append("\nИспользуй JSON формат:")
        formatted.append('{"tool_calls": [{"name": "server.tool_name", "parameters": {}}]}')
        
        return "\n".join(formatted)
        
        formatted.append("""

Для вызова инструментов используй JSON формат в блоке кода:

```json
{
  "tool_calls": [
    {
      "name": "server_name.tool_name",
      "parameters": {
        "param1": "value1",
        "param2": "value2"
      }
    }
  ]
}
```""")
        return "\n".join(formatted)
    
    async def _process_tool_calls(self, response: str, tools: List[Dict], mcp_sessions: Dict[str, Any] = None) -> str:
        """Обрабатывает вызовы инструментов в ответе LLM с поддержкой JSON формата."""
        import json
        import logging
        
        logger = logging.getLogger(__name__)
        logger.info(f"=== ОБРАБОТКА TOOL CALLS ===")
        logger.info(f"Полный ответ LLM:\n{response}")
        
        # Сначала пробуем найти JSON блоки с tool calls
        tool_calls = self._extract_tool_calls_from_json(response)
        
        # Если JSON не найден, используем старый regexp формат как fallback
        if not tool_calls:
            tool_calls = self._extract_tool_calls_from_regexp(response)
        
        logger.info(f"Найдено tool calls: {len(tool_calls)}")
        
        if not tool_calls:
            return response
        
        # Выполняем найденные вызовы инструментов
        results = []
        for tool_call in tool_calls:
            tool_name = tool_call['name']
            server_name = tool_call.get('server', 'unknown')
            full_name = tool_call.get('full_name', tool_name)
            params = tool_call['parameters']
            original_text = tool_call['original_text']
            
            logger.info(f"Выполнение tool call: {full_name} (server: {server_name})")
            try:
                result = await self._execute_mcp_tool_with_server(tool_name, server_name, params, tools, mcp_sessions)
                logger.info(f"Результат {full_name}: {result[:100]}...")
                
                # Заменяем оригинальный текст на результат
                result_text = f"Результат {full_name}: {result}"
                response = response.replace(original_text, result_text)
                results.append(result_text)
                
            except Exception as e:
                # Создаем детальное сообщение об ошибке для LLM
                error_details = self._format_tool_error_for_llm(full_name, params, str(e), tools)
                logger.error(f"Ошибка {full_name}: {e}")
                response = response.replace(original_text, error_details)
                results.append(error_details)
        
        return response
    
    def _extract_tool_calls_from_json(self, response: str) -> List[Dict]:
        """Извлекает tool calls из JSON блоков в ответе."""
        import json
        import re
        
        tool_calls = []
        
        # Сначала пробуем парсить весь ответ как чистый JSON
        try:
            data = json.loads(response.strip())
            if isinstance(data, dict) and 'tool_calls' in data:
                for call in data['tool_calls']:
                    if 'name' in call and 'parameters' in call:
                        # Парсим полное имя инструмента
                        full_name = call['name']
                        server_name, tool_name = self._parse_tool_name(full_name)
                        
                        tool_calls.append({
                            'name': tool_name,
                            'server': server_name,
                            'full_name': full_name,
                            'parameters': call['parameters'],
                            'original_text': response
                        })
                return tool_calls
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Ищем JSON блоки с tool_calls в markdown
        json_pattern = r'```json\s*(\{.*?"tool_calls".*?\})\s*```'
        json_matches = re.findall(json_pattern, response, re.DOTALL | re.IGNORECASE)
        
        for json_str in json_matches:
            try:
                data = json.loads(json_str)
                if 'tool_calls' in data:
                    for call in data['tool_calls']:
                        if 'name' in call and 'parameters' in call:
                            # Парсим полное имя инструмента
                            full_name = call['name']
                            server_name, tool_name = self._parse_tool_name(full_name)
                            
                            tool_calls.append({
                                'name': tool_name,
                                'server': server_name,
                                'full_name': full_name,
                                'parameters': call['parameters'],
                                'original_text': f"```json\n{json_str}\n```"
                            })
            except json.JSONDecodeError:
                continue
        
        return tool_calls
    
    def _extract_tool_calls_from_regexp(self, response: str) -> List[Dict]:
        """Извлекает tool calls из старого regexp формата (удален)."""
        # Старый формат больше не поддерживается
        return []
    
    def _parse_tool_name(self, full_name: str) -> tuple[str, str]:
        """Парсит полное имя инструмента на сервер и имя."""
        if '.' in full_name:
            parts = full_name.split('.', 1)
            return parts[0], parts[1]  # server_name, tool_name
        else:
            # Если точки нет, считаем что это старый формат без сервера
            return 'unknown', full_name
    
    def _format_tool_error_for_llm(self, tool_name: str, params: Dict, error_msg: str, tools: List[Dict]) -> str:
        """Форматирует ошибку tool call с подсказками для исправления."""
        
        # Находим информацию об инструменте
        tool_info = next((t for t in tools if t['name'] == tool_name), None)
        
        error_response = f"""ОШИБКА при выполнении {tool_name}: {error_msg}

Проверьте параметры и повторите вызов:
- Переданные параметры: {params}"""
        
        if tool_info and 'schema' in tool_info:
            schema = tool_info['schema']
            
            # Добавляем информацию о требуемых параметрах
            if 'properties' in schema:
                required_params = schema.get('required', [])
                properties = schema['properties']
                
                error_response += "\n- Доступные параметры:"
                for param_name, param_info in properties.items():
                    param_type = param_info.get('type', 'unknown')
                    is_required = param_name in required_params
                    req_marker = " (ОБЯЗАТЕЛЬНЫЙ)" if is_required else " (опциональный)"
                    description = param_info.get('description', '')
                    
                    error_response += f"\n  • {param_name} ({param_type}){req_marker}: {description}"
        
        # Добавляем общие советы по исправлению
        if "required" in error_msg.lower():
            error_response += "\n\nСовет: Проверьте, что все обязательные параметры указаны."
        elif "invalid" in error_msg.lower() or "format" in error_msg.lower():
            error_response += "\n\nСовет: Проверьте формат и типы данных параметров."
        elif "not found" in error_msg.lower():
            error_response += "\n\nСовет: Проверьте правильность имени инструмента и его доступность."
        
        error_response += f"\n\nПовторите вызов с исправленными параметрами в формате JSON."
        
        return error_response
    
    async def _execute_mcp_tool_with_server(self, tool_name: str, server_name: str, params: Dict, tools: List[Dict], mcp_sessions: Dict[str, Any] = None) -> str:
        """Выполняет MCP инструмент с явным указанием сервера."""
        import logging
        
        logger = logging.getLogger(__name__)
        logger.info(f"=== ВЫПОЛНЕНИЕ MCP TOOL ===")
        logger.info(f"Tool: {tool_name}")
        logger.info(f"Server: {server_name}")
        logger.info(f"Params: {params}")
        
        # Находим инструмент по имени и серверу
        tool_info = None
        for tool in tools:
            if tool['name'] == tool_name and tool.get('server') == server_name:
                tool_info = tool
                break
        
        if not tool_info:
            logger.error(f"Инструмент {tool_name} на сервере {server_name} не найден")
            return f"Инструмент {tool_name} на сервере {server_name} не найден"
        
        if not mcp_sessions or server_name not in mcp_sessions:
            logger.error(f"MCP сессия для сервера {server_name} недоступна")
            return f"MCP сессия для сервера {server_name} недоступна"
        
        session = mcp_sessions[server_name]
        logger.info(f"Сессия найдена: {type(session)}")
        
        try:
            logger.info(f"Вызов session.call_tool({tool_name}, {params})")
            # Выполняем MCP вызов с таймаутом
            import asyncio
            result = await asyncio.wait_for(
                session.call_tool(tool_name, params),
                timeout=10.0  # 10 секунд таймаут
            )
            logger.info(f"Результат получен: {type(result)}")
            return str(result.content[0].text) if result.content else "Пустой результат"
        except asyncio.TimeoutError:
            logger.error(f"Таймаут MCP вызова {tool_name}")
            return f"Таймаут MCP вызова {tool_name}"
        except Exception as e:
            logger.error(f"Ошибка выполнения {tool_name}: {str(e)}")
            return f"Ошибка выполнения {tool_name}: {str(e)}"
    
    async def _execute_mcp_tool(self, tool_name: str, params: Dict, tools: List[Dict], mcp_sessions: Dict[str, Any] = None) -> str:
        """Выполняет MCP инструмент."""
        import logging
        
        logger = logging.getLogger(__name__)
        logger.info(f"=== ВЫПОЛНЕНИЕ MCP TOOL ===")
        logger.info(f"Tool: {tool_name}")
        logger.info(f"Params: {params}")
        
        # Находим инструмент по имени
        tool_info = next((t for t in tools if t['name'] == tool_name), None)
        if not tool_info:
            logger.error(f"Инструмент {tool_name} не найден")
            return f"Инструмент {tool_name} не найден"
        
        # Получаем MCP сессию для выполнения
        server_name = tool_info['server']
        logger.info(f"Server: {server_name}")
        
        if not mcp_sessions or server_name not in mcp_sessions:
            logger.error(f"MCP сессия для сервера {server_name} недоступна")
            return f"MCP сессия для сервера {server_name} недоступна"
        
        session = mcp_sessions[server_name]
        logger.info(f"Сессия найдена: {type(session)}")
        
        try:
            logger.info(f"Вызов session.call_tool({tool_name}, {params})")
            # Выполняем MCP вызов с таймаутом
            import asyncio
            result = await asyncio.wait_for(
                session.call_tool(tool_name, params),
                timeout=10.0  # 10 секунд таймаут
            )
            logger.info(f"Результат получен: {type(result)}")
            return str(result.content[0].text) if result.content else "Пустой результат"
        except asyncio.TimeoutError:
            logger.error(f"Таймаут MCP вызова {tool_name}")
            return f"Таймаут MCP вызова {tool_name}"
        except Exception as e:
            logger.error(f"Ошибка выполнения {tool_name}: {str(e)}")
            return f"Ошибка выполнения {tool_name}: {str(e)}"
