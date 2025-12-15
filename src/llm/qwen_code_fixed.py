"""
Исправленная версия QwenCodeProvider с архитектурой qwen-code для tool calls.
"""

from typing import List, Dict, Any
from langchain_core.messages import BaseMessage, SystemMessage, AIMessage, HumanMessage
import logging

logger = logging.getLogger(__name__)

class QwenCodeProviderFixed:
    """Исправленная версия с правильной обработкой tool calls."""
    
    def __init__(self):
        self.model_name = "qwen3-coder-plus"
    
    async def chat_completion_with_tool_accumulation(self, messages: List[BaseMessage], tools: List[Dict] = None, mcp_sessions: Dict[str, Any] = None, max_iterations: int = 10) -> str:
        """
        Выполнение с накоплением результатов tool calls по архитектуре qwen-code.
        """
        logger.info("=== CHAT_COMPLETION_WITH_TOOL_ACCUMULATION ===")
        
        if not tools or not mcp_sessions:
            # Импортируем оригинальный провайдер для fallback
            from .qwen_code import QwenCodeProvider
            provider = QwenCodeProvider()
            response = await provider.chat_completion(messages)
            return response.content
        
        # Создаем накопитель для результатов
        from .tool_accumulator import ToolCallAccumulator
        accumulator = ToolCallAccumulator()
        
        current_messages = messages.copy()
        
        for iteration in range(max_iterations):
            logger.info(f"=== ИТЕРАЦИЯ {iteration + 1}/{max_iterations} ===")
            
            # Добавляем описание инструментов в system message
            enhanced_messages = []
            tools_description = self._format_tools_for_prompt(tools)
            
            for msg in current_messages:
                if isinstance(msg, SystemMessage):
                    enhanced_content = f"{msg.content}\n\nДоступные инструменты:\n{tools_description}"
                    enhanced_messages.append(SystemMessage(content=enhanced_content))
                else:
                    enhanced_messages.append(msg)
            
            # Генерируем ответ через оригинальный провайдер
            from .qwen_code import QwenCodeProvider
            provider = QwenCodeProvider()
            response = await provider.chat_completion(enhanced_messages)
            
            logger.info(f"=== LLM ОТВЕТ ИТЕРАЦИЯ {iteration + 1} ===")
            logger.info(f"Полный ответ: {response.content}")
            
            # Парсим tool calls
            tool_calls = self._extract_tool_calls_from_json(response.content)
            
            if not tool_calls:
                logger.info("Tool calls не найдены в ответе")
                break
            
            # Добавляем ответ LLM в контекст
            current_messages.append(AIMessage(content=response.content))
            
            # Выполняем tool calls и собираем результаты
            tool_results = []
            for tool_call in tool_calls:
                tool_name = tool_call['name']
                server_name = tool_call.get('server', 'unknown')
                full_name = tool_call.get('full_name', tool_name)
                params = tool_call['parameters']
                
                logger.info(f"Выполнение tool call: {full_name}")
                try:
                    result = await self._execute_mcp_tool_with_server(tool_name, server_name, params, tools, mcp_sessions)
                    accumulator.add_tool_call(full_name, params, result)
                    tool_results.append(f"Результат {full_name}: {result}")
                except Exception as e:
                    error_msg = f"Ошибка {full_name}: {e}"
                    logger.error(error_msg)
                    accumulator.add_tool_call(full_name, params, error_msg)
                    tool_results.append(error_msg)
            
            # Добавляем результаты tool calls как user message (как в qwen-code)
            if tool_results:
                tool_results_content = "\n".join(tool_results)
                current_messages.append(HumanMessage(content=tool_results_content))
                logger.info(f"Добавлены результаты tool calls: {tool_results_content[:200]}...")
            
            # Проверяем, нужно ли продолжать
            if not self._should_continue_execution(response.content, accumulator):
                break
        
        # Возвращаем финальный результат
        return accumulator.get_summary()
    
    def _format_tools_for_prompt(self, tools: List[Dict]) -> str:
        """Форматирует краткий список инструментов для LLM."""
        if not tools:
            return "Инструменты недоступны."
        
        # Группируем инструменты по серверам
        servers = {}
        for tool in tools:
            name = tool['name']
            if '.' in name:
                server, tool_name = name.split('.', 1)
                if server not in servers:
                    servers[server] = []
                servers[server].append(tool_name)
        
        # Форматируем вывод с примером использования
        lines = []
        for server, tool_names in servers.items():
            tools_str = ", ".join(tool_names)
            lines.append(f"- {server}: {tools_str}")
        
        lines.append("\nДля вызова инструмента используй JSON формат:")
        lines.append('{"tool_calls": [{"name": "youtrack-mcp.user_current", "parameters": {}}]}')
        
        return "\n".join(lines)
    
    def _extract_tool_calls_from_json(self, response: str) -> List[Dict]:
        """Извлекает tool calls из различных форматов ответа."""
        import json
        import re
        
        tool_calls = []
        
        # Формат 1: JSON с tool_calls
        json_pattern = r'\{"tool_calls":\s*\[.*?\]\}'
        matches = re.findall(json_pattern, response, re.DOTALL)
        
        for match in matches:
            try:
                data = json.loads(match)
                if 'tool_calls' in data:
                    for call in data['tool_calls']:
                        name = call.get('name', '')
                        if '.' in name:
                            server, tool_name = name.split('.', 1)
                        else:
                            server = 'unknown'
                            tool_name = name
                        
                        tool_calls.append({
                            'name': tool_name,
                            'server': server,
                            'full_name': name,
                            'parameters': call.get('parameters', {}),
                            'original_text': match
                        })
            except json.JSONDecodeError:
                continue
        
        # Формат 2: OpenAI function call format
        function_pattern = r'\[?\{"id":"[^"]+","function":\{"arguments":"[^"]*","name":"([^"]+)"\},"type":"function"[^\}]*\}\]?'
        matches = re.findall(function_pattern, response)
        
        for match in matches:
            name = match
            if ':' in name:
                # Формат "youtrack-mcp: user_current"
                server, tool_name = name.split(':', 1)
                server = server.strip()
                tool_name = tool_name.strip()
            elif '.' in name:
                server, tool_name = name.split('.', 1)
            else:
                server = 'unknown'
                tool_name = name
            
            tool_calls.append({
                'name': tool_name,
                'server': server,
                'full_name': f"{server}.{tool_name}",
                'parameters': {},
                'original_text': match
            })
        
        return tool_calls
    
    async def _execute_mcp_tool_with_server(self, tool_name: str, server_name: str, params: Dict, tools: List[Dict], mcp_sessions: Dict[str, Any]) -> str:
        """Выполняет MCP tool через указанный сервер."""
        logger.info(f"=== ВЫПОЛНЕНИЕ MCP TOOL ===")
        logger.info(f"Tool: {tool_name}")
        logger.info(f"Server: {server_name}")
        logger.info(f"Params: {params}")
        
        if server_name not in mcp_sessions:
            raise ValueError(f"MCP сервер {server_name} не найден")
        
        session = mcp_sessions[server_name]
        
        try:
            result = await session.call_tool(tool_name, params)
            
            # Извлекаем текст из результата
            if hasattr(result, 'content') and result.content:
                content = result.content[0]
                if hasattr(content, 'text'):
                    return content.text
                else:
                    return str(content)
            else:
                return str(result)
                
        except Exception as e:
            logger.error(f"Инструмент {tool_name} на сервере {server_name} не найден")
            raise e
    
    def _should_continue_execution(self, response: str, accumulator: 'ToolCallAccumulator') -> bool:
        """Определяет, нужно ли продолжать выполнение."""
        # Проверяем количество выполненных операций
        executed_ops = accumulator.get_executed_operations()
        
        # Если выполнено меньше 3 операций, продолжаем
        if len(executed_ops) < 3:
            return True
        
        # Проверяем наличие ключевых слов завершения
        completion_keywords = ["завершен", "выполнен", "готов", "финальный"]
        if any(keyword in response.lower() for keyword in completion_keywords):
            return False
        
        return False
