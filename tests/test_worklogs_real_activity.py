"""
Интеграционный тест для реальной активности в YouTrack
"""

import pytest
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from workflows.manager import WorkflowManager
from workflows.engine import WorkflowEngine
from agents.manager import AgentManager
from core.trust import TrustManager
from core.settings import SettingsManager
from mcp_integration.manager import MCPManager


@pytest.mark.asyncio
async def test_real_youtrack_activity():
    """Тест реальной активности в YouTrack за последние 7 дней"""
    
    print("Инициализация компонентов с MCP...")
    settings_manager = SettingsManager()
    agent_manager = AgentManager(settings_manager)
    trust_manager = TrustManager(settings_manager)
    
    # Инициализируем MCP менеджер и запускаем YouTrack сервер
    mcp_manager = MCPManager(settings_manager.settings)
    await mcp_manager.start_server('youtrack-mcp')
    
    try:
        # Проверяем подключение к YouTrack
        print("Проверка подключения к YouTrack...")
        youtrack_tools = mcp_manager.get_available_tools('worklogs')
        youtrack_tool_names = [tool for tool in youtrack_tools if 'youtrack' in tool]
        print(f"Доступные YouTrack инструменты: {len(youtrack_tool_names)}")
        
        # Получаем текущего пользователя
        if 'youtrack-mcp.user_current' in youtrack_tools:
            user_result = await mcp_manager.call_tool('youtrack-mcp.user_current', {})
            current_user = user_result.get('login', 'неизвестно')
            print(f"Текущий пользователь: {current_user}")
        
        # Ищем активность за последние 7 дней
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        print(f"Поиск активности с {start_date.strftime('%Y-%m-%d')} по {end_date.strftime('%Y-%m-%d')}")
        
        # Ищем issues обновленные за период
        if 'youtrack-mcp.issues_search' in youtrack_tools:
            search_params = {
                'query': f'updated: {start_date.strftime("%Y-%m-%d")} .. {end_date.strftime("%Y-%m-%d")}',
                'limit': 20
            }
            
            issues_result = await mcp_manager.call_tool('youtrack-mcp.issues_search', search_params)
            issues = issues_result.get('issues', [])
            
            print(f"Найдено issues за период: {len(issues)}")
            
            if issues:
                print("\n--- Активность в issues ---")
                for issue in issues[:5]:  # Показываем первые 5
                    print(f"• {issue.get('idReadable', 'N/A')}: {issue.get('summary', 'Без названия')}")
                    print(f"  Обновлено: {issue.get('updated', 'неизвестно')}")
                    if issue.get('assignee'):
                        assignee = issue['assignee']
                        print(f"  Исполнитель: {assignee.get('name', assignee.get('login', 'неизвестно'))}")
            
        # Получаем work items за период
        if 'youtrack-mcp.workitems_list' in youtrack_tools:
            workitems_params = {
                'startDate': start_date.strftime('%Y-%m-%d'),
                'endDate': end_date.strftime('%Y-%m-%d')
            }
            
            workitems_result = await mcp_manager.call_tool('youtrack-mcp.workitems_list', workitems_params)
            workitems = workitems_result.get('workItems', [])
            
            print(f"\nНайдено work items за период: {len(workitems)}")
            
            if workitems:
                total_minutes = sum(item.get('duration', {}).get('minutes', 0) for item in workitems)
                total_hours = total_minutes / 60
                
                print(f"Общее время работы: {total_hours:.1f} часов ({total_minutes} минут)")
                
                print("\n--- Work Items ---")
                for item in workitems[:5]:  # Показываем первые 5
                    issue_info = item.get('issue', {})
                    duration = item.get('duration', {})
                    
                    print(f"• {issue_info.get('idReadable', 'N/A')}: {item.get('text', 'Без описания')}")
                    print(f"  Дата: {item.get('date', 'неизвестно')}")
                    print(f"  Время: {duration.get('presentation', 'неизвестно')}")
        
        # Получаем starred issues (избранные)
        if 'youtrack-mcp.issues_starred_list' in youtrack_tools:
            starred_result = await mcp_manager.call_tool('youtrack-mcp.issues_starred_list', {'limit': 10})
            starred_issues = starred_result.get('issues', [])
            
            print(f"\nИзбранные issues: {len(starred_issues)}")
            
            if starred_issues:
                print("\n--- Избранные Issues ---")
                for issue in starred_issues[:3]:  # Показываем первые 3
                    print(f"* {issue.get('idReadable', 'N/A')}: {issue.get('summary', 'Без названия')}")
        
        print(f"\nАнализ активности завершен")
        
    finally:
        # Останавливаем MCP сервер
        await mcp_manager.stop_server('youtrack-mcp')


if __name__ == "__main__":
    # Запуск теста напрямую
    asyncio.run(test_real_youtrack_activity())
