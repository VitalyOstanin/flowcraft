"""
Класс для накопления результатов tool calls в итерационном выполнении.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime


class ToolCallAccumulator:
    """Накопитель результатов tool calls для итерационного выполнения."""
    
    def __init__(self):
        self.tool_calls: List[Dict[str, Any]] = []
        self.final_response: Optional[str] = None
        self.created_at = datetime.now()
    
    def add_tool_call(self, tool_name: str, parameters: Dict[str, Any], result: str) -> None:
        """Добавляет результат выполнения tool call."""
        self.tool_calls.append({
            'tool_name': tool_name,
            'parameters': parameters,
            'result': result,
            'timestamp': datetime.now(),
            'success': not result.startswith('ОШИБКА')
        })
    
    def add_final_response(self, response: str) -> None:
        """Добавляет финальный ответ LLM."""
        self.final_response = response
    
    def get_context_summary(self) -> str:
        """Возвращает краткое резюме накопленных результатов."""
        if not self.tool_calls:
            return ""
        
        summary_lines = []
        for i, call in enumerate(self.tool_calls, 1):
            status = "✅" if call['success'] else "❌"
            summary_lines.append(
                f"{i}. {status} {call['tool_name']}: {call['result'][:100]}..."
            )
        
        return "\n".join(summary_lines)
    
    def get_formatted_result(self) -> str:
        """Возвращает полный отформатированный результат."""
        if not self.tool_calls and not self.final_response:
            return "Нет результатов выполнения."
        
        result_parts = []
        
        # Добавляем результаты tool calls
        if self.tool_calls:
            result_parts.append("=== Выполненные операции ===")
            for i, call in enumerate(self.tool_calls, 1):
                status = "✅ Успешно" if call['success'] else "❌ Ошибка"
                result_parts.append(f"\n{i}. {call['tool_name']} - {status}")
                result_parts.append(f"   Параметры: {call['parameters']}")
                result_parts.append(f"   Результат: {call['result']}")
        
        # Добавляем финальный ответ
        if self.final_response:
            if result_parts:
                result_parts.append("\n\n=== Финальный анализ ===")
            result_parts.append(self.final_response)
        
        return "\n".join(result_parts)
    
    def get_successful_calls(self) -> List[Dict[str, Any]]:
        """Возвращает только успешные tool calls."""
        return [call for call in self.tool_calls if call['success']]
    
    def get_failed_calls(self) -> List[Dict[str, Any]]:
        """Возвращает только неудачные tool calls."""
        return [call for call in self.tool_calls if not call['success']]
    
    def has_errors(self) -> bool:
        """Проверяет наличие ошибок в выполнении."""
        return any(not call['success'] for call in self.tool_calls)
    
    def get_executed_operations(self) -> List[str]:
        """Возвращает список выполненных операций."""
        operations = []
        for call in self.tool_calls:
            # Извлекаем имя операции из полного имени tool
            tool_name = call['tool_name']
            if '.' in tool_name:
                operation = tool_name.split('.')[-1]
            else:
                operation = tool_name
            operations.append(operation)
        return operations
    
    def get_summary(self) -> str:
        """Возвращает краткое резюме для совместимости."""
        return self.get_formatted_result()
    
    def get_total_size(self) -> int:
        """Возвращает примерный размер накопленных данных в байтах."""
        total_size = 0
        for call in self.tool_calls:
            total_size += len(str(call['parameters'])) + len(call['result'])
        
        if self.final_response:
            total_size += len(self.final_response)
        
        return total_size
