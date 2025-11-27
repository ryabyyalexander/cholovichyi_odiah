#!/usr/bin/env python3
"""
Пример использования исправленных методов удаления пользователей.

Демонстрирует как безопасно удалить пользователя из базы данных
с учетом всех связанных данных и каскадного удаления.
"""

from data_base.models import data_base
import json

def safe_delete_user(user_id: int) -> bool:
    """
    Безопасно удаляет пользователя с предварительной проверкой.
    
    Args:
        user_id: ID пользователя для удаления
        
    Returns:
        True если пользователь был успешно удален, False если нет
    """
    
    # 1. Проверяем безопасность удаления
    print(f"🔍 Проверяем возможность удаления пользователя {user_id}...")
    safety_info = data_base.check_user_deletion_safety(user_id)
    
    if not safety_info["exists"]:
        print(f"❌ Пользователь {user_id} не найден в базе данных")
        return False
    
    # 2. Показываем информацию о пользователе
    print(f"👤 Пользователь: {safety_info['first_name']}")
    print(f"👑 Администратор: {'Да' if safety_info['is_admin'] else 'Нет'}")
    
    # 3. Показываем связанные данные
    if safety_info["statistics"]:
        print("\n📊 Связанные данные, которые будут удалены:")
        for table, count in safety_info["statistics"].items():
            print(f"   • {table}: {count} записей")
    
    # 4. Показываем предупреждения
    if safety_info["warnings"]:
        print("\n⚠️  Предупреждения:")
        for warning in safety_info["warnings"]:
            print(f"   • {warning}")
    
    # 5. Запрашиваем подтверждение (в реальном коде)
    if safety_info["warnings"]:
        print(f"\n❗ ВНИМАНИЕ: Удаление пользователя {user_id} затронет важные данные!")
        print("В реальном приложении здесь должно быть подтверждение администратора.")
        # В данном примере мы продолжим
    
    # 6. Выполняем удаление
    try:
        print(f"\n🗑️  Удаляем пользователя {user_id}...")
        data_base.delete_user_completely(user_id)
        print(f"✅ Пользователь {user_id} успешно удален!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при удалении пользователя {user_id}: {e}")
        return False

def demo_user_deletion():
    """Демонстрация работы исправленных методов удаления."""
    
    print("=" * 60)
    print("🧪 ДЕМОНСТРАЦИЯ ИСПРАВЛЕННЫХ МЕТОДОВ УДАЛЕНИЯ ПОЛЬЗОВАТЕЛЕЙ")
    print("=" * 60)
    
    # Получаем список всех пользователей для демонстрации
    users, total_count = data_base.get_all_users_paginated(page=1, page_size=5)
    
    if not users:
        print("👥 В базе данных нет пользователей для демонстрации")
        return
    
    print(f"👥 Найдено {total_count} пользователей в базе данных")
    print("\nПервые 5 пользователей:")
    
    for user in users:
        print(f"   • ID: {user['user_id']}, Имя: {user['first_name']}, "
              f"Админ: {'Да' if user['is_admin'] else 'Нет'}")
    
    # Пример проверки безопасности удаления для первого пользователя
    if users:
        first_user_id = users[0]['user_id']
        print(f"\n🔍 Пример проверки безопасности удаления для пользователя {first_user_id}:")
        
        safety_info = data_base.check_user_deletion_safety(first_user_id)
        print(f"Результат проверки:")
        print(json.dumps(safety_info, indent=2, ensure_ascii=False))
        
        # В демонстрации НЕ удаляем пользователя, только показываем процесс
        print(f"\n⚠️  В демонстрации мы НЕ удаляем пользователя {first_user_id}")
        print("Для реального удаления раскомментируйте строку ниже:")
        print(f"# safe_delete_user({first_user_id})")

if __name__ == "__main__":
    demo_user_deletion()