#!/usr/bin/env python3
"""
Утилита для очистки битых миграций базы данных QODER.

Использование:
    python fix_migration_errors.py

Эта утилита исправляет ошибки типа "no such table: main.products_old"
и другие проблемы с неудачными миграциями базы данных.
"""

import sqlite3
import os
import sys
from datetime import datetime

def check_database_exists(db_path: str) -> bool:
    """Проверяет существование файла базы данных."""
    return os.path.exists(db_path)

def backup_database(db_path: str) -> str:
    """Создает резервную копию базы данных."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.backup_{timestamp}"
    
    try:
        import shutil
        shutil.copy2(db_path, backup_path)
        print(f"✅ Создана резервная копия: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"❌ Ошибка создания резервной копии: {e}")
        return None

def analyze_database_state(db_path: str):
    """Анализирует состояние базы данных."""
    try:
        with sqlite3.connect(db_path) as db:
            cursor = db.cursor()
            
            # Получаем список всех таблиц
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            all_tables = [row[0] for row in cursor.fetchall()]
            
            print(f"📊 Найдено таблиц в базе данных: {len(all_tables)}")
            print(f"   Список таблиц: {', '.join(all_tables)}")
            
            # Проверяем наличие _old таблиц
            old_tables = [table for table in all_tables if table.endswith('_old')]
            if old_tables:
                print(f"⚠️  Найдены старые таблицы от неудачных миграций: {', '.join(old_tables)}")
            else:
                print("✅ Старых таблиц не найдено")
            
            # Проверяем основные таблицы
            essential_tables = ['users', 'products', 'sales', 'sizes']
            missing_tables = [table for table in essential_tables if table not in all_tables]
            if missing_tables:
                print(f"❌ Отсутствуют важные таблицы: {', '.join(missing_tables)}")
            else:
                print("✅ Все основные таблицы присутствуют")
            
            return all_tables, old_tables, missing_tables
    
    except sqlite3.Error as e:
        print(f"❌ Ошибка анализа базы данных: {e}")
        return None, None, None

def cleanup_broken_migrations(db_path: str):
    """Очищает битые миграции."""
    try:
        with sqlite3.connect(db_path) as db:
            cursor = db.cursor()
            
            print("🔧 Начинаю очистку битых миграций...")
            
            # Получаем список всех таблиц
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            all_tables = [row[0] for row in cursor.fetchall()]
            
            # Очищаем оставшиеся _old таблицы
            old_tables = [table for table in all_tables if table.endswith('_old')]
            for old_table in old_tables:
                main_table = old_table[:-4]  # убираем '_old'
                
                if main_table in all_tables:
                    # Основная таблица существует, удаляем старую
                    cursor.execute(f"DROP TABLE {old_table};")
                    print(f"🗑️  Удалена оставшаяся таблица: {old_table}")
                else:
                    # Основной таблицы нет, восстанавливаем из _old
                    cursor.execute(f"ALTER TABLE {old_table} RENAME TO {main_table};")
                    print(f"🔄 Восстановлена таблица {main_table} из {old_table}")
            
            db.commit()
            print("✅ Очистка битых миграций завершена")
            return True
    
    except sqlite3.Error as e:
        print(f"❌ Ошибка при очистке битых миграций: {e}")
        return False

def fix_database_permissions(db_path: str):
    """Проверяет и исправляет права доступа к файлу базы данных."""
    try:
        # Проверяем права на чтение и запись
        if not os.access(db_path, os.R_OK):
            print("❌ Нет прав на чтение файла базы данных")
            return False
        
        if not os.access(db_path, os.W_OK):
            print("❌ Нет прав на запись в файл базы данных")
            return False
        
        print("✅ Права доступа к базе данных в порядке")
        return True
    
    except Exception as e:
        print(f"❌ Ошибка проверки прав доступа: {e}")
        return False

def main():
    """Главная функция утилиты."""
    print("🔧 QODER Database Migration Fix Utility")
    print("=" * 50)
    
    # Определяем путь к базе данных
    db_name = "bot_original.db"  # стандартное имя БД для QODER
    
    if not check_database_exists(db_name):
        print(f"❌ Файл базы данных '{db_name}' не найден в текущей директории")
        print("   Убедитесь, что запускаете скрипт из корневой папки проекта QODER")
        return False
    
    print(f"📂 Найден файл базы данных: {db_name}")
    
    # Проверяем права доступа
    if not fix_database_permissions(db_name):
        return False
    
    # Создаем резервную копию
    backup_path = backup_database(db_name)
    if not backup_path:
        print("⚠️  Не удалось создать резервную копию. Продолжить? (y/N): ", end="")
        if input().lower() != 'y':
            return False
    
    # Анализируем состояние базы данных
    print("\n📊 Анализ состояния базы данных:")
    all_tables, old_tables, missing_tables = analyze_database_state(db_name)
    
    if all_tables is None:
        print("❌ Не удалось проанализировать базу данных")
        return False
    
    # Если есть битые миграции, предлагаем их очистить
    if old_tables:
        print(f"\n⚠️  Обнаружены признаки неудачных миграций!")
        print("   Это может быть причиной ошибок 'no such table: main.XXX_old'")
        print("\n🔧 Хотите очистить битые миграции? (Y/n): ", end="")
        if input().lower() != 'n':
            success = cleanup_broken_migrations(db_name)
            if success:
                print("\n✅ Битые миграции успешно очищены!")
                print("   Теперь можно перезапустить бот")
            else:
                print("\n❌ Не удалось очистить битые миграции")
                return False
    else:
        print("\n✅ Битых миграций не обнаружено")
    
    # Проверяем отсутствующие таблицы
    if missing_tables:
        print(f"\n⚠️  Внимание: отсутствуют важные таблицы: {', '.join(missing_tables)}")
        print("   Рекомендуется полная переинициализация базы данных")
        print("   Для этого удалите файл базы данных и перезапустите бот")
    
    print("\n🎉 Диагностика завершена!")
    if backup_path:
        print(f"   Резервная копия сохранена: {backup_path}")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Операция прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        sys.exit(1)