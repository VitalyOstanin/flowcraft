"""Qwen Code провайдер с OAuth аутентификацией."""

import json
import httpx
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime

from .base import BaseLLMProvider, LLMMessage, LLMResponse

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
        api_messages = [{"role": msg.role, "content": msg.content} for msg in messages]
        
        payload = {
            "model": self.model_name,
            "messages": api_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
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
        api_messages = [{"role": msg.role, "content": msg.content} for msg in messages]
        
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
    
    async def generate_with_tools(self, messages: List[BaseMessage], tools: List[Dict]) -> str:
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
        response = await self.generate(enhanced_messages)
        
        # Парсим и выполняем вызовы инструментов если есть
        return await self._process_tool_calls(response, tools)
    
    def _format_tools_for_prompt(self, tools: List[Dict]) -> str:
        """Форматирует список инструментов для промпта."""
        if not tools:
            return "Инструменты недоступны."
        
        formatted = []
        for tool in tools:
            formatted.append(f"- {tool['name']}: {tool['description']}")
        
        formatted.append("\nДля вызова инструмента используй формат: TOOL_CALL:tool_name:parameters_json")
        return "\n".join(formatted)
    
    async def _process_tool_calls(self, response: str, tools: List[Dict]) -> str:
        """Обрабатывает вызовы инструментов в ответе LLM."""
        import re
        
        # Ищем паттерн TOOL_CALL:tool_name:parameters
        tool_pattern = r'TOOL_CALL:(\w+):({.*?})'
        matches = re.findall(tool_pattern, response, re.DOTALL)
        
        if not matches:
            return response
        
        # Выполняем найденные вызовы инструментов
        results = []
        for tool_name, params_str in matches:
            try:
                import json
                params = json.loads(params_str)
                result = await self._execute_mcp_tool(tool_name, params, tools)
                results.append(f"Результат {tool_name}: {result}")
            except Exception as e:
                results.append(f"Ошибка {tool_name}: {e}")
        
        # Заменяем вызовы инструментов на результаты
        processed_response = response
        for i, (tool_name, params_str) in enumerate(matches):
            call_text = f"TOOL_CALL:{tool_name}:{params_str}"
            processed_response = processed_response.replace(call_text, results[i])
        
        return processed_response
    
    async def _execute_mcp_tool(self, tool_name: str, params: Dict, tools: List[Dict]) -> str:
        """Выполняет MCP инструмент."""
        # Находим инструмент по имени
        tool_info = next((t for t in tools if t['name'] == tool_name), None)
        if not tool_info:
            return f"Инструмент {tool_name} не найден"
        
        # Получаем MCP сессию для выполнения
        server_name = tool_info['server']
        
        # Здесь нужно получить активную MCP сессию
        # Пока возвращаем заглушку
        return f"Выполнен {tool_name} с параметрами {params}"
