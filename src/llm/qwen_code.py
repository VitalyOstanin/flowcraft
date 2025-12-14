"""Qwen Code провайдер с OAuth аутентификацией."""

import json
import httpx
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime

from .base import BaseLLMProvider, LLMMessage, LLMResponse


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
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.OAUTH_TOKEN_ENDPOINT,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
                content=body,
                timeout=30.0,
            )
            
            if not response.is_success:
                error_text = await response.aread()
                raise ValueError(f"Ошибка обновления токена: {response.status_code} - {error_text}")
            
            token_data = response.json()
            
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
        
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
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
                usage = result.get("usage")
                
                return LLMResponse(content=content, usage=usage)
                
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
