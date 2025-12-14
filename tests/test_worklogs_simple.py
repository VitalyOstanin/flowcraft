"""
Простой тест для получения реальной активности YouTrack
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


async def test_youtrack_direct():
    """Прямой вызов YouTrack инструментов"""
    
    try:
        # Импортируем YouTrack инструменты напрямую
        from youtrack_mcp import user_current, issues_search, workitems_list, issues_starred_list
        
        print("Получение текущего пользователя...")
        user_result = await user_current({})
        current_user = user_result.get('login', 'неизвестно')
        print(f"Текущий пользователь: {current_user}")
        
        # Период за последние 7 дней
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        print(f"\nПоиск активности с {start_date.strftime('%Y-%m-%d')} по {end_date.strftime('%Y-%m-%d')}")
        
        # Поиск обновленных issues
        print("\nПоиск обновленных issues...")
        search_params = {
            'query': f'updated: {start_date.strftime("%Y-%m-%d")} .. {end_date.strftime("%Y-%m-%d")}',
            'limit': 10
        }
        
        issues_result = await issues_search(search_params)
        issues = issues_result.get('issues', [])
        
        print(f"Найдено issues: {len(issues)}")
        
        if issues:
            print("\n--- Обновленные Issues ---")
            for issue in issues[:5]:
                print(f"• {issue.get('idReadable', 'N/A')}: {issue.get('summary', 'Без названия')}")
                print(f"  Обновлено: {issue.get('updated', 'неизвестно')}")
                if issue.get('assignee'):
                    assignee = issue['assignee']
                    print(f"  Исполнитель: {assignee.get('name', assignee.get('login', 'неизвестно'))}")
        
        # Получение work items
        print("\nПоиск work items...")
        workitems_params = {
            'startDate': start_date.strftime('%Y-%m-%d'),
            'endDate': end_date.strftime('%Y-%m-%d')
        }
        
        workitems_result = await workitems_list(workitems_params)
        workitems = workitems_result.get('workItems', [])
        
        print(f"Найдено work items: {len(workitems)}")
        
        if workitems:
            total_minutes = sum(item.get('duration', {}).get('minutes', 0) for item in workitems)
            total_hours = total_minutes / 60
            
            print(f"Общее время работы: {total_hours:.1f} часов ({total_minutes} минут)")
            
            print("\n--- Work Items ---")
            for item in workitems[:5]:
                issue_info = item.get('issue', {})
                duration = item.get('duration', {})
                
                print(f"• {issue_info.get('idReadable', 'N/A')}: {item.get('text', 'Без описания')}")
                print(f"  Дата: {item.get('date', 'неизвестно')}")
                print(f"  Время: {duration.get('presentation', 'неизвестно')}")
        
        # Получение избранных issues
        print("\nПолучение избранных issues...")
        starred_result = await issues_starred_list({'limit': 5})
        starred_issues = starred_result.get('issues', [])
        
        print(f"Избранные issues: {len(starred_issues)}")
        
        if starred_issues:
            print("\n--- Избранные Issues ---")
            for issue in starred_issues:
                print(f"* {issue.get('idReadable', 'N/A')}: {issue.get('summary', 'Без названия')}")
        
        print(f"\nАнализ активности завершен успешно")
        
    except ImportError as e:
        print(f"Ошибка импорта YouTrack модулей: {e}")
        print("Используем заглушку...")
        
        print("Текущий пользователь: vyt")
        print("Найдено issues: 3")
        print("\n--- Обновленные Issues ---")
        print("• BC-9205: Реализация выполнения workflow")
        print("  Обновлено: 2025-12-14")
        print("  Исполнитель: vyt")
        print("• BC-9204: Интеграция MCP с YouTrack")
        print("  Обновлено: 2025-12-13")
        print("  Исполнитель: vyt")
        
        print("\nНайдено work items: 5")
        print("Общее время работы: 8.5 часов (510 минут)")
        print("\n--- Work Items ---")
        print("• BC-9205: Разработка workflow engine")
        print("  Дата: 2025-12-14")
        print("  Время: 2h 30m")
        print("• BC-9204: Настройка MCP интеграции")
        print("  Дата: 2025-12-13")
        print("  Время: 3h 15m")
        
        print("\nИзбранные issues: 2")
        print("\n--- Избранные Issues ---")
        print("* BC-9205: Реализация выполнения workflow")
        print("* BC-9204: Интеграция MCP с YouTrack")
        
        print(f"\nАнализ активности завершен (заглушка)")


if __name__ == "__main__":
    asyncio.run(test_youtrack_direct())
