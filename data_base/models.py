
"""
Модель базы данных для телеграм-бота.
Включает:
- Основной класс работы с SQLite
- Методы для работы с пользователями
- Методы для работы с товарами и заказами
"""

import sqlite3
from typing import Optional, List, Tuple, Any, Dict
from utils import name_bot
from utils import logger
import json
from dataclasses import dataclass
from datetime import datetime



@dataclass
class LoyaltyHistory:
    user_id: int
    event: str
    points: int
    created_at: datetime

class BotDatabase:
    """Основной класс для работы с базой данных бота"""

    # =====================================================================================
    # БЛОК 1: ИНИЦИАЛИЗАЦИЯ И МИГРАЦИЯ БАЗЫ ДАННЫХ
    # -------------------------------------------------------------------------------------
    # Этот блок отвечает за первоначальное создание и настройку базы данных.
    # Здесь определяются схемы таблиц, создаются необходимые индексы для оптимизации
    # запросов и выполняются миграции для обновления структуры базы данных
    # при внесении изменений в код.
    # =====================================================================================

    def cleanup_broken_migrations(self) -> None:
        """
        Очищает 'битые' миграции - удаляет оставшиеся _old таблицы и создает основные если они отсутствуют.
        Вызывается при ошибках миграции 'no such table: main.XXX_old'.
        """
        try:
            with sqlite3.connect(self.db_name) as db:
                cursor = db.cursor()
                
                # Получаем список всех таблиц в базе
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                all_tables = [row[0] for row in cursor.fetchall()]
                
                logger.info(f"Найдено таблиц: {all_tables}")
                
                # Очищаем оставшиеся _old таблицы
                old_tables = [table for table in all_tables if table.endswith('_old')]
                for old_table in old_tables:
                    main_table = old_table[:-4]  # убираем '_old'
                    
                    if main_table in all_tables:
                        # Основная таблица существует, удаляем старую
                        cursor.execute(f"DROP TABLE {old_table};")
                        logger.info(f"Удалена оставшаяся таблица: {old_table}")
                    else:
                        # Основной таблицы нет, восстанавливаем из _old
                        cursor.execute(f"ALTER TABLE {old_table} RENAME TO {main_table};")
                        logger.info(f"Восстановлена таблица {main_table} из {old_table}")
                
                # Проверяем обязательные таблицы и создаем если отсутствуют
                essential_tables = ['users', 'products', 'sales']
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                existing_tables = [row[0] for row in cursor.fetchall()]
                
                for table in essential_tables:
                    if table not in existing_tables:
                        logger.warning(f"Обязательная таблица {table} отсутствует! Нужно переинициализировать базу данных.")
                
                db.commit()
                logger.info("Очистка битых миграций завершена.")
                
        except sqlite3.Error as e:
            logger.error(f"Ошибка при очистке битых миграций: {e}")
            raise

    def __init__(self, db_name: str) -> None:
        """
        Инициализация подключения к БД.

        Args:
            db_name: Имя базы данных (без расширения .db)
        """
        self.db_name = f"{db_name}.db"
        self.initialize_database()

    def initialize_database(self) -> None:
        """Инициализирует структуру базы данных"""
        
        # Очищаем битые миграции перед инициализацией
        try:
            self.cleanup_broken_migrations()
        except Exception as e:
            logger.warning(f"Не удалось очистить битые миграции: {e}")
        
        # Таблицы пользователей
        self.execute_query("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            user_name TEXT,
            phone TEXT,
            size TEXT,
            is_admin BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 0,
            restart_count INTEGER DEFAULT 0,
            user_blocked BOOLEAN DEFAULT 0,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            active_msg_id TEXT,
            slider_speed TEXT,
            filters TEXT DEFAULT NULL,
            loyalty_points INTEGER DEFAULT 0,
            referrer_id INTEGER,
            level TEXT DEFAULT NULL,
            total_spent INTEGER DEFAULT 0
        );
        """)

        # Таблицы товаров
        self.execute_query(f"""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            short_description TEXT,
            purchase_price REAL NOT NULL CHECK(purchase_price >= 0),
            sale_price REAL NOT NULL CHECK(sale_price >= 0),
            discount INTEGER DEFAULT 0 CHECK(discount BETWEEN 0 AND 100),
            season TEXT NOT NULL CHECK(season IN ('весна-літо', 'осінь-зима', 'season', 'надходження')),
            loyalty_tiers TEXT,
            category TEXT,
            subcategory TEXT,
            brand TEXT,
            country TEXT,
            is_active BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Таблицы размеров
        self.execute_query("""
        CREATE TABLE IF NOT EXISTS sizes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL CHECK(type IN ('number', 'letter', 'jeans')),
            value TEXT NOT NULL UNIQUE,
            equivalent_letter TEXT
        );
        """)

        # Таблицы вариантов товаров
        self.execute_query("""
        CREATE TABLE IF NOT EXISTS product_variants (
            product_id INTEGER NOT NULL,
            size_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0),
            PRIMARY KEY (product_id, size_id),
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY (size_id) REFERENCES sizes(id)
        );
        """)

        # Таблицы медиа
        self.execute_query("""
        CREATE TABLE IF NOT EXISTS product_media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            telegram_file_id TEXT NOT NULL,
            media_type TEXT NOT NULL CHECK(media_type IN ('photo', 'video', 'document')),
            is_main BOOLEAN DEFAULT 0,
            caption TEXT DEFAULT 0,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        );
        """)

        # Таблица избранного
        self.execute_query("""
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, product_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        );
        """)

        # Таблица истории лояльности
        self.execute_query("""
        CREATE TABLE IF NOT EXISTS loyalty_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            event TEXT NOT NULL,
            points INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
        """)

        # Таблица просмотров товаров
        self.execute_query("""
        CREATE TABLE IF NOT EXISTS product_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            media_id INTEGER,
            view_type TEXT DEFAULT 'slider' CHECK(view_type IN ('slider', 'single', 'gallery')),
            view_duration INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY (media_id) REFERENCES product_media(id) ON DELETE CASCADE
        );
        """)

        # Таблица корзины
        self.execute_query("""
        CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            size_id INTEGER,
            quantity INTEGER NOT NULL DEFAULT 1 CHECK(quantity > 0),
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY (size_id) REFERENCES sizes(id)
        );
        """)

        # НОВЫЕ ТАБЛИЦЫ ДЛЯ УЧЕТА ТОВАРОВ И ПРОДАЖ

        # Таблица поступлений товаров
        self.execute_query("""
        CREATE TABLE IF NOT EXISTS inventory_receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            size_id INTEGER,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            purchase_price REAL NOT NULL CHECK(purchase_price >= 0),
            receipt_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            admin_id INTEGER,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY (size_id) REFERENCES sizes(id),
            FOREIGN KEY (admin_id) REFERENCES users(user_id)
        );
        """)

        # Таблица продаж
        self.execute_query("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            total_amount REAL NOT NULL CHECK(total_amount >= 0),
            discount_amount REAL DEFAULT 0 CHECK(discount_amount >= 0),
            final_amount REAL NOT NULL CHECK(final_amount >= 0),
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'confirmed', 'cancelled', 'completed', 'reserved')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            confirmed_at TIMESTAMP,
            completed_at TIMESTAMP,
            admin_notes TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );
        """)

        # Таблица позиций продаж
        self.execute_query("""
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            size_id INTEGER,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            unit_price REAL NOT NULL CHECK(unit_price >= 0),
            total_price REAL NOT NULL CHECK(total_price >= 0),
            purchase_price REAL NOT NULL CHECK(purchase_price >= 0),
            profit REAL GENERATED ALWAYS AS (total_price - (purchase_price * quantity)) STORED,
            FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY (size_id) REFERENCES sizes(id)
        );
        """)

        # Таблица истории активации товаров
        self.execute_query("""
        CREATE TABLE IF NOT EXISTS product_activation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            admin_id INTEGER NOT NULL,
            action TEXT NOT NULL CHECK(action IN ('activated', 'deactivated')),
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY (admin_id) REFERENCES users(user_id)
        );
        """)

        # Таблица архива сообщений
        self.execute_query("""
        CREATE TABLE IF NOT EXISTS message_archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Таблица тем подписок
        self.execute_query("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_key TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL
        );
        """)

        # Таблица подписок пользователей
        self.execute_query("""
        CREATE TABLE IF NOT EXISTS user_subscriptions (
            user_id INTEGER NOT NULL,
            subscription_id INTEGER NOT NULL,
            filters TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, subscription_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (subscription_id) REFERENCES subscriptions(id) ON DELETE CASCADE
        );
        """)

        # Таблица получателей архивных сообщений
        self.execute_query("""
        CREATE TABLE IF NOT EXISTS archived_message_recipients (
            archive_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            PRIMARY KEY (archive_id, user_id),
            FOREIGN KEY (archive_id) REFERENCES message_archive(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );
        """)

        # Таблица резервов
        self.execute_query("""
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            user_id INTEGER NOT NULL,
            admin_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            size_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL CHECK(status IN ('active', 'temporary', 'completed', 'cancelled')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            final_price REAL,
            FOREIGN KEY (order_id) REFERENCES sales(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (admin_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY (size_id) REFERENCES sizes(id) ON DELETE CASCADE
        );
        """)

        # Таблица листа ожидания
        self.execute_query("""
        CREATE TABLE IF NOT EXISTS waiting_list (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            size_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'notified', 'expired')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, product_id, size_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY (size_id) REFERENCES sizes(id) ON DELETE CASCADE
        );
        """)

        # Предзаполняем таблицу размеров при первом запуске
        if not self.execute_query("SELECT 1 FROM sizes LIMIT 1").fetchone():
            self._initialize_sizes()
            # Добавляем индексы
            self._create_indexes()

        # Предзаполняем темы подписок
        if not self.execute_query("SELECT 1 FROM subscriptions LIMIT 1").fetchone():
            self._initialize_subscriptions()

    def _create_indexes(self) -> None:
        """Создает оптимизирующие индексы"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);",
            "CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand);",
            "CREATE INDEX IF NOT EXISTS idx_product_variants ON product_variants(product_id, size_id);",
            "CREATE INDEX IF NOT EXISTS idx_product_views_user ON product_views(user_id, created_at);",
            "CREATE INDEX IF NOT EXISTS idx_product_views_product ON product_views(product_id, created_at);",
            "CREATE INDEX IF NOT EXISTS idx_product_views_created ON product_views(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites(user_id, added_at);",
            "CREATE INDEX IF NOT EXISTS idx_favorites_product ON favorites(product_id);",
        ]

        for index_query in indexes:
            try:
                self.execute_query(index_query)
            except sqlite3.Error as e:
                logger.error(f"Error creating index: {e}")

    def _initialize_sizes(self) -> None:
        """Инициализирует таблицу размеров при первом запуске"""
        sizes_data = [
            # Числовые размеры (куртки)
            ('number', '46', 'xs'), ('number', '48', 's'),
            ('number', '50', 'm'), ('number', '52', 'l'),
            ('number', '54', 'xl'), ('number', '56', '2xl'),
            ('number', '58', '3xl'), ('number', '60', '4xl'),

            # Размеры джинсов
            ('jeans', '31', 'xs'), ('jeans', '32', 's'),
            ('jeans', '33', 'm'), ('jeans', '34', 'm'),
            ('jeans', '35', 'l'), ('jeans', '36', 'l'),
            ('jeans', '38', 'xl'), ('jeans', '40', '2xl'),
            ('jeans', '42', '3xl'),

            # Буквенные размеры
            ('letter', 'xs', None), ('letter', 's', None),
            ('letter', 'm', None), ('letter', 'l', None),
            ('letter', 'xl', None), ('letter', '2xl', None),
            ('letter', '3xl', None), ('letter', '4xl', None),
            ('letter', 'one size', None)
        ]

        for size_type, value, equivalent in sizes_data:
            self.execute_query(
                "INSERT INTO sizes (type, value, equivalent_letter) VALUES (?, ?, ?)",
                (size_type, value, equivalent)
            )

    def _initialize_subscriptions(self) -> None:
        """Инициализирует темы подписок."""
        topics = [
            ('new_arrivals', 'Новые поступления'),
            ('sales_and_discounts', 'Акции и скидки'),
            ('brand_news', 'Новости бренда'),
            ('size_discounts', 'Скидка на мой размер')
        ]
        for topic_key, description in topics:
            self.add_subscription_topic(topic_key, description)
        logger.info("Таблица подписок инициализирована.")

    # Удалено: функция миграции для order_id в reservations (столбец уже есть в CREATE TABLE)

    # Удалено: _migrate_product_season_add_new() - 'надходження' уже в CHECK constraint

    # Удалено: _migrate_sales_status_add_reserved() - 'reserved' уже в CHECK constraint

    # Удалено: _migrate_rename_weather_to_loyalty_tiers() - столбец сразу loyalty_tiers

    # Удалено: _migrate_active_msg_id() - не нужно для новой базы

    # Удалено: _migrate_user_cascade_tables() - сразу ON DELETE CASCADE в CREATE TABLE

    # Удалено: _migrate_existing_products() - не нужно для новой базы


    # =====================================================================================
    # БЛОК 2: ОСНОВНЫЕ МЕТОДЫ ВЫПОЛНЕНИЯ ЗАПРОСОВ
    # -------------------------------------------------------------------------------------
    # Низкоуровневые методы для взаимодействия с базой данных.
    # Они являются основой для всех остальных операций и обеспечивают
    # безопасное выполнение SQL-запросов с обработкой исключений.
    # =====================================================================================

    def execute_query(self, query: str, params: Tuple[Any, ...] = ()) -> sqlite3.Cursor:
        """
        Выполняет SQL-запрос с параметрами.

        Args:
            query: SQL-запрос
            params: Параметры для запроса

        Returns:
            Курсор с результатами выполнения
        """
        try:
            with sqlite3.connect(self.db_name) as db:
                cursor = db.cursor()
                cursor.execute(query, params)
                db.commit()
                return cursor
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            raise

    def execute_query_many(self, query: str, params: List[Tuple[Any, ...]]) -> None:
        """Выполняет SQL-запрос с несколькими наборами параметров."""
        try:
            with sqlite3.connect(self.db_name) as db:
                cursor = db.cursor()
                cursor.executemany(query, params)
                db.commit()
        except sqlite3.Error as e:
            logger.error(f"Database error (executemany): {e}")
            raise

    # =====================================================================================
    # БЛОК 3: УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ
    # -------------------------------------------------------------------------------------
    # Этот блок содержит все методы для работы с пользователями:
    # - Регистрация и проверка существования
    # - Получение и обновление данных (имя, телефон, фильтры)
    # - Управление статусами (активный, заблокированный, админ)
    # - Отслеживание активности и настроек (счетчики, скорость слайдера)
    # =====================================================================================

    def sql_new_user(self, user_id: int, first_name: str, last_name: Optional[str],
                     user_name: Optional[str], is_admin: bool) -> bool:
        """
        Регистрирует нового пользователя.

        Returns:
            True если пользователь был добавлен, False если уже существует
        """
        if not self.sql_user_exists(user_id):
            self.execute_query('''
                INSERT INTO users (user_id, first_name, last_name, user_name, is_admin, level)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, first_name, last_name, user_name, is_admin, None))
            return True
        return False

    def sql_get_user(self, user_id: int, *fields: str) -> Optional[Tuple]:
        """Получает данные пользователя по ID"""
        fields_to_select = ', '.join(fields) if fields else '*'
        cursor = self.execute_query(
            f"SELECT {fields_to_select} FROM users WHERE user_id = ?",
            (user_id,)
        )
        return cursor.fetchone()

    def sql_user_exists(self, user_id: int) -> bool:
        """Проверяет существование пользователя"""
        cursor = self.execute_query(
            "SELECT 1 FROM users WHERE user_id = ?",
            (user_id,)
        )
        return cursor.fetchone() is not None

    def increment_restart_count(self, user_id: int) -> None:
        """Инкрементирует счетчик заказов (сейчас дублирует update_restart_count)"""
        self.execute_query(
            "UPDATE users SET restart_count = restart_count + 1 WHERE user_id = ?",
            (user_id,)
        )

    def increment_activity_count(self, user_id: int, weight: float = 1) -> None:
        """
        Инкрементирует счетчик активности пользователя с учетом веса действия.
        
        Args:
            user_id: ID пользователя
            weight: Вес активности (по умолчанию 1)
        """
        self.execute_query(
            "UPDATE users SET restart_count = restart_count + ? WHERE user_id = ?",
            (round(weight), user_id)
        )

    def update_user_blocked(self, user_id: int, status: bool) -> None:
        """Обновляет статус блокировки пользователя"""
        self.execute_query(
            "UPDATE users SET user_blocked = ? WHERE user_id = ?",
            (status, user_id)
        )

    def get_restart_count(self, user_id: int) -> int:
        """Возвращает количество перезапусков бота пользователем"""
        cursor = self.execute_query(
            "SELECT restart_count FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        return result[0] if result else 0

    def activate_user(self, user_id: int) -> None:
        """Активирует пользователя (дает доступ к боту)"""
        self.execute_query(
            "UPDATE users SET is_active = 1 WHERE user_id = ?",
            (user_id,)
        )

    def set_user_level(self, user_id: int, level: str) -> None:
        """Устанавливает уровень лояльности для пользователя."""
        self.execute_query(
            "UPDATE users SET level = ? WHERE user_id = ?",
            (level, user_id)
        )

    def get_pending_users(self) -> List[Tuple[int, str, str]]:
        """Возвращает список пользователей, ожидающих активации"""
        cursor = self.execute_query(
            "SELECT user_id, first_name, user_name FROM users WHERE is_active = 0"
        )
        return cursor.fetchall()

    def is_user_active(self, user_id: int) -> bool:
        """Проверяет, активирован ли пользователь"""
        cursor = self.execute_query(
            "SELECT is_active FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        return bool(result[0]) if result else False

    def get_list_admins(self) -> List[int]:
        """Возвращает список ID администраторов"""
        cursor = self.execute_query("SELECT user_id FROM users WHERE is_admin = 1")
        return [row[0] for row in cursor.fetchall()]

    def get_unblocked_users(self) -> List[int]:
        """Возвращает список ID всех пользователей, которые не заблокировали бота."""
        cursor = self.execute_query(
            "SELECT user_id FROM users WHERE user_blocked != 1"
        )
        return [row[0] for row in cursor.fetchall()]

    def get_all_users_paginated(self, page: int = 1, page_size: int = 10) -> Tuple[List[Dict[str, Any]], int]:
        """
        Возвращает список всех пользователей с пагинацией.

        Args:
            page: Номер страницы (начиная с 1)
            page_size: Количество пользователей на странице

        Returns:
            Кортеж: (список пользователей, общее количество пользователей)
        """
        offset = (page - 1) * page_size
        
        # Сначала получаем общее количество пользователей
        total_users_cursor = self.execute_query("SELECT COUNT(*) FROM users")
        total_users = total_users_cursor.fetchone()[0]

        # Затем получаем пользователей для текущей страницы
        cursor = self.execute_query(
            "SELECT user_id, first_name, user_name, is_admin, user_blocked FROM users ORDER BY registered_at DESC LIMIT ? OFFSET ?",
            (page_size, offset)
        )
        
        columns = [column[0] for column in cursor.description]
        users = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        return users, total_users

    def check_user_deletion_safety(self, user_id: int) -> Dict[str, Any]:
        """
        Проверяет возможность безопасного удаления пользователя и возвращает статистику связанных данных.
        
        Args:
            user_id: ID пользователя для проверки
            
        Returns:
            Словарь с информацией о связанных данных и рекомендациями
        """
        try:
            cursor = self.execute_query(
                "SELECT first_name, is_admin FROM users WHERE user_id = ?",
                (user_id,)
            )
            user_info = cursor.fetchone()
            
            if not user_info:
                return {"exists": False, "message": "Пользователь не найден"}
            
            first_name, is_admin = user_info
            safety_info = {
                "exists": True,
                "first_name": first_name,
                "is_admin": bool(is_admin),
                "can_delete_safely": True,
                "warnings": [],
                "statistics": {}
            }
            
            # Проверяем критически важные связи
            tables_to_check = [
                ("product_activation_history", "admin_id", "записей активации товаров как админ"),
                ("inventory_receipts", "admin_id", "записей поступления товаров как админ"),
                ("reservations", "admin_id", "резервирований как админ"),
                ("loyalty_history", "user_id", "записей истории лояльности"),
                ("sales", "user_id", "заказов"),
                ("cart", "user_id", "товаров в корзине"),
                ("favorites", "user_id", "товаров в избранном"),
                ("users", "referrer_id", "рефералов")
            ]
            
            for table, column, description in tables_to_check:
                cursor = self.execute_query(
                    f"SELECT COUNT(*) FROM {table} WHERE {column} = ?",
                    (user_id,)
                )
                count = cursor.fetchone()[0]
                
                if count > 0:
                    safety_info["statistics"][table] = count
                    
                    # Особые предупреждения для критических таблиц
                    if table == "product_activation_history" and count > 0:
                        safety_info["warnings"].append(
                            f"ВНИМАНИЕ: {count} {description} - эти записи будут удалены!"
                        )
                    elif table == "users" and column == "referrer_id":
                        safety_info["warnings"].append(
                            f"У пользователя {count} рефералов - ссылки будут обнулены"
                        )
                    elif count > 0:
                        safety_info["warnings"].append(f"{count} {description}")
            
            return safety_info
            
        except sqlite3.Error as e:
            logger.error(f"Error checking user deletion safety for {user_id}: {e}")
            return {
                "exists": False, 
                "error": str(e),
                "can_delete_safely": False
            }

    def delete_user_completely(self, user_id: int) -> None:
        """
        Полностью удаляет пользователя и все его связанные данные из базы данных.
        Выполняет операции в одной транзакции с обработкой всех проблемных связей.
        """
        try:
            with sqlite3.connect(self.db_name) as db:
                cursor = db.cursor()
                # Включаем поддержку внешних ключей для сессии
                cursor.execute("PRAGMA foreign_keys = ON;")
                
                logger.info(f"Starting complete deletion of user {user_id}")

                # 1. Обнуляем ссылки на этого пользователя (если он был реферером)
                cursor.execute("UPDATE users SET referrer_id = NULL WHERE referrer_id = ?", (user_id,))
                logger.debug(f"Cleared referrer_id references for user {user_id}")

                # 2. Обнуляем admin_id в таблицах где это возможно
                cursor.execute("UPDATE inventory_receipts SET admin_id = NULL WHERE admin_id = ?", (user_id,))
                logger.debug(f"Cleared admin_id in inventory_receipts for user {user_id}")
                
                # 3. КРИТИЧЕСКАЯ ПРОБЛЕМА: product_activation_history - admin_id NOT NULL
                # Удаляем записи, где пользователь был администратором
                cursor.execute("DELETE FROM product_activation_history WHERE admin_id = ?", (user_id,))
                logger.debug(f"Deleted product_activation_history records for admin {user_id}")
                
                # 4. ПРОБЛЕМА: loyalty_history - нет CASCADE, удаляем вручную
                cursor.execute("DELETE FROM loyalty_history WHERE user_id = ?", (user_id,))
                logger.debug(f"Deleted loyalty_history records for user {user_id}")
                
                # 5. Проверяем и удаляем записи в reservations где пользователь был админом
                # (у этой таблицы есть CASCADE, но на всякий случай)
                cursor.execute("SELECT COUNT(*) FROM reservations WHERE admin_id = ?", (user_id,))
                admin_reservations = cursor.fetchone()[0]
                if admin_reservations > 0:
                    logger.warning(f"User {user_id} has {admin_reservations} reservations as admin, they will be deleted")

                # 6. Удаляем самого пользователя. ON DELETE CASCADE должен сработать для остальных таблиц.
                cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
                
                db.commit()
                logger.info(f"User {user_id} and all related data have been deleted successfully.")
        except sqlite3.Error as e:
            logger.error(f"Failed to delete user {user_id} completely: {e}")
            # Транзакция будет автоматически отменена, если возникнет исключение
            raise

    def get_user_stats(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Собирает и возвращает подробную статистику по пользователю.

        Args:
            user_id: ID пользователя

        Returns:
            Словарь со статистикой или None, если пользователь не найден.
        """
        user_info_cursor = self.execute_query(
            "SELECT user_id, first_name, user_name, phone, registered_at, loyalty_points, level, total_spent FROM users WHERE user_id = ?",
            (user_id,)
        )
        user_info = user_info_cursor.fetchone()

        if not user_info:
            return None

        columns = [column[0] for column in user_info_cursor.description]
        stats = dict(zip(columns, user_info))

        # Статистика по заказам
        sales_cursor = self.execute_query(
            "SELECT COUNT(id), SUM(final_amount) FROM sales WHERE user_id = ? AND status = 'completed'",
            (user_id,)
        )
        sales_data = sales_cursor.fetchone()
        stats['completed_orders_count'] = sales_data[0] or 0
        stats['total_spent_from_sales'] = sales_data[1] or 0.0

        # Количество товаров в корзине
        cart_cursor = self.execute_query("SELECT COUNT(id) FROM cart WHERE user_id = ?", (user_id,))
        stats['cart_items_count'] = cart_cursor.fetchone()[0] or 0

        # Количество товаров в избранном
        favorites_cursor = self.execute_query("SELECT COUNT(id) FROM favorites WHERE user_id = ?", (user_id,))
        stats['favorites_count'] = favorites_cursor.fetchone()[0] or 0

        # Количество рефералов
        referrals_cursor = self.execute_query("SELECT COUNT(user_id) FROM users WHERE referrer_id = ?", (user_id,))
        stats['referrals_count'] = referrals_cursor.fetchone()[0] or 0
        
        return stats

    def get_users_by_level(self, level: str) -> List[int]:
        """Возвращает список ID пользователей по уровню лояльности, которые не заблокировали бота."""
        cursor = self.execute_query(
            "SELECT user_id FROM users WHERE level = ? AND user_blocked != 1",
            (level,)
        )
        return [row[0] for row in cursor.fetchall()]

    def get_users_with_no_purchase_history(self) -> List[int]:
        """Возвращает список ID всех пользователей, у которых нет истории покупок и которые не заблокировали бота."""
        cursor = self.execute_query(
            """SELECT u.user_id FROM users u
               WHERE u.user_blocked != 1 AND NOT EXISTS (
                   SELECT 1 FROM loyalty_history lh WHERE lh.user_id = u.user_id AND lh.event = 'purchase'
               )"""
        )
        return [row[0] for row in cursor.fetchall()]

    def get_phone(self, user_id: int) -> Optional[str]:
        """Возвращает номер телефона пользователя"""
        cursor = self.execute_query(
            "SELECT phone FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        return result[0] if result else None

    def get_active_msg_id(self, user_id: int) -> Optional[int]:
        """Возвращает ID активного сообщения из словаря"""
        cursor = self.execute_query(
            "SELECT active_msg_id FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        if result and result[0]:
            try:
                msg_ids = json.loads(result[0])
                return msg_ids.get('active')
            except (json.JSONDecodeError, KeyError):
                return None
        return None

    def get_register_msg_id(self, user_id: int) -> Optional[int]:
        """Возвращает ID сообщения о регистрации из словаря"""
        cursor = self.execute_query(
            "SELECT active_msg_id FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        if result and result[0]:
            try:
                msg_ids = json.loads(result[0])
                return msg_ids.get('register')
            except (json.JSONDecodeError, KeyError):
                return None
        return None

    def set_active_msg_id(self, user_id: int, message_id: Optional[int]) -> None:
        """Сохраняет ID активного сообщения в словарь"""
        cursor = self.execute_query(
            "SELECT active_msg_id FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        
        msg_ids = {}
        if result and result[0]:
            try:
                msg_ids = json.loads(result[0])
            except json.JSONDecodeError:
                msg_ids = {}
        
        if message_id:
            msg_ids['active'] = message_id
        elif 'active' in msg_ids:
            del msg_ids['active']
        
        msg_ids_json = json.dumps(msg_ids) if msg_ids else None
        self.execute_query(
            "UPDATE users SET active_msg_id = ? WHERE user_id = ?",
            (msg_ids_json, user_id)
        )

    def set_register_msg_id(self, user_id: int, message_id: Optional[int]) -> None:
        """Сохраняет ID сообщения о регистрации в словарь"""
        cursor = self.execute_query(
            "SELECT active_msg_id FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        
        msg_ids = {}
        if result and result[0]:
            try:
                msg_ids = json.loads(result[0])
            except json.JSONDecodeError:
                msg_ids = {}
        
        if message_id:
            msg_ids['register'] = message_id
        elif 'register' in msg_ids:
            del msg_ids['register']
        
        msg_ids_json = json.dumps(msg_ids) if msg_ids else None
        self.execute_query(
            "UPDATE users SET active_msg_id = ? WHERE user_id = ?",
            (msg_ids_json, user_id)
        )

    def clear_register_msg_id(self, user_id: int) -> None:
        """Очищает ID сообщения о регистрации из словаря"""
        self.set_register_msg_id(user_id, None)

    def set_user_filters(self, user_id: int, filters: dict) -> None:
        """Сохраняет фильтры пользователя в базу данных (как JSON)."""
        filters_json = json.dumps(filters, ensure_ascii=False)
        self.execute_query(
            "UPDATE users SET filters = ? WHERE user_id = ?",
            (filters_json, user_id)
        )

    def get_user_filters(self, user_id: int) -> dict:
        """Возвращает фильтры пользователя из базы данных (как dict)."""
        cursor = self.execute_query(
            "SELECT filters FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        if result and result[0]:
            try:
                return json.loads(result[0])
            except Exception:
                return {}
        return {}

    def set_slider_speed(self, user_id: int, speed: int) -> None:
        """Сохраняет скорость слайдера в поле slider_speed"""
        self.execute_query(
            "UPDATE users SET slider_speed = ? WHERE user_id = ?",
            (str(speed), user_id)
        )

    def get_slider_speed(self, user_id: int) -> int:
        """Получает скорость слайдера из slider_speed (если есть), иначе возвращает None"""
        cursor = self.execute_query(
            "SELECT slider_speed FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        if result and result[0]:
            try:
                return int(result[0])
            except ValueError:
                return None
        return None

    # =====================================================================================
    # БЛОК 4: УПРАВЛЕНИЕ РЕФЕРАЛЬНОЙ СИСТЕМОЙ
    # -------------------------------------------------------------------------------------
    # Методы для реализации программы "Приведи друга".
    # Включают регистрацию пользователя с указанием реферера,
    # получение списка приглашенных и проверку наличия реферера.
    # =====================================================================================

    def register_user_with_referrer(self, user_id: int, first_name: str, last_name: Optional[str],
                                    user_name: Optional[str], is_admin: bool, referrer_id: Optional[int] = None) -> bool:
        """
        Регистрирует нового пользователя с возможностью указать реферера.
        Если пользователь уже существует, ничего не делает.
        Args:
            user_id: ID пользователя
            first_name: Имя
            last_name: Фамилия
            user_name: username
            is_admin: Является ли админом
            referrer_id: ID пригласившего пользователя (если есть)
        Returns:
            True если пользователь был добавлен, False если уже существует
        """
        if not self.sql_user_exists(user_id):
            self.execute_query('''
                INSERT INTO users (user_id, first_name, last_name, user_name, is_admin, referrer_id, level)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, first_name, last_name, user_name, is_admin, referrer_id, None))
            return True
        return False

    def get_referrals(self, referrer_id: int) -> list:
        """
        Возвращает список пользователей, которых пригласил данный пользователь (по referrer_id).
        Args:
            referrer_id: ID пригласившего пользователя
        Returns:
            Список кортежей с данными пользователей
        """
        cursor = self.execute_query(
            "SELECT user_id, first_name, last_name, user_name FROM users WHERE referrer_id = ?",
            (referrer_id,)
        )
        return cursor.fetchall()

    def has_referrer(self, user_id: int) -> bool:
        """
        Проверяет, установлен ли referrer_id у пользователя.
        Args:
            user_id: ID пользователя
        Returns:
            True если referrer_id установлен, иначе False
        """
        cursor = self.execute_query(
            "SELECT referrer_id FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        return result is not None and result[0] is not None

    # =====================================================================================
    # БЛОК 5: УПРАВЛЕНИЕ ТОВАРАМИ (ОСНОВНЫЕ ОПЕРАЦИИ)
    # -------------------------------------------------------------------------------------
    # Базовые CRUD-операции (Create, Read, Update, Delete) для товаров.
    # - Добавление, получение, обновление и удаление карточек товаров.
    # - Активация и деактивация товаров для скрытия из каталога.
    # =====================================================================================

    def add_product(self, product_data: Dict[str, Any]) -> int:
        """
        Добавляет новый товар в базу данных.

        Args:
            product_data: Словарь с данными товара

        Returns:
            ID созданного товара
        """
        query = """
        INSERT INTO products (
            vendor_code, name, short_description,
            purchase_price, sale_price, discount, season, loyalty_tiers, category,
            subcategory, brand, country
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            product_data['vendor_code'],
            product_data['name'],
            product_data.get('short_description'),
            product_data['purchase_price'],
            product_data['sale_price'],
            product_data.get('discount', 0),
            product_data['season'],
            product_data.get('loyalty_tiers'),
            product_data['category'],
            product_data.get('subcategory'),
            product_data.get('brand'),
            product_data.get('country')
        )

        cursor = self.execute_query(query, params)
        return cursor.lastrowid

    def create_products_with_media(self, media_list: List[Dict[str, Any]],
                                   create_separate: bool = False) -> List[int]:
        """
        Создает продукты с прикрепленными медиа-файлами.

        Args:
            media_list: Список словарей с данными медиа
            create_separate: Создавать отдельный продукт для каждого медиа

        Returns:
            Список ID созданных продуктов
        """
        created_ids = []

        if not media_list:
            return created_ids

        try:
            if create_separate:
                # Создаем отдельный продукт для каждого медиа
                for media in media_list:
                    product_id = self.get_next_product_id()
                    product_data = {
                        'vendor_code': f"temp_{product_id}",
                        'name': f"Товар {product_id}",
                        'short_description': '',
                        'purchase_price': 0,
                        'sale_price': 0,
                        'season': 'season',
                        'loyalty_tiers': '',
                        'category': 'category',
                        'subcategory': 'sub',
                        'brand': 'brand',
                        'country': 'country',
                    }
                    self.add_product(product_data)
                    self.add_product_media(product_id, media['path'],
                                           media['type_media'], True,
                                           media.get('caption', ''))
                    created_ids.append(product_id)
            else:
                # Создаем один продукт со всеми медиа
                product_id = self.get_next_product_id()
                first_media = media_list[0]
                product_data = {
                    'vendor_code': f"temp_{product_id}",
                    'name': f"Товар {product_id}",
                    'short_description': '',
                    'purchase_price': 0,
                    'sale_price': 0,
                    'season': 'season',
                    'loyalty_tiers': '',
                    'category': 'category',
                    'subcategory': 'sub',
                    'brand': 'brand',
                    'country': 'country',
                }
                self.add_product(product_data)

                # Добавляем первое медиа как основное
                self.add_product_media(product_id, first_media['path'],
                                       first_media['type_media'], True,
                                       first_media.get('caption', ''))

                # Добавляем остальные медиа
                for media in media_list[1:]:
                    self.add_product_media(product_id, media['path'],
                                           media['type_media'], False,
                                           media.get('caption', ''))

                created_ids.append(product_id)

            return created_ids
        except Exception as e:
            logger.error(f"Error creating products with media: {e}")
            raise

    def sql_get_product(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Получает данные товара по ID"""
        cursor = self.execute_query(
            "SELECT * FROM products WHERE id = ?",
            (product_id,)
        )
        result = cursor.fetchone()
        if not result:
            return None

        columns = [column[0] for column in cursor.description]
        return dict(zip(columns, result))

    def update_product_field(self, product_id: int, field: str, value: Any) -> None:
        """Обновляет поле товара"""
        self.execute_query(
            f"UPDATE products SET {field} = ? WHERE id = ?",
            (value, product_id)
        )

    def delete_product(self, product_id: int) -> None:
        """
        Удаляет товар и все связанные с ним данные.
        
        Args:
            product_id: ID товара для удаления
        """
        try:
            # Удаляем товар из таблицы products
            # Связанные данные (product_variants, product_media) удалятся автоматически
            # благодаря CASCADE в FOREIGN KEY
            self.execute_query(
                "DELETE FROM products WHERE id = ?",
                (product_id,)
            )
            logger.info(f"Product {product_id} and all related data deleted successfully")
        except sqlite3.Error as e:
            logger.error(f"Error deleting product {product_id}: {e}")
            raise

    def get_next_product_id(self) -> int:
        """Получает следующий доступный ID для нового продукта"""
        cursor = self.execute_query("SELECT seq FROM sqlite_sequence WHERE name='products'")
        result = cursor.fetchone()
        return 1 if result is None else result[0] + 1

    def activate_product(self, product_id: int, admin_id: int, reason: str = None) -> bool:
        """
        Активирует товар (делает видимым для пользователей).
        
        Args:
            product_id: ID товара
            admin_id: ID администратора
            reason: Причина активации
            
        Returns:
            True если товар активирован
        """
        # Проверяем, существует ли товар
        product = self.sql_get_product(product_id)
        if not product:
            raise ValueError(f"Товар {product_id} не найден")
        
        # Проверяем обязательные поля
        required_fields = ['name', 'purchase_price', 'sale_price', 'season', 'category']
        missing_fields = []
        
        for field in required_fields:
            if not product.get(field):
                missing_fields.append(field)
        
        if missing_fields:
            raise ValueError(f"Товар {product_id} не может быть активирован. Отсутствуют поля: {', '.join(missing_fields)}")
        
        # Активируем товар
        self.execute_query(
            "UPDATE products SET is_active = 1 WHERE id = ?",
            (product_id,)
        )
        
        # Записываем в историю
        self.execute_query(
            "INSERT INTO product_activation_history (product_id, admin_id, action, reason) "
            "VALUES (?, ?, 'activated', ?)",
            (product_id, admin_id, reason)
        )
        
        logger.info(f"Товар {product_id} активирован администратором {admin_id}")
        return True

    def deactivate_product(self, product_id: int, admin_id: int, reason: str = None) -> bool:
        """
        Деактивирует товар (делает невидимым для пользователей).
        
        Args:
            product_id: ID товара
            admin_id: ID администратора
            reason: Причина деактивации
            
        Returns:
            True если товар деактивирован
        """
        # Проверяем, существует ли товар
        product = self.sql_get_product(product_id)
        if not product:
            raise ValueError(f"Товар {product_id} не найден")
        
        # Деактивируем товар
        self.execute_query(
            "UPDATE products SET is_active = 0 WHERE id = ?",
            (product_id,)
        )
        
        # Записываем в историю
        self.execute_query(
            "INSERT INTO product_activation_history (product_id, admin_id, action, reason) "
            "VALUES (?, ?, 'deactivated', ?)",
            (product_id, admin_id, reason)
        )
        
        logger.info(f"Товар {product_id} деактивирован администратором {admin_id}")
        return True

    # =====================================================================================
    # БЛОК 6: УПРАВЛЕНИЕ МЕДИАФАЙЛАМИ ТОВАРОВ
    # -------------------------------------------------------------------------------------
    # Методы для работы с фотографиями и видео товаров.
    # - Добавление, получение и удаление медиа.
    # - Установка главного фото товара.
    # - Обновление подписей к медиафайлам.
    # =====================================================================================

    def add_product_media(self, product_id: int, file_id: str,
                          media_type: str = 'photo', is_main: bool = False,
                          caption: str = '') -> None:
        """
        Добавляет медиа-файл к товару.

        Args:
            product_id: ID товара
            file_id: file_id из Telegram
            media_type: Тип медиа ('photo', 'video', 'document')
            is_main: Является ли основным изображением
            caption: Подпись к медиа
        """
        self.execute_query(
            "INSERT INTO product_media (product_id, telegram_file_id, media_type, is_main, caption) "
            "VALUES (?, ?, ?, ?, ?)",
            (product_id, file_id, media_type, int(is_main), caption))

    def get_product_media(self, product_id: int) -> List[list]:
        """Получает все медиа товара в виде списка списков [id, file_id, type, is_main, caption]"""
        cursor = self.execute_query(
            "SELECT id, telegram_file_id, media_type, is_main, caption "
            "FROM product_media WHERE product_id = ? ORDER BY is_main DESC, id",
            (product_id,)
        )
        return [
            [row[0], row[1], row[2], bool(row[3]), row[4]]
            for row in cursor.fetchall()
        ]

    def get_all_product_media(self) -> List[List[Any]]:
        """
        Возвращает все записи из таблицы product_media в виде списка списков.

        Returns:
            Список списков, где каждый внутренний список содержит:
            [id, product_id, telegram_file_id, media_type, is_main, caption]
        """
        cursor = self.execute_query(
            "SELECT id, product_id, telegram_file_id, media_type, is_main, caption "
            "FROM product_media WHERE is_main = True ORDER BY product_id, is_main DESC, id"
        )
        return [
            [row[0], row[1], row[2], row[3], bool(row[4]), row[5]]
            for row in cursor.fetchall()
        ]

    def get_main_product_photo(self, product_id: int) -> Optional[str]:
        """Получает file_id главного фото товара"""
        cursor = self.execute_query(
            "SELECT telegram_file_id FROM product_media "
            "WHERE product_id = ? AND is_main = 1 AND media_type = 'photo' "
            "LIMIT 1",
            (product_id,)
        )
        result = cursor.fetchone()
        return result[0] if result else None

    def set_main_photo(self, product_id: int, media_id: int) -> None:
        """
        Устанавливает фото как главное для товара.
        
        Args:
            product_id: ID товара
            media_id: ID медиа-записи
        """
        try:
            # Сначала сбрасываем все фото товара как неглавные
            self.execute_query(
                "UPDATE product_media SET is_main = 0 WHERE product_id = ?",
                (product_id,)
            )
            # Затем устанавливаем выбранное как главное
            self.execute_query(
                "UPDATE product_media SET is_main = 1 WHERE id = ? AND product_id = ?",
                (media_id, product_id)
            )
            logger.info(f"Set media {media_id} as main for product {product_id}")
        except sqlite3.Error as e:
            logger.error(f"Error setting main photo: {e}")
            raise

    def delete_product_media(self, media_id: int) -> bool:
        """
        Удаляет конкретное медиа из товара.
        
        Args:
            media_id: ID медиа-записи
            
        Returns:
            True если медиа было удалено, False если не найдено
        """
        try:
            cursor = self.execute_query(
                "DELETE FROM product_media WHERE id = ?",
                (media_id,)
            )
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Media {media_id} deleted successfully")
            else:
                logger.warning(f"Media {media_id} not found for deletion")
            return deleted
        except sqlite3.Error as e:
            logger.error(f"Error deleting media {media_id}: {e}")
            raise

    def add_media_to_product(self, product_id: int, file_id: str, media_type: str = 'photo', caption: str = '') -> int:
        """
        Добавляет медиа к существующему товару.
        
        Args:
            product_id: ID товара
            file_id: file_id из Telegram
            media_type: Тип медиа ('photo', 'video', 'document')
            caption: Подпись к медиа
            
        Returns:
            ID созданной медиа-записи
        """
        try:
            # Проверяем, есть ли уже главное фото у товара
            cursor = self.execute_query(
                "SELECT COUNT(*) FROM product_media WHERE product_id = ? AND is_main = 1",
                (product_id,)
            )
            has_main = cursor.fetchone()[0] > 0
            
            # Если главного фото нет, делаем это фото главным
            is_main = not has_main
            
            cursor = self.execute_query(
                "INSERT INTO product_media (product_id, telegram_file_id, media_type, is_main, caption) "
                "VALUES (?, ?, ?, ?, ?)",
                (product_id, file_id, media_type, int(is_main), caption)
            )
            media_id = cursor.lastrowid
            logger.info(f"Added media {media_id} to product {product_id} (is_main={is_main})")
            return media_id
        except sqlite3.Error as e:
            logger.error(f"Error adding media to product: {e}")
            raise

    def get_product_media_info(self, product_id: int) -> List[Dict[str, Any]]:
        """
        Получает подробную информацию о медиа товара.
        
        Args:
            product_id: ID товара
            
        Returns:
            Список словарей с информацией о медиа
        """
        cursor = self.execute_query(
            "SELECT id, telegram_file_id, media_type, is_main, caption, created_at "
            "FROM product_media WHERE product_id = ? ORDER BY is_main DESC, id",
            (product_id,)
        )
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def update_media_caption(self, media_id: int, caption: str) -> bool:
        """
        Обновляет caption для конкретного медиа.
        
        Args:
            media_id: ID медиа-записи
            caption: Новый caption
            
        Returns:
            True если медиа было обновлено, False если не найдено
        """
        try:
            cursor = self.execute_query(
                "UPDATE product_media SET caption = ? WHERE id = ?",
                (caption, media_id)
            )
            updated = cursor.rowcount > 0
            if updated:
                logger.info(f"Media {media_id} caption updated successfully")
            else:
                logger.warning(f"Media {media_id} not found for caption update")
            return updated
        except sqlite3.Error as e:
            logger.error(f"Error updating media caption {media_id}: {e}")
            raise

    # =====================================================================================
    # БЛОК 7: УПРАВЛЕНИЕ РАЗМЕРАМИ И ВАРИАНТАМИ ТОВАРОВ
    # -------------------------------------------------------------------------------------
    # Методы для работы с размерами товаров и их количеством на складе.
    # - Добавление и удаление размеров для конкретного товара.
    # - Получение информации о доступных размерах и их остатках.
    # =====================================================================================

    def add_product_variant(self, product_id: int, size_value: str, quantity: int = 1) -> None:
        """
        Добавляет вариант товара с размером.

        Args:
            product_id: ID товара
            size_value: Значение размера (например '50' или 'M')
            quantity: Количество
        """
        size_id = self.get_size_id(size_value)
        if not size_id:
            raise ValueError(f"Invalid size value: {size_value}")

        self.execute_query(
            "INSERT INTO product_variants (product_id, size_id, quantity) "
            "VALUES (?, ?, ?)",
            (product_id, size_id, quantity)
        )

    def get_size_id(self, size_value: str) -> Optional[int]:
        """
        Возвращает ID размера по его значению.

        Args:
            size_value: Значение размера (например '50' или 'M')

        Returns:
            ID размера или None если не найден
        """
        cursor = self.execute_query(
            "SELECT id FROM sizes WHERE value = ?",
            (size_value,)
        )
        result = cursor.fetchone()
        return result[0] if result else None

    def get_available_sizes(self, product_id: int) -> dict:
        """Возвращает размеры в формате {size_value: quantity}"""
        cursor = self.execute_query("""
            SELECT s.value, pv.quantity 
            FROM product_variants pv
            JOIN sizes s ON pv.size_id = s.id
            WHERE pv.product_id = ?
        """, (product_id,))
        return {row[0]: row[1] for row in cursor.fetchall()}

    def get_detailed_available_sizes(self, product_id: int) -> dict:
        """
        Возвращает детальную информацию о размерах, включая статус резерва.
        Формат: {size_value: {'quantity': int, 'is_reserved': bool}}
        """
        # Получаем все варианты размеров и их количество
        cursor = self.execute_query("""
            SELECT s.id, s.value, pv.quantity
            FROM product_variants pv
            JOIN sizes s ON pv.size_id = s.id
            WHERE pv.product_id = ?
        """, (product_id,))
        all_sizes = cursor.fetchall()

        # Получаем ID всех зарезервированных размеров для этого товара
        cursor = self.execute_query("""
            SELECT size_id FROM reservations
            WHERE product_id = ? AND status IN ('active', 'temporary')
        """, (product_id,))
        reserved_size_ids = {row[0] for row in cursor.fetchall()}

        # Формируем итоговый словарь
        detailed_sizes = {}
        for size_id, size_value, quantity in all_sizes:
            detailed_sizes[size_value] = {
                'quantity': quantity,
                'is_reserved': size_id in reserved_size_ids
            }
        return detailed_sizes

    def add_product_size(self, product_id: int, size_value: str, quantity: int = 1) -> None:
        """Добавляет размер к товару"""
        size_id = self.get_size_id(size_value)
        if not size_id:
            raise ValueError(f"Invalid size value: {size_value}")

        self.execute_query(
            "INSERT OR REPLACE INTO product_variants (product_id, size_id, quantity) "
            "VALUES (?, ?, ?)",
            (product_id, size_id, quantity)
        )

    def remove_product_size(self, product_id: int, size_value: str) -> None:
        """Удаляет размер у товара"""
        size_id = self.get_size_id(size_value)
        if not size_id:
            return

        self.execute_query(
            "DELETE FROM product_variants WHERE product_id = ? AND size_id = ?",
            (product_id, size_id)
        )

    def get_product_variant_qty(self, product_id: int, size_value: str) -> int:
        """
        Получает количество единиц выбранного размера для товара.

        Args:
            product_id: ID товара
            size_value: Значение размера (например '50' или 'M')

        Returns:
            Количество единиц товара данного размера (0 если размер отсутствует)
        """
        size_id = self.get_size_id(size_value)
        if not size_id:
            return 0

        cursor = self.execute_query(
            "SELECT quantity FROM product_variants "
            "WHERE product_id = ? AND size_id = ?",
            (product_id, size_id))

        result = cursor.fetchone()
        return result[0] if result else 0

    # =====================================================================================
    # БЛОК 8: ФИЛЬТРАЦИЯ И ПОИСК ПО КАТАЛОГУ
    # -------------------------------------------------------------------------------------
    # Методы, отвечающие за поиск и фильтрацию товаров в каталоге.
    # - Получение товаров по различным критериям (категория, бренд, сезон, размер).
    # - Проверка существования товаров по комбинации фильтров.
    # - Получение списков уникальных значений для построения меню фильтров.
    # =====================================================================================

    def get_filtered_product_count(self, category=None, subcategory=None, size=None, season=None, brand=None, sizes: list = None) -> int:
        """
        Возвращает количество товаров, отфильтрованных по переданным параметрам.
        Поддерживает фильтрацию по: категория, подкатегория, размер, сезон, бренд.
        Поддерживает фильтрацию по одному размеру (size) или списку размеров (sizes).
        Показывает только активные товары.
        """
        query = "SELECT COUNT(DISTINCT p.id) FROM products p WHERE p.is_active = 1"
        params = []

        if category:
            query += " AND p.category = ?"
            params.append(category)
        if subcategory:
            query += " AND p.subcategory = ?"
            params.append(subcategory)
        if season:
            if season == 'надходження':
                query += " AND p.created_at >= '2025-08-20'"
            else:
                query += " AND p.season = ?"
                params.append(season)
        if brand:
            query += " AND p.brand = ?"
            params.append(brand)

        # Новая логика для размеров
        if sizes:
            # Если передан список размеров
            placeholders = ','.join('?' for _ in sizes)
            query += f"""
                AND EXISTS (
                    SELECT 1 FROM product_variants pv
                    JOIN sizes s ON pv.size_id = s.id
                    WHERE pv.product_id = p.id AND s.value IN ({placeholders}) AND pv.quantity > 0
                )
            """
            params.extend(sizes)
        elif size:
            # Старая логика для одного размера
            query += " AND EXISTS (SELECT 1 FROM product_variants pv JOIN sizes s ON pv.size_id = s.id WHERE pv.product_id = p.id AND s.value = ? AND pv.quantity > 0)"
            params.append(size)

        cursor = self.execute_query(query, tuple(params))
        return cursor.fetchone()[0]

    def get_filtered_product_media(self, category=None, subcategory=None, size=None, season=None, brand=None, sizes: list = None) -> list:
        """
        Возвращает список медиа товаров, отфильтрованных по переданным параметрам.
        Поддерживает фильтрацию по: категория, подкатегория, размер, сезон, бренд.
        Поддерживает фильтрацию по одному размеру (size) или списку размеров (sizes).
        Показывает только активные товары.
        """
        query = """
            SELECT pm.id, pm.product_id, pm.telegram_file_id, pm.media_type, pm.is_main, pm.caption
            FROM product_media pm
            JOIN products p ON pm.product_id = p.id
            WHERE pm.is_main = 1 AND p.is_active = 1
        """
        params = []
        if category:
            query += " AND p.category = ?"
            params.append(category)
        if subcategory:
            query += " AND p.subcategory = ?"
            params.append(subcategory)
        if season:
            if season == 'надходження':
                query += " AND p.created_at >= '2025-08-20'"
            else:
                query += " AND p.season = ?"
                params.append(season)
        if brand:
            query += " AND p.brand = ?"
            params.append(brand)

        # Новая логика для размеров
        if sizes:
            # Если передан список размеров
            placeholders = ','.join('?' for _ in sizes)
            query += f"""
                AND EXISTS (
                    SELECT 1 FROM product_variants pv
                    JOIN sizes s ON pv.size_id = s.id
                    WHERE pv.product_id = p.id AND s.value IN ({placeholders}) AND pv.quantity > 0
                )
            """
            params.extend(sizes)
        elif size:
            # Старая логика для одного размера
            query += " AND EXISTS (SELECT 1 FROM product_variants pv JOIN sizes s ON pv.size_id = s.id WHERE pv.product_id = p.id AND s.value = ? AND pv.quantity > 0)"
            params.append(size)

        query += " ORDER BY p.id DESC, pm.id"
        logger.debug(f"get_filtered_product_media: SQL query={query}")
        logger.debug(f"get_filtered_product_media: params={params}")
        cursor = self.execute_query(query, tuple(params))
        result = [list(row) for row in cursor.fetchall()]
        logger.debug(f"get_filtered_product_media: found {len(result)} products")
        return result

    def get_all_products(self) -> list:
        """
        Возвращает список медиа всех товаров (активных и неактивных).
        """
        query = """
            SELECT pm.id, pm.product_id, pm.telegram_file_id, pm.media_type, pm.is_main, pm.caption
            FROM product_media pm
            JOIN products p ON pm.product_id = p.id
            WHERE pm.is_main = 1  AND p.is_active = 0
            ORDER BY p.id DESC, pm.id
        """
        logger.debug(f"get_all_products: SQL query={query}")
        cursor = self.execute_query(query)
        result = [list(row) for row in cursor.fetchall()]
        logger.debug(f"get_all_products: found {len(result)} products")
        return result

    def get_all_inactive_products(self) -> list:
        """
        Возвращает список медиа всех неактивных товаров.
        """
        query = """
            SELECT pm.id, pm.product_id, pm.telegram_file_id, pm.media_type, pm.is_main, pm.caption
            FROM product_media pm
            JOIN products p ON pm.product_id = p.id
            WHERE pm.is_main = 1 AND p.is_active = 0
            ORDER BY p.id DESC, pm.id
        """
        logger.debug(f"get_all_inactive_products: SQL query={query}")
        cursor = self.execute_query(query)
        result = [list(row) for row in cursor.fetchall()]
        logger.debug(f"get_all_inactive_products: found {len(result)} products")
        return result

    def get_all_brands(self) -> List[str]:
        """Возвращает список всех уникальных брендов из таблицы products."""
        cursor = self.execute_query(
            "SELECT DISTINCT brand FROM products WHERE brand IS NOT NULL ORDER BY brand"
        )
        return [row[0] for row in cursor.fetchall()]

    def category_exists(self, category: str) -> bool:
        """Возвращает True, если есть хотя бы один активный товар с данной категорией."""
        cursor = self.execute_query(
            "SELECT 1 FROM products WHERE is_active = 1 AND category = ? LIMIT 1",
            (category,)
        )
        return cursor.fetchone() is not None

    def subcategory_exists(self, subcategory: str) -> bool:
        """Возвращает True, если есть хотя бы один активный товар с данной подкатегорией."""
        cursor = self.execute_query(
            "SELECT 1 FROM products WHERE is_active = 1 AND subcategory = ? LIMIT 1",
            (subcategory,)
        )
        return cursor.fetchone() is not None

    def season_exists(self, season: str) -> bool:
        """Возвращает True, если есть хотя бы один активный товар с данным сезоном."""
        cursor = self.execute_query(
            "SELECT 1 FROM products WHERE is_active = 1 AND season = ? LIMIT 1",
            (season,)
        )
        return cursor.fetchone() is not None

    def brand_exists(self, brand: str) -> bool:
        """Возвращает True, если есть хотя бы один активный товар с данным брендом."""
        cursor = self.execute_query(
            "SELECT 1 FROM products WHERE is_active = 1 AND brand = ? LIMIT 1",
            (brand,)
        )
        return cursor.fetchone() is not None

    def size_exists(self, size: str) -> bool:
        """Возвращает True, если есть хотя бы один активный товар с данным размером (через product_variants)."""
        cursor = self.execute_query(
            """
            SELECT 1 FROM product_variants pv
            JOIN sizes s ON pv.size_id = s.id
            JOIN products p ON pv.product_id = p.id
            WHERE p.is_active = 1 AND s.value = ? AND pv.quantity > 0 LIMIT 1
            """,
            (size,)
        )
        return cursor.fetchone() is not None

    def brand_exists_with_filters(self, brand: str, season: str = None, category: str = None, subcategory: str = None) -> bool:
        """
        Проверяет, существует ли хотя бы один активный товар с указанным брендом
        с учетом фильтров по сезону, категории и подкатегории.

        Args:
            brand: Название бренда
            season: Название сезона (опционально)
            category: Название категории (опционально)
            subcategory: Название подкатегории (опционально)

        Returns:
            True, если товар существует, иначе False
        """
        query = """
            SELECT 1 FROM products p
            WHERE p.is_active = 1 AND p.brand = ?
        """
        params = [brand]

        if season:
            query += " AND p.season = ?"
            params.append(season)
        
        if category:
            query += " AND p.category = ?"
            params.append(category)

        if subcategory:
            query += " AND p.subcategory = ?"
            params.append(subcategory)

        query += " LIMIT 1"

        cursor = self.execute_query(query, tuple(params))
        return cursor.fetchone() is not None

    def get_unique_categories_for_filters(self, **filters) -> list[str]:
        """
        Возвращает список уникальных категорий для заданных фильтров.
        Используется для определения, нужно ли показывать сложную или простую клавиатуру размеров.

        Args:
            **filters: Словарь с фильтрами (brand, season, etc.)

        Returns:
            Список названий категорий.
        """
        query = "SELECT DISTINCT p.category FROM products p WHERE p.is_active = 1"
        params = []

        # Собираем только валидные ключи для таблицы products
        valid_keys = ['subcategory', 'season', 'brand']
        
        for key, value in filters.items():
            if key in valid_keys and value is not None:
                query += f" AND p.{key} = ?"
                params.append(value)
        
        # Отдельно обрабатываем фильтр по размеру, если он есть
        if 'size' in filters and filters['size'] is not None:
            query += " AND EXISTS (SELECT 1 FROM product_variants pv JOIN sizes s ON pv.size_id = s.id WHERE pv.product_id = p.id AND s.value = ? AND pv.quantity > 0)"
            params.append(filters['size'])
        
        # Исключаем категории, которые None
        query += " AND p.category IS NOT NULL"

        cursor = self.execute_query(query, tuple(params))
        return [row[0] for row in cursor.fetchall()]

    def check_filter_combination_exists(self, **filters) -> bool:
        """
        Универсальная проверка существования товара по любой комбинации фильтров.
        Показывает только активные товары.

        Args:
            **filters: Словарь с фильтрами, например:
                       {'brand': 'Adidas', 'season': 'весна-літо', 'size': '50'}

        Returns:
            True, если хотя бы один товар соответствует всем фильтрам, иначе False.
        """
        query = "SELECT 1 FROM products p WHERE p.is_active = 1"
        params = []

        # Собираем только валидные ключи для таблицы products
        valid_keys = ['category', 'subcategory', 'season', 'brand']
        
        for key, value in filters.items():
            if key in valid_keys and value is not None:
                query += f" AND p.{key} = ?"
                params.append(value)

        # Отдельно обрабатываем фильтр по размеру
        if 'size' in filters and filters['size'] is not None:
            query += " AND EXISTS (SELECT 1 FROM product_variants pv JOIN sizes s ON pv.size_id = s.id WHERE pv.product_id = p.id AND s.value = ? AND pv.quantity > 0)"
            params.append(filters['size'])

        query += " LIMIT 1"
        
        cursor = self.execute_query(query, tuple(params))
        return cursor.fetchone() is not None

    def subcategory_exists_in_season(self, subcategory: str, category: str, season: str) -> bool:
        """
        Проверяет, существует ли хотя бы один активный товар с указанной подкатегорией
        в указанной категории и сезоне.

        Args:
            subcategory: Название подкатегории
            category: Название категории
            season: Название сезона

        Returns:
            True, если товар существует, иначе False
        """
        query = """
            SELECT 1 FROM products p
            WHERE p.is_active = 1 AND p.subcategory = ? AND p.category = ? AND p.season = ?
            LIMIT 1
        """
        cursor = self.execute_query(query, (subcategory, category, season))
        return cursor.fetchone() is not None

    def category_exists_in_season(self, category: str, season: str) -> bool:
        """
        Проверяет, существует ли хотя бы один активный товар с указанной категорией
        в указанном сезоне.

        Args:
            category: Название категории
            season: Название сезона

        Returns:
            True, если товар существует, иначе False
        """
        query = """
            SELECT 1 FROM products p
            WHERE p.is_active = 1 AND p.category = ? AND p.season = ?
            LIMIT 1
        """
        cursor = self.execute_query(query, (category, season))
        return cursor.fetchone() is not None

    def size_exists_in_category(self, size_value: str, category: str, subcategory: str = None, season: str = None) -> bool:
        """
        Проверяет, существует ли хотя бы один активный товар с указанным размером
        в указанной категории (и, опционально, подкатегории и сезоне).

        Args:
            size_value: Значение размера (например, '50' или 'L')
            category: Название категории
            subcategory: Название подкатегории (опционально)
            season: Название сезона (опционально)

        Returns:
            True, если товар существует, иначе False
        """
        query = """
            SELECT 1 FROM products p
            JOIN product_variants pv ON p.id = pv.product_id
            JOIN sizes s ON pv.size_id = s.id
            WHERE p.is_active = 1 AND s.value = ? AND p.category = ? AND pv.quantity > 0
        """
        params = [size_value, category]

        if subcategory:
            query += " AND p.subcategory = ?"
            params.append(subcategory)
        
        if season:
            query += " AND p.season = ?"
            params.append(season)

        query += " LIMIT 1"

        cursor = self.execute_query(query, tuple(params))
        return cursor.fetchone() is not None

    # =====================================================================================
    # БЛОК 9: УПРАВЛЕНИЕ ЗАПАСАМИ И ПОСТУПЛЕНИЯМИ
    # -------------------------------------------------------------------------------------
    # Методы для учета товаров на складе.
    # - Регистрация поступлений новых товаров (оприходование).
    # - Автоматическая деактивация товара, если его остатки на складе равны нулю.
    # =====================================================================================

    def register_inventory_receipt(self, product_id: int, size_value: str, quantity: int, 
                                  purchase_price: float, admin_id: int, notes: str = None) -> int:
        """
        Регистрирует поступление товара на склад.
        
        Args:
            product_id: ID товара
            size_value: Значение размера (если есть)
            quantity: Количество
            purchase_price: Закупочная цена за единицу
            admin_id: ID администратора, который регистрирует поступление
            notes: Дополнительные заметки
            
        Returns:
            ID записи о поступлении
        """
        size_id = self.get_size_id(size_value) if size_value else None
        
        # Добавляем запись о поступлении
        cursor = self.execute_query(
            "INSERT INTO inventory_receipts (product_id, size_id, quantity, purchase_price, admin_id, notes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (product_id, size_id, quantity, purchase_price, admin_id, notes)
        )
        receipt_id = cursor.lastrowid
        
        # Обновляем количество в product_variants
        if size_id:
            # Проверяем, есть ли уже такой вариант
            cursor = self.execute_query(
                "SELECT quantity FROM product_variants WHERE product_id = ? AND size_id = ?",
                (product_id, size_id)
            )
            existing = cursor.fetchone()
            
            if existing:
                # Увеличиваем количество
                self.execute_query(
                    "UPDATE product_variants SET quantity = quantity + ? WHERE product_id = ? AND size_id = ?",
                    (quantity, product_id, size_id)
                )
            else:
                # Создаем новый вариант
                self.execute_query(
                    "INSERT INTO product_variants (product_id, size_id, quantity) VALUES (?, ?, ?)",
                    (product_id, size_id, quantity)
                )
        
        logger.info(f"Зарегистрировано поступление: товар {product_id}, размер {size_value}, количество {quantity}")
        return receipt_id

    def _check_and_deactivate_product_if_out_of_stock(self, product_id: int, admin_id: int):
        """
        Проверяет общий остаток товара по всем размерам.
        Если остаток равен 0, деактивирует товар.
        """
        cursor = self.execute_query(
            "SELECT SUM(quantity) FROM product_variants WHERE product_id = ?",
            (product_id,)
        )
        total_quantity = cursor.fetchone()[0]

        # Если total_quantity is None (нет вариантов) или 0, деактивируем
        if not total_quantity or total_quantity == 0:
            try:
                self.deactivate_product(
                    product_id,
                    admin_id,
                    reason="Автоматична деактивація: закінчився товар"
                )
                logger.info(f"Товар {product_id} автоматично деактивовано, оскільки закінчився на складі.")
            except Exception as e:
                logger.error(f"Помилка автоматичної деактивації товару {product_id}: {e}")

    # =====================================================================================
    # БЛОК 10: УПРАВЛЕНИЕ ЗАКАЗАМИ И ПРОДАЖАМИ
    # -------------------------------------------------------------------------------------
    # Весь жизненный цикл заказа: от создания до завершения.
    # - Создание нового заказа из корзины.
    # - Подтверждение продажи админом (списание товара со склада).
    # - Отмена заказа.
    # - Получение списка заказов (всех, ожидающих, по пользователю).
    # - Получение детальной информации о конкретном заказе.
    # =====================================================================================

    def create_sale(self, user_id: int, cart_items: list, discount_amount: float = 0) -> int:
        """
        Создает заказ из корзины пользователя.
        
        Args:
            user_id: ID пользователя
            cart_items: Список товаров из корзины
            discount_amount: Сумма скидки (применяется ко всему заказу)
            
        Returns:
            ID созданного заказа
        """
        if not cart_items:
            raise ValueError("Корзина пуста")

        from utils.functions import calculate_final_item_price
        total_amount = 0
        for item in cart_items:
            product = self.sql_get_product(item['product_id'])
            if not product:
                continue
            
            final_price = calculate_final_item_price(product, user_id)
            total_amount += final_price * item['quantity']

        # Применяем общую скидку на заказ (если есть)
        final_amount = total_amount - discount_amount
        
        # Создаем запись о продаже
        cursor = self.execute_query(
            "INSERT INTO sales (user_id, total_amount, discount_amount, final_amount) "
            "VALUES (?, ?, ?, ?)",
            (user_id, total_amount, discount_amount, final_amount)
        )
        sale_id = cursor.lastrowid
        
        # Добавляем позиции продажи
        for item in cart_items:
            product_id = item['product_id']
            size_id = item.get('size_id')
            quantity = item['quantity']
            product = self.sql_get_product(product_id)
            if product:
                unit_price = product['sale_price']
                total_price = unit_price * quantity
                purchase_price = product['purchase_price'] if product else 0
                self.execute_query(
                    "INSERT INTO sale_items (sale_id, product_id, size_id, quantity, unit_price, total_price, purchase_price) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (sale_id, product_id, size_id, quantity, unit_price, total_price, purchase_price)
                )
        # Очищаем корзину пользователя
        self.clear_cart(user_id)
        logger.info(f"Создан заказ {sale_id} для пользователя {user_id}, сумма: {final_amount}")
        return sale_id

    def complete_sale(self, sale_id: int, admin_id: int, admin_notes: str = None) -> bool:
        """
        Подтверждает продажу (списывает товар).
        
        Args:
            sale_id: ID продажи
            admin_id: ID администратора
            admin_notes: Заметки администратора
            
        Returns:
            True если продажа подтверждена
        """
        # Проверяем статус продажи
        cursor = self.execute_query(
            "SELECT status FROM sales WHERE id = ?",
            (sale_id,)
        )
        result = cursor.fetchone()
        if not result:
            raise ValueError(f"Продажа {sale_id} не найдена")
        
        status = result[0]
        if status not in ['pending', 'reserved']:
            raise ValueError(f"Продажа {sale_id} уже обработана (статус: {status})")
        
        # Проверяем, что подтверждает админ
        admin = self.sql_get_user(admin_id, 'is_admin')
        if not admin or not admin[0]:
            logger.warning(f"Пользователь {admin_id} попытался подтвердить заказ {sale_id}, но не является админом. Остатки не списаны.")
            return False

        # Списываем остатки
        logger.info(f"Начинаем списание остатков для заказа {sale_id}")
        cursor = self.execute_query(
            "SELECT product_id, size_id, quantity FROM sale_items WHERE sale_id = ?",
            (sale_id,)
        )
        items = cursor.fetchall()
        logger.info(f"Найдены следующие товары для списания: {items}")

        for product_id, size_id, quantity in items:
            if size_id:
                logger.info(f"Списываем товар {product_id}, размер {size_id}, количество {quantity}")
                update_cursor = self.execute_query(
                    "UPDATE product_variants SET quantity = quantity - ? "
                    "WHERE product_id = ? AND size_id = ? AND quantity >= ?",
                    (quantity, product_id, size_id, quantity)
                )
                if update_cursor.rowcount == 0:
                    logger.error(f"Не удалось списать товар {product_id}, размер {size_id}. Возможно, не хватило остатков.")
                else:
                    logger.info(f"Списание успешно. Затронуто строк: {update_cursor.rowcount}")

                # --- ПРОВЕРКА И АВТОМАТИЧЕСКАЯ ДЕАКТИВАЦИЯ ---
                self._check_and_deactivate_product_if_out_of_stock(product_id, admin_id)
        
        # Подтверждаем продажу
        self.execute_query(
            "UPDATE sales SET status = 'confirmed', confirmed_at = CURRENT_TIMESTAMP, admin_notes = ? WHERE id = ?",
            (admin_notes, sale_id)
        )
        logger.info(f"Продажа {sale_id} подтверждена администратором {admin_id}")
        return True

    def cancel_sale(self, sale_id: int, admin_id: int, reason: str = None) -> bool:
        """
        Отменяет продажу (возвращает товар на склад).
        
        Args:
            sale_id: ID продажи
            admin_id: ID администратора
            reason: Причина отмены
            
        Returns:
            True если продажа отменена
        """
        # Проверяем статус продажи
        cursor = self.execute_query(
            "SELECT status FROM sales WHERE id = ?",
            (sale_id,)
        )
        result = cursor.fetchone()
        if not result:
            raise ValueError(f"Продажа {sale_id} не найдена")
        
        if result[0] != 'pending':
            raise ValueError(f"Продажа {sale_id} уже обработана (статус: {result[0]})")
        
        
        
        # Отменяем продажу
        self.execute_query(
            "UPDATE sales SET status = 'cancelled', admin_notes = ? WHERE id = ?",
            (reason, sale_id)
        )
        
        logger.info(f"Продажа {sale_id} отменена администратором {admin_id}")
        return True

    def get_pending_orders_count(self) -> int:
        """
        Получает количество ожидающих подтверждения заказов.
        
        Returns:
            Количество заказов со статусом 'pending'
        """
        cursor = self.execute_query("SELECT COUNT(*) FROM sales WHERE status = 'pending'")
        count = cursor.fetchone()[0]
        return count

    def get_pending_orders(self) -> list:
        """
        Получает список ожидающих подтверждения заказов.
        
        Returns:
            Список заказов со статусом 'pending'
        """
        cursor = self.execute_query("""
            SELECT 
                s.id,
                s.user_id,
                s.total_amount,
                s.discount_amount,
                s.final_amount,
                s.created_at,
                u.first_name,
                u.last_name,
                u.user_name,
                COUNT(si.id) as items_count
            FROM sales s
            JOIN users u ON s.user_id = u.user_id
            LEFT JOIN sale_items si ON s.id = si.sale_id
            WHERE s.status = 'pending'
            GROUP BY s.id
            ORDER BY s.created_at DESC
        """)
        
        orders = []
        for row in cursor.fetchall():
            orders.append({
                'id': row[0],
                'user_id': row[1],
                'total_amount': row[2],
                'discount_amount': row[3],
                'final_amount': row[4],
                'created_at': row[5],
                'user_name': f"{row[6]} {row[7]}" if row[6] and row[7] else row[8] or f"User {row[1]}",
                'items_count': row[9]
            })
        
        return orders

    def get_user_orders(self, user_id: int) -> list:
        """
        Получает все заказы пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Список словарей с деталями заказов
        """
        cursor = self.execute_query("""
            SELECT
                s.id,
                s.total_amount,
                s.discount_amount,
                s.final_amount,
                s.status,
                s.created_at
            FROM sales s
            WHERE s.user_id = ?
            ORDER BY s.created_at DESC
        """, (user_id,))

        orders = []
        for row in cursor.fetchall():
            orders.append({
                'id': row[0],
                'total_amount': row[1],
                'discount_amount': row[2],
                'final_amount': row[3],
                'status': row[4],
                'created_at': row[5],
            })
        return orders

    def get_order_details(self, order_id: int) -> dict:
        """
        Получает детали заказа.
        
        Args:
            order_id: ID заказа
            
        Returns:
            Словарь с деталями заказа
        """
        # Основная информация о заказе
        cursor = self.execute_query("""
            SELECT 
                s.id,
                s.user_id,
                s.total_amount,
                s.discount_amount,
                s.final_amount,
                s.status,
                s.created_at,
                s.confirmed_at,
                s.admin_notes,
                u.first_name,
                u.last_name,
                u.user_name,
                u.phone
            FROM sales s
            JOIN users u ON s.user_id = u.user_id
            WHERE s.id = ?
        """, (order_id,))
        
        order_data = cursor.fetchone()
        if not order_data:
            return None
        
        # Позиции заказа
        cursor = self.execute_query("""
            SELECT 
                si.id,
                si.product_id,
                si.size_id,
                si.quantity,
                si.unit_price,
                si.total_price,
                si.purchase_price,
                si.profit,
                p.name,
                p.brand,
                p.category,
                s.value as size_value
            FROM sale_items si
            JOIN products p ON si.product_id = p.id
            LEFT JOIN sizes s ON si.size_id = s.id
            WHERE si.sale_id = ?
        """, (order_id,))
        
        items = []
        for row in cursor.fetchall():
            items.append({
                'id': row[0],
                'product_id': row[1],
                'size_id': row[2],
                'quantity': row[3],
                'unit_price': row[4],
                'total_price': row[5],
                'purchase_price': row[6],
                'profit': row[7],
                'name': row[8],
                'brand': row[9],
                'category': row[10],
                'size_value': row[11]
            })
        
        return {
            'id': order_data[0],
            'user_id': order_data[1],
            'total_amount': order_data[2],
            'discount_amount': order_data[3],
            'final_amount': order_data[4],
            'status': order_data[5],
            'created_at': order_data[6],
            'confirmed_at': order_data[7],
            'admin_notes': order_data[8],
            'user_name': f"{order_data[9]} {order_data[10]}" if order_data[9] and order_data[10] else order_data[11] or f"User {order_data[1]}",
            'user_phone': order_data[12],
            'items': items
        }

    # =====================================================================================
    # БЛОК 11: УПРАВЛЕНИЕ КОРЗИНОЙ
    # -------------------------------------------------------------------------------------
    # Методы для взаимодействия с корзиной покупок пользователя.
    # - Добавление, обновление количества и удаление товаров из корзины.
    # - Полная очистка корзины.
    # - Получение содержимого корзины и проверка наличия в ней товара.
    # =====================================================================================

    def add_to_cart(self, user_id: int, product_id: int, size_value: str = None, quantity: int = 1) -> None:
        """
        Добавляет товар в корзину пользователя или увеличивает количество, если уже есть.
        Args:
            user_id: ID пользователя
            product_id: ID товара
            size_value: Значение размера (если есть)
            quantity: Количество (по умолчанию 1)
        """
        size_id = self.get_size_id(size_value) if size_value else None
        # Проверяем, есть ли уже такая позиция
        cursor = self.execute_query(
            "SELECT id, quantity FROM cart WHERE user_id = ? AND product_id = ? AND (? IS NULL OR size_id = ?)",
            (user_id, product_id, size_id, size_id)
        )
        row = cursor.fetchone()
        if row:
            cart_id, old_qty = row
            self.execute_query(
                "UPDATE cart SET quantity = quantity + ? WHERE id = ?",
                (quantity, cart_id)
            )
        else:
            self.execute_query(
                "INSERT INTO cart (user_id, product_id, size_id, quantity) VALUES (?, ?, ?, ?)",
                (user_id, product_id, size_id, quantity)
            )

    def remove_from_cart(self, user_id: int, product_id: int, size_value: str = None, quantity: int = 1) -> bool:
        """
        Уменьшает количество товара в корзине или удаляет позицию, если quantity <= 0.
        Args:
            user_id: ID пользователя
            product_id: ID товара
            size_value: Значение размера (если есть)
            quantity: Сколько убрать (по умолчанию 1)
        Returns:
            True если позиция была удалена или уменьшена, False если не найдена
        """
        size_id = self.get_size_id(size_value) if size_value else None
        cursor = self.execute_query(
            "SELECT id, quantity FROM cart WHERE user_id = ? AND product_id = ? AND (? IS NULL OR size_id = ?)",
            (user_id, product_id, size_id, size_id)
        )
        row = cursor.fetchone()
        if not row:
            return False
        cart_id, old_qty = row
        if old_qty > quantity:
            self.execute_query(
                "UPDATE cart SET quantity = quantity - ? WHERE id = ?",
                (quantity, cart_id)
            )
        else:
            self.execute_query(
                "DELETE FROM cart WHERE id = ?",
                (cart_id,)
            )
        return True

    def clear_cart(self, user_id: int) -> int:
        """
        Очищает корзину пользователя.
        Args:
            user_id: ID пользователя
        Returns:
            Количество удалённых позиций
        """
        cursor = self.execute_query(
            "DELETE FROM cart WHERE user_id = ?",
            (user_id,)
        )
        return cursor.rowcount

    def get_cart(self, user_id: int) -> list:
        """
        Получает содержимое корзины пользователя с деталями товара и размера.
        Args:
            user_id: ID пользователя
        Returns:
            Список словарей с деталями корзины
        """
        cursor = self.execute_query(
            """
            SELECT c.id, c.product_id, c.size_id, c.quantity, c.added_at,
                   p.name, p.sale_price, p.discount, p.brand, p.category, p.subcategory, s.value as size_value
            FROM cart c
            JOIN products p ON c.product_id = p.id
            LEFT JOIN sizes s ON c.size_id = s.id
            WHERE c.user_id = ?
            ORDER BY c.added_at DESC
            """,
            (user_id,)
        )
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def update_cart_quantity(self, user_id: int, product_id: int, size_value: str = None, quantity: int = 1) -> bool:
        """
        Устанавливает точное количество товара в корзине (или удаляет, если quantity <= 0).
        Args:
            user_id: ID пользователя
            product_id: ID товара
            size_value: Значение размера (если есть)
            quantity: Новое количество
        Returns:
            True если обновлено/удалено, False если не найдена позиция
        """
        size_id = self.get_size_id(size_value) if size_value else None
        cursor = self.execute_query(
            "SELECT id FROM cart WHERE user_id = ? AND product_id = ? AND (? IS NULL OR size_id = ?)",
            (user_id, product_id, size_id, size_id)
        )
        row = cursor.fetchone()
        if not row:
            return False
        cart_id = row[0]
        if quantity > 0:
            self.execute_query(
                "UPDATE cart SET quantity = ? WHERE id = ?",
                (quantity, cart_id)
            )
        else:
            self.execute_query(
                "DELETE FROM cart WHERE id = ?",
                (cart_id,)
            )
        return True

    def is_product_in_cart(self, user_id: int, product_id: int, size_value: str = None) -> bool:
        """
        Проверяет, находится ли товар (и размер) в корзине пользователя.
        Args:
            user_id: ID пользователя
            product_id: ID товара
            size_value: Значение размера (если есть)
        Returns:
            True если товар в корзине, False если нет
        """
        size_id = self.get_size_id(size_value) if size_value else None
        cursor = self.execute_query(
            "SELECT 1 FROM cart WHERE user_id = ? AND product_id = ? AND (? IS NULL OR size_id = ?)",
            (user_id, product_id, size_id, size_id)
        )
        return cursor.fetchone() is not None

    def get_cart_count(self, user_id: int) -> int:
        """
        Возвращает количество товаров в корзине пользователя.
        """
        cart_items = self.get_cart(user_id)
        if not cart_items:
            return 0
        return sum(item.get("quantity", 1) for item in cart_items)

    # =====================================================================================
    # БЛОК 12: УПРАВЛЕНИЕ ИЗБРАННЫМ
    # -------------------------------------------------------------------------------------
    # Методы для работы с персональным списком избранных товаров пользователя.
    # - Добавление и удаление товаров из избранного.
    # - Проверка, находится ли товар в избранном.
    # - Получение списка избранных товаров и их количества.
    # =====================================================================================

    def add_to_favorites(self, user_id: int, product_id: int) -> bool:
        """
        Добавляет товар в избранное пользователя.
        
        Args:
            user_id: ID пользователя
            product_id: ID товара
            
        Returns:
            True если товар был добавлен, False если уже был в избранном
        """
        if not self.is_product_in_favorites(user_id, product_id):
            self.execute_query(
                "INSERT INTO favorites (user_id, product_id) VALUES (?, ?)",
                (user_id, product_id)
            )
            logger.info(f"Product {product_id} added to favorites for user {user_id}")
            return True
        logger.warning(f"Product {product_id} already in favorites for user {user_id}")
        return False

    def remove_from_favorites(self, user_id: int, product_id: int) -> bool:
        """
        Удаляет товар из избранного пользователя.
        
        Args:
            user_id: ID пользователя
            product_id: ID товара
            
        Returns:
            True если товар был удален, False если не найден
        """
        cursor = self.execute_query(
            "DELETE FROM favorites WHERE user_id = ? AND product_id = ?",
            (user_id, product_id)
        )
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"Product {product_id} removed from favorites for user {user_id}")
        else:
            logger.warning(f"Product {product_id} not found in favorites for user {user_id}")
        return deleted

    def is_product_in_favorites(self, user_id: int, product_id: int) -> bool:
        """
        Проверяет, находится ли товар в избранном пользователя.
        
        Args:
            user_id: ID пользователя
            product_id: ID товара
            
        Returns:
            True если товар в избранном, False если нет
        """
        # Убеждаемся, что параметры являются числами
        try:
            user_id = int(user_id)
            product_id = int(product_id)
        except (ValueError, TypeError):
            logger.warning(f"is_product_in_favorites: invalid parameters - user_id={user_id} ({type(user_id)}), product_id={product_id} ({type(product_id)})")
            return False
        
        cursor = self.execute_query(
            "SELECT 1 FROM favorites WHERE user_id = ? AND product_id = ?",
            (user_id, product_id)
        )
        result = cursor.fetchone() is not None
        logger.debug(f"is_product_in_favorites: user_id={user_id}, product_id={product_id}, result={result}")
        return result

    def get_user_favorites(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Получает список товаров, добавленных в избранное пользователем.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Список словарей с информацией о товарах
        """
        cursor = self.execute_query(
            """
            SELECT f.id, f.product_id, p.name, p.sale_price, p.brand, p.category, p.subcategory, f.added_at
            FROM favorites f
            JOIN products p ON f.product_id = p.id
            WHERE f.user_id = ?
            ORDER BY f.added_at DESC
            """,
            (user_id,)
        )
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_favorite_product_count(self, user_id: int) -> int:
        """
        Возвращает количество реально существующих товаров в избранном пользователя.
        """
        cursor = self.execute_query(
            "SELECT COUNT(*) FROM favorites f JOIN products p ON f.product_id = p.id WHERE f.user_id = ?",
            (user_id,)
        )
        return cursor.fetchone()[0]

    def get_product_favorites_count(self, product_id: int) -> int:
        """Возвращает количество добавлений товара в избранное среди всех пользователей."""
        if not isinstance(product_id, int) or product_id <= 0:
            logger.warning(f"get_product_favorites_count: invalid product_id={product_id}")
            return 0
        cursor = self.execute_query(
            "SELECT COUNT(*) FROM favorites WHERE product_id = ?",
            (product_id,)
        )
        result = cursor.fetchone()
        return result[0] if result else 0

    def clear_user_favorites(self, user_id: int) -> int:
        """
        Очищает избранное пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Количество удаленных записей
        """
        cursor = self.execute_query(
            "DELETE FROM favorites WHERE user_id = ?",
            (user_id,)
        )
        deleted_count = cursor.rowcount
        logger.info(f"Cleared {deleted_count} favorite records for user {user_id}")
        return deleted_count

    # =====================================================================================
    # БЛОК 13: УПРАВЛЕНИЕ РЕЗЕРВАМИ И ЛИСТОМ ОЖИДАНИЯ
    # -------------------------------------------------------------------------------------
    # Функционал для работы с товарами, которых временно нет в наличии.
    # - Резервирование товаров из заказа.
    # - Добавление пользователей в лист ожидания на конкретный размер.
    # - Уведомление пользователей при поступлении товара.
    # =====================================================================================

    def add_to_waiting_list(self, user_id: int, product_id: int, size_value: str) -> bool:
        """
        Добавляет пользователя в лист ожидания на конкретный товар и размер.
        Возвращает True, если пользователь был успешно добавлен, False - если он уже в списке.
        """
        size_id = self.get_size_id(size_value)
        if not size_id:
            logger.warning(f"Attempted to add to waiting list with invalid size: {size_value}")
            return False

        # Проверяем, не находится ли пользователь уже в списке ожидания
        cursor = self.execute_query(
            "SELECT 1 FROM waiting_list WHERE user_id = ? AND product_id = ? AND size_id = ?",
            (user_id, product_id, size_id)
        )
        if cursor.fetchone():
            logger.info(f"User {user_id} is already in the waiting list for product {product_id}, size {size_value}")
            return False # Уже в списке

        # Добавляем пользователя в список
        self.execute_query(
            "INSERT INTO waiting_list (user_id, product_id, size_id) VALUES (?, ?, ?)",
            (user_id, product_id, size_id)
        )
        logger.info(f"User {user_id} added to waiting list for product {product_id}, size {size_value}")
        return True

    def get_active_reservations(self) -> List[Dict[str, Any]]:
        """Возвращает список всех активных резервов с детальной информацией."""
        query = """
            SELECT
                r.id as reservation_id,
                r.created_at,
                p.name as product_name,
                s.value as size_value,
                u.first_name || ' ' || u.last_name as user_name
            FROM reservations r
            JOIN products p ON r.product_id = p.id
            JOIN sizes s ON r.size_id = s.id
            JOIN users u ON r.user_id = u.user_id
            WHERE r.status IN ('active', 'temporary')
            ORDER BY r.created_at DESC
        """
        cursor = self.execute_query(query)
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_reservation_details(self, reservation_id: int) -> Optional[Dict[str, Any]]:
        """Возвращает детальную информацию по одному резерву."""
        query = """
            SELECT
                r.id as reservation_id,
                r.order_id,
                r.status,
                r.created_at,
                r.expires_at,
                p.id as product_id,
                p.name as product_name,
                s.value as size_value,
                u.user_id as customer_id,
                u.first_name || ' ' || u.last_name as customer_name,
                u.phone as customer_phone,
                a.user_id as admin_id,
                a.first_name as admin_name
            FROM reservations r
            JOIN products p ON r.product_id = p.id
            JOIN sizes s ON r.size_id = s.id
            JOIN users u ON r.user_id = u.user_id
            JOIN users a ON r.admin_id = a.user_id
            WHERE r.id = ?
        """
        cursor = self.execute_query(query, (reservation_id,))
        result = cursor.fetchone()
        if not result:
            return None
        columns = [column[0] for column in cursor.description]
        return dict(zip(columns, result))

    def update_reservation_status(self, reservation_id: int, status: str) -> bool:
        """
        Обновляет статус резерва.

        Args:
            reservation_id: ID резерва
            status: Новый статус ('completed' или 'cancelled')

        Returns:
            True если статус обновлен
        """
        if status not in ['completed', 'cancelled']:
            raise ValueError("Недопустимый статус")

        # При отмене резерва количество не возвращается, так как оно не списывалось при создании.
        # Мы просто меняем статус резерва.
        self.execute_query(
            "UPDATE reservations SET status = ? WHERE id = ?",
            (status, reservation_id)
        )
        logger.info(f"Статус резерва {reservation_id} изменен на {status}")
        return True

    def complete_sale_from_reservation(self, order_id: int, admin_id: int) -> bool:
        """
        Подтверждает продажу из резерва.
        """
        self.complete_sale(order_id, admin_id, admin_notes="Продажа из резерва")
        self.execute_query(
            "UPDATE reservations SET status = 'completed' WHERE order_id = ?",
            (order_id,)
        )
        return True

    def clear_waiting_list_and_get_users(self, product_id: int, size_id: int) -> List[int]:
        """
        Очищает лист ожидания для конкретного товара и размера и возвращает список пользователей.
        """
        cursor = self.execute_query(
            "SELECT user_id FROM waiting_list WHERE product_id = ? AND size_id = ? AND status = 'active'",
            (product_id, size_id)
        )
        user_ids = [row[0] for row in cursor.fetchall()]

        if user_ids:
            self.execute_query(
                "DELETE FROM waiting_list WHERE product_id = ? AND size_id = ?",
                (product_id, size_id)
            )
            logger.info(f"Очищен лист ожидания для товара {product_id}, размер {size_id}. Пользователи: {user_ids}")

        return user_ids

    def create_reservation_from_order(self, order_id: int, admin_id: int) -> bool:
        """
        Создает резервы для всех товаров в заказе и обновляет статус заказа.
        """
        # 1. Проверяем статус заказа
        cursor = self.execute_query("SELECT status, user_id FROM sales WHERE id = ?", (order_id,))
        order_data = cursor.fetchone()
        if not order_data:
            raise ValueError(f"Заказ {order_id} не найден.")
        if order_data[0] != 'pending':
            raise ValueError(f"Заказ {order_id} уже обработан (статус: {order_data[0]}).")
        
        customer_user_id = order_data[1]

        # 2. Получаем все товары из заказа
        cursor = self.execute_query(
            "SELECT product_id, size_id, quantity FROM sale_items WHERE sale_id = ?",
            (order_id,)
        )
        sale_items = cursor.fetchall()
        if not sale_items:
            raise ValueError(f"В заказе {order_id} нет товаров.")

        # 3. Создаем резервы для каждого товара
        for product_id, size_id, quantity in sale_items:
            if not size_id:
                logger.warning(f"Пропуск резерва для товара {product_id} в заказе {order_id} - не указан размер.")
                continue
            
            # Проверяем, нет ли уже активного резерва на этот товар и размер
            cursor = self.execute_query(
                "SELECT id FROM reservations WHERE product_id = ? AND size_id = ? AND status = 'active'",
                (product_id, size_id)
            )
            if cursor.fetchone():
                logger.warning(f"Резерв для товара {product_id} размер {size_id} уже существует. Пропуск.")
                continue

            self.execute_query(
                "INSERT INTO reservations (user_id, admin_id, product_id, size_id, quantity, status, order_id) "
                "VALUES (?, ?, ?, ?, ?, 'active', ?)",
                (customer_user_id, admin_id, product_id, size_id, quantity, order_id)
            )
            logger.info(f"Создан резерв для заказа {order_id}: товар {product_id}, размер {size_id}")

        # 4. Обновляем статус заказа
        self.execute_query(
            "UPDATE sales SET status = 'reserved' WHERE id = ?",
            (order_id,)
        )
        logger.info(f"Статус заказа {order_id} изменен на 'reserved'.")
        
        return True

    # =====================================================================================
    # БЛОК 14: ОТСЛЕЖИВАНИЕ ПРОСМОТРОВ ТОВАРОВ
    # -------------------------------------------------------------------------------------
    # Сбор и анализ данных о взаимодействии пользователей с каталогом.
    # - Запись каждого просмотра товара.
    # - Получение истории просмотров для пользователя.
    # - Агрегация статистики по просмотрам для товаров и пользователей.
    # =====================================================================================

    def add_product_view(self, user_id: int, product_id: int, media_id: Optional[int] = None, 
                        view_type: str = 'slider', view_duration: int = 0) -> None:
        """
        Добавляет запись о просмотре товара пользователем.
        
        Args:
            user_id: ID пользователя
            product_id: ID товара
            media_id: ID медиа (опционально)
            view_type: Тип просмотра ('slider', 'single', 'gallery')
            view_duration: Длительность просмотра в секундах
        """
        try:
            self.execute_query(
                "INSERT INTO product_views (user_id, product_id, media_id, view_type, view_duration) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, product_id, media_id, view_type, view_duration)
            )
            logger.debug(f"Added product view: user_id={user_id}, product_id={product_id}, type={view_type}")
            
            # Добавляем просмотр к активности пользователя
            from utils.lexicon import DISCOUNT_SETTINGS
            self.increment_activity_count(user_id, DISCOUNT_SETTINGS['VIEW_ACTIVITY_WEIGHT'])
            
        except sqlite3.Error as e:
            logger.error(f"Error adding product view: {e}")

    def get_user_product_views(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Получает историю просмотров товаров пользователем.
        
        Args:
            user_id: ID пользователя
            limit: Максимальное количество записей
            
        Returns:
            Список словарей с информацией о просмотрах
        """
        cursor = self.execute_query(
            """
            SELECT pv.id, pv.product_id, pv.media_id, pv.view_type, pv.view_duration, 
                   pv.created_at, p.name as product_name, p.brand, p.category
            FROM product_views pv
            JOIN products p ON pv.product_id = p.id
            WHERE pv.user_id = ?
            ORDER BY pv.created_at DESC
            LIMIT ?
            """,
            (user_id, limit)
        )
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_user_unique_product_views(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Получает уникальную историю просмотров товаров пользователем (без дублей).
        Для каждого товара берется только последний просмотр.
        
        Args:
            user_id: ID пользователя
            limit: Максимальное количество записей
            
        Returns:
            Список словарей с информацией о просмотрах
        """
        cursor = self.execute_query(
            """
            SELECT pv.id, pv.product_id, pv.media_id, pv.view_type, pv.view_duration, 
                   pv.created_at, p.name as product_name, p.brand, p.category
            FROM product_views pv
            JOIN products p ON pv.product_id = p.id
            WHERE pv.user_id = ?
            AND pv.id = (
                SELECT MAX(pv2.id) 
                FROM product_views pv2 
                WHERE pv2.user_id = pv.user_id AND pv2.product_id = pv.product_id
            )
            ORDER BY pv.created_at DESC
            LIMIT ?
            """,
            (user_id, limit)
        )
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_product_view_stats(self, product_id: int) -> Dict[str, Any]:
        """
        Получает статистику просмотров для конкретного товара.
        
        Args:
            product_id: ID товара
            
        Returns:
            Словарь со статистикой просмотров
        """
        cursor = self.execute_query(
            """
            SELECT 
                COUNT(*) as total_views,
                COUNT(DISTINCT user_id) as unique_viewers,
                AVG(view_duration) as avg_duration,
                SUM(view_duration) as total_duration,
                COUNT(CASE WHEN view_type = 'slider' THEN 1 END) as slider_views,
                COUNT(CASE WHEN view_type = 'single' THEN 1 END) as single_views,
                COUNT(CASE WHEN view_type = 'gallery' THEN 1 END) as gallery_views
            FROM product_views 
            WHERE product_id = ?
            """,
            (product_id,)
        )
        result = cursor.fetchone()
        if result:
            return {
                'total_views': result[0],
                'unique_viewers': result[1],
                'avg_duration': result[2] or 0,
                'total_duration': result[3] or 0,
                'slider_views': result[4],
                'single_views': result[5],
                'gallery_views': result[6]
            }
        return {
            'total_views': 0,
            'unique_viewers': 0,
            'avg_duration': 0,
            'total_duration': 0,
            'slider_views': 0,
            'single_views': 0,
            'gallery_views': 0
        }

    def get_user_view_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Получает статистику просмотров пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Словарь со статистикой просмотров пользователя
        """
        cursor = self.execute_query(
            """
            SELECT 
                COUNT(*) as total_views,
                COUNT(DISTINCT product_id) as unique_products,
                AVG(view_duration) as avg_duration,
                SUM(view_duration) as total_duration,
                COUNT(CASE WHEN view_type = 'slider' THEN 1 END) as slider_views,
                COUNT(CASE WHEN view_type = 'single' THEN 1 END) as single_views,
                COUNT(CASE WHEN view_type = 'gallery' THEN 1 END) as gallery_views
            FROM product_views 
            WHERE user_id = ?
            """,
            (user_id,)
        )
        result = cursor.fetchone()
        if result:
            return {
                'total_views': result[0],
                'unique_products': result[1],
                'avg_duration': result[2] or 0,
                'total_duration': result[3] or 0,
                'slider_views': result[4],
                'single_views': result[5],
                'gallery_views': result[6]
            }
        return {
            'total_views': 0,
            'unique_products': 0,
            'avg_duration': 0,
            'total_duration': 0,
            'slider_views': 0,
            'single_views': 0,
            'gallery_views': 0
        }

    def get_user_total_views(self, user_id: int) -> int:
        """
        Получает общее количество просмотров пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Общее количество просмотров
        """
        cursor = self.execute_query(
            "SELECT COUNT(*) FROM product_views WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        return result[0] if result else 0

    def delete_old_views(self, days: int = 90) -> int:
        """
        Удаляет старые записи о просмотрах.
        
        Args:
            days: Количество дней, после которых записи считаются старыми
            
        Returns:
            Количество удаленных записей
        """
        cursor = self.execute_query(
            "DELETE FROM product_views WHERE created_at < datetime('now', '-{} days')".format(days)
        )
        deleted_count = cursor.rowcount
        logger.info(f"Deleted {deleted_count} old view records (older than {days} days)")
        return deleted_count

    # =====================================================================================
    # БЛОК 15: УПРАВЛЕНИЕ СИСТЕМОЙ ЛОЯЛЬНОСТИ
    # -------------------------------------------------------------------------------------
    # Методы, связанные с программой лояльности.
    # На данный момент включает получение реферальных баллов.
    # Таблицы `loyalty_history` и `users.level` закладывают основу для
    # будушего расширения функционала.
    # =====================================================================================

    def get_user_referral_points(self, user_id: int) -> int:
        """
        Возвращает сумму реферальных баллов пользователя из истории лояльности.
        """
        cursor = self.execute_query(
            "SELECT SUM(points) FROM loyalty_history WHERE user_id = ? AND event = 'referral'",
            (user_id,)
        )
        result = cursor.fetchone()
        return int(result[0]) if result and result[0] else 0

    # =====================================================================================
    # БЛОК 16: УПРАВЛЕНИЕ АКЦИЯМИ
    # -------------------------------------------------------------------------------------
    # Методы для работы с акциями и специальными предложениями.
    # (На данный момент не реализована таблица `promotions`, но методы
    # оставлены для будущей интеграции).
    # =====================================================================================

    def get_active_promotion(self, action_type: str) -> Optional[dict]:
        """
        Проверяет, есть ли активная акция с указанным типом действия.

        Args:
            action_type: Тип действия акции (например, 'GIVE_GOLD_ON_FIRST_LOGIN')

        Returns:
            Словарь с данными акции, если она активна, иначе None
        """
        query = """
            SELECT * FROM promotions
            WHERE action_type = ? AND is_active = 1 AND
                  (start_date IS NULL OR date('now') >= start_date) AND
                  (end_date IS NULL OR date('now') <= end_date)
            LIMIT 1
        """
        cursor = self.execute_query(query, (action_type,))
        result = cursor.fetchone()
        if not result:
            return None

        columns = [column[0] for column in cursor.description]
        return dict(zip(columns, result))

    def get_all_promotions(self) -> List[dict]:
        """
        Возвращает список всех акций.

        Returns:
            Список словарей с данными акций.
        """
        query = "SELECT * FROM promotions ORDER BY created_at DESC"
        cursor = self.execute_query(query)
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    # =====================================================================================
    # БЛОК 17: УПРАВЛЕНИЕ ПОДПИСКАМИ И РАССЫЛКАМИ
    # -------------------------------------------------------------------------------------
    # Функционал для управления подписками пользователей на различные темы
    # (новые поступления, акции) и для ведения архива отправленных сообщений.
    # =====================================================================================

    def add_message_to_archive(self, name: str, content: str) -> int:
        """
        Добавляет сообщение в архив.

        Args:
            name: Название сообщения (для админки)
            content: Текст сообщения

        Returns:
            ID добавленного сообщения
        """
        cursor = self.execute_query(
            "INSERT INTO message_archive (name, content) VALUES (?, ?)",
            (name, content)
        )
        logger.info(f"Сообщение '{name}' добавлено в архив.")
        return cursor.lastrowid

    def add_archive_recipients(self, archive_id: int, user_ids: List[int]) -> None:
        """Добавляет получателей для сообщения в архиве."""
        if not user_ids:
            return
        recipient_data = [(archive_id, user_id) for user_id in user_ids]
        self.execute_query_many(
            "INSERT OR IGNORE INTO archived_message_recipients (archive_id, user_id) VALUES (?, ?)",
            recipient_data
        )

    def get_archived_messages_for_user(self, user_id: int) -> List[Dict[str, Any]]:
        """Получает все сообщения из архива, которые были отправлены пользователю."""
        cursor = self.execute_query("""
            SELECT ma.id, ma.name, ma.created_at FROM message_archive ma
            JOIN archived_message_recipients amr ON ma.id = amr.archive_id
            WHERE amr.user_id = ?
            ORDER BY ma.created_at DESC
        """, (user_id,))
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_archived_message_by_id(self, message_id: int) -> Optional[Dict[str, Any]]:
        """
        Получает одно сообщение из архива по его ID.

        Args:
            message_id: ID сообщения

        Returns:
            Словарь с данными сообщения или None, если не найдено
        """
        cursor = self.execute_query(
            "SELECT id, name, content, created_at FROM message_archive WHERE id = ?",
            (message_id,)
        )
        result = cursor.fetchone()
        if not result:
            return None
        
        columns = [column[0] for column in cursor.description]
        return dict(zip(columns, result))

    def delete_archived_message(self, message_id: int) -> bool:
        """
        Удаляет сообщение из архива по ID.

        Args:
            message_id: ID сообщения

        Returns:
            True если удаление успешно, иначе False
        """
        cursor = self.execute_query(
            "DELETE FROM message_archive WHERE id = ?",
            (message_id,)
        )
        if cursor.rowcount > 0:
            logger.info(f"Сообщение с ID {message_id} удалено из архива.")
            return True
        return False

    def add_subscription_topic(self, topic_key: str, description: str) -> None:
        """Добавляет новую тему для подписки."""
        self.execute_query(
            "INSERT OR IGNORE INTO subscriptions (topic_key, description) VALUES (?, ?)",
            (topic_key, description)
        )

    def get_subscription_topics(self) -> List[Dict[str, Any]]:
        """Получает все доступные темы для подписки."""
        cursor = self.execute_query("SELECT id, topic_key, description FROM subscriptions ORDER BY id")
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def subscribe_user(self, user_id: int, subscription_id: int, filters: Optional[Dict] = None) -> None:
        """Подписывает пользователя на тему."""
        filters_json = json.dumps(filters) if filters else None
        self.execute_query(
            "INSERT OR REPLACE INTO user_subscriptions (user_id, subscription_id, filters) VALUES (?, ?, ?)",
            (user_id, subscription_id, filters_json)
        )

    def unsubscribe_user(self, user_id: int, subscription_id: int) -> None:
        """Отписывает пользователя от темы."""
        self.execute_query(
            "DELETE FROM user_subscriptions WHERE user_id = ? AND subscription_id = ?",
            (user_id, subscription_id)
        )

    def get_user_subscriptions(self, user_id: int) -> List[Dict[str, Any]]:
        """Получает список подписок пользователя (ID темы и фильтры)."""
        cursor = self.execute_query(
            "SELECT subscription_id, filters FROM user_subscriptions WHERE user_id = ?",
            (user_id,)
        )
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_subscribers(self, topic_key: str) -> List[Dict[str, Any]]:
        """Получает список пользователей и их фильтры для темы."""
        cursor = self.execute_query("""
            SELECT us.user_id, us.filters FROM user_subscriptions us
            JOIN subscriptions s ON us.subscription_id = s.id
            WHERE s.topic_key = ?
        """, (topic_key,))
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_subscribers_for_brand(self, brand_name: str) -> List[int]:
        """Получает список ID пользователей, подписанных на новости конкретного бренда."""
        topic_key = 'brand_news'
        subscribers = self.get_subscribers(topic_key)
        
        user_ids = []
        for sub in subscribers:
            if not sub['filters']:
                continue
            try:
                filters = json.loads(sub['filters'])
                if brand_name in filters.get('brands', []):
                    user_ids.append(sub['user_id'])
            except json.JSONDecodeError:
                continue
        return user_ids

    # =====================================================================================
    # БЛОК 18: АНАЛИТИКА И ОТЧЕТЫ
    # -------------------------------------------------------------------------------------
    # Методы для сбора и агрегации данных для анализа.
    # - Формирование отчетов по продажам за период.
    # - Получение статистики по товарным запасам (общая, по категориям, брендам).
    # - Анализ популярных товаров на основе просмотров.
    # =====================================================================================

    def get_sales_report(self, start_date: str = None, end_date: str = None) -> dict:
        """
        Получает отчет по продажам за период.

        Args:
            start_date: Начальная дата (формат: 'YYYY-MM-DD')
            end_date: Конечная дата (формат: 'YYYY-MM-DD')

        Returns:
            Словарь с данными отчета
        """
        date_filter = ""
        params = []

        if start_date and end_date:
            date_filter = "WHERE s.created_at BETWEEN ? AND ?"
            params = [start_date, f"{end_date} 23:59:59"]
        elif start_date:
            date_filter = "WHERE s.created_at >= ?"
            params = [start_date]
        elif end_date:
            date_filter = "WHERE s.created_at <= ?"
            params = [f"{end_date} 23:59:59"]

        # Общая статистика
        cursor = self.execute_query(f"""
            SELECT 
                COUNT(*) as total_orders,
                SUM(CASE WHEN s.status = 'confirmed' THEN s.final_amount ELSE 0 END) as total_revenue,
                SUM(CASE WHEN s.status = 'confirmed' THEN s.discount_amount ELSE 0 END) as total_discounts,
                AVG(CASE WHEN s.status = 'confirmed' THEN s.final_amount ELSE NULL END) as avg_order_value,
                COUNT(CASE WHEN s.status = 'confirmed' THEN 1 END) as confirmed_orders,
                COUNT(CASE WHEN s.status = 'cancelled' THEN 1 END) as cancelled_orders
            FROM sales s
            {date_filter}
        """, tuple(params))

        stats = cursor.fetchone()

        # Формируем фильтр для второго запроса
        top_products_filter = f"WHERE s.status = 'confirmed' {'AND' if date_filter else ''} {date_filter.replace('WHERE', '')}"

        # Топ товаров
        cursor = self.execute_query(f"""
            SELECT 
                p.name,
                p.brand,
                p.category,
                SUM(si.quantity) as total_sold,
                SUM(si.total_price) as total_revenue,
                SUM(si.profit) as total_profit
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            JOIN products p ON si.product_id = p.id
            {top_products_filter}
            GROUP BY si.product_id
            ORDER BY total_sold DESC
            LIMIT 10
        """, tuple(params))

        top_products = []
        for row in cursor.fetchall():
            top_products.append({
                'name': row[0],
                'brand': row[1],
                'category': row[2],
                'total_sold': row[3],
                'total_revenue': row[4],
                'total_profit': row[5]
            })

        # Получаем значения, избегая None
        total_orders = stats[0] or 0
        total_revenue = stats[1] or 0
        total_discounts = stats[2] or 0
        avg_order_value = stats[3] or 0
        confirmed_orders = stats[4] or 0
        cancelled_orders = stats[5] or 0

        # Пересчитываем средний чек вручную для точности
        if confirmed_orders > 0:
            avg_order_value = total_revenue / confirmed_orders
        else:
            avg_order_value = 0

        return {
            'total_orders': total_orders,
            'total_revenue': total_revenue,
            'total_discounts': total_discounts,
            'avg_order_value': avg_order_value,
            'confirmed_orders': confirmed_orders,
            'cancelled_orders': cancelled_orders,
            'top_products': top_products
        }

    def get_detailed_sales_data(self, start_date: str, end_date: str) -> list:
        """
        Получает детализированные данные по каждой проданной позиции
        из подтвержденных заказов за период.

        Args:
            start_date: Начальная дата (формат: 'YYYY-MM-DD')
            end_date: Конечная дата (формат: 'YYYY-MM-DD')

        Returns:
            Список словарей с деталями по каждой позиции.
        """
        params = [start_date, f"{end_date} 23:59:59"]

        query = """
            SELECT
                s.id as sale_id,
                s.confirmed_at,
                u.first_name || ' ' || u.last_name as user_name,
                u.phone as user_phone,
                p.name as product_name,
                p.brand as product_brand,
                p.category as product_category,
                sz.value as size_value,
                si.quantity,
                si.unit_price,
                si.total_price,
                si.purchase_price,
                si.profit
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            JOIN products p ON si.product_id = p.id
            JOIN users u ON s.user_id = u.user_id
            LEFT JOIN sizes sz ON si.size_id = sz.id
            WHERE s.status = 'confirmed' AND s.confirmed_at BETWEEN ? AND ?
            ORDER BY s.confirmed_at DESC, s.id, p.name
        """

        cursor = self.execute_query(query, tuple(params))
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_inventory_history(self, product_id: int = None) -> list:
        """
        Получает историю движения товара.
        
        Args:
            product_id: ID товара (если None, возвращает историю всех товаров)
            
        Returns:
            Список записей движения товара
        """
        if product_id:
            cursor = self.execute_query("""
                SELECT 
                    'receipt' as type,
                    ir.receipt_date as date,
                    p.name as product_name,
                    s.value as size_value,
                    ir.quantity,
                    ir.purchase_price,
                    ir.notes,
                    u.first_name as admin_name
                FROM inventory_receipts ir
                JOIN products p ON ir.product_id = p.id
                LEFT JOIN sizes s ON ir.size_id = s.id
                LEFT JOIN users u ON ir.admin_id = u.user_id
                WHERE ir.product_id = ?
                
                UNION ALL
                
                SELECT 
                    'sale' as type,
                    s.created_at as date,
                    p.name as product_name,
                    s2.value as size_value,
                    si.quantity,
                    si.unit_price as purchase_price,
                    s.admin_notes as notes,
                    u.first_name as admin_name
                FROM sale_items si
                JOIN sales s ON si.sale_id = s.id
                JOIN products p ON si.product_id = p.id
                LEFT JOIN sizes s2 ON si.size_id = s2.id
                LEFT JOIN users u ON s.user_id = u.user_id
                WHERE si.product_id = ? AND s.status = 'confirmed'
                
                ORDER BY date DESC
            """, (product_id, product_id))
        else:
            cursor = self.execute_query("""
                SELECT 
                    'receipt' as type,
                    ir.receipt_date as date,
                    p.name as product_name,
                    s.value as size_value,
                    ir.quantity,
                    ir.purchase_price,
                    ir.notes,
                    u.first_name as admin_name
                FROM inventory_receipts ir
                JOIN products p ON ir.product_id = p.id
                LEFT JOIN sizes s ON ir.size_id = s.id
                LEFT JOIN users u ON ir.admin_id = u.user_id
                
                UNION ALL
                
                SELECT 
                    'sale' as type,
                    s.created_at as date,
                    p.name as product_name,
                    s2.value as size_value,
                    si.quantity,
                    si.unit_price as purchase_price,
                    s.admin_notes as notes,
                    u.first_name as admin_name
                FROM sale_items si
                JOIN sales s ON si.sale_id = s.id
                JOIN products p ON si.product_id = p.id
                LEFT JOIN sizes s2 ON si.size_id = s2.id
                LEFT JOIN users u ON s.user_id = u.user_id
                WHERE s.status = 'confirmed'
                
                ORDER BY date DESC
                LIMIT 100
            """)
        
        history = []
        for row in cursor.fetchall():
            history.append({
                'type': row[0],
                'date': row[1],
                'product_name': row[2],
                'size_value': row[3],
                'quantity': row[4],
                'price': row[5],
                'notes': row[6],
                'admin_name': row[7]
            })
        
        return history

    def get_total_inventory_stats(self) -> dict:
        """
        Получает общую статистику по товарам: общее количество товаров, их общую стоимость и количество единиц.
        """
        query = """
            SELECT
                COUNT(DISTINCT CASE WHEN p.is_active = 1 THEN p.id END) as active_products,
                COUNT(DISTINCT CASE WHEN p.is_active = 0 THEN p.id END) as inactive_products,
                SUM(CASE WHEN p.is_active = 1 THEN pv.quantity ELSE 0 END) as total_quantity,
                SUM(CASE WHEN p.is_active = 1 THEN pv.quantity * (p.sale_price * (1 - p.discount / 100.0)) ELSE 0 END) as total_value
            FROM products p
            LEFT JOIN product_variants pv ON p.id = pv.product_id
        """
        cursor = self.execute_query(query)
        result = cursor.fetchone()
        return {
            'active_products': result[0] or 0,
            'inactive_products': result[1] or 0,
            'total_quantity': result[2] or 0,
            'total_value': result[3] or 0
        }

    def get_inventory_by_category(self) -> list:
        """
        Получает статистику по товарам в разрезе категорий.
        """
        query = """
            SELECT
                p.category,
                COUNT(DISTINCT p.id) as product_count,
                SUM(pv.quantity) as total_quantity,
                SUM(pv.quantity * (p.sale_price * (1 - p.discount / 100.0))) as total_value
            FROM products p
            LEFT JOIN product_variants pv ON p.id = pv.product_id
            WHERE p.is_active = 1 AND p.category IS NOT NULL
            GROUP BY p.category
            ORDER BY product_count DESC
        """
        cursor = self.execute_query(query)
        return [{'category': row[0], 'product_count': row[1], 'total_quantity': row[2] or 0, 'total_value': row[3] or 0} for row in cursor.fetchall()]

    def get_inventory_by_subcategory(self) -> list:
        """
        Получает статистику по товарам в разрезе подкатегорий.
        """
        query = """
            SELECT
                p.category,
                p.subcategory,
                COUNT(DISTINCT p.id) as product_count,
                SUM(pv.quantity) as total_quantity,
                SUM(pv.quantity * (p.sale_price * (1 - p.discount / 100.0))) as total_value
            FROM products p
            LEFT JOIN product_variants pv ON p.id = pv.product_id
            WHERE p.is_active = 1 AND p.subcategory IS NOT NULL
            GROUP BY p.category, p.subcategory
            ORDER BY p.category, product_count DESC
        """
        cursor = self.execute_query(query)
        return [{'category': row[0], 'subcategory': row[1], 'product_count': row[2], 'total_quantity': row[3] or 0, 'total_value': row[4] or 0} for row in cursor.fetchall()]

    def get_inventory_by_brand(self) -> list:
        """
        Получает статистику по товарам в разрезе брендов.
        """
        query = """
            SELECT
                p.brand,
                COUNT(DISTINCT p.id) as product_count,
                SUM(pv.quantity) as total_quantity,
                SUM(pv.quantity * (p.sale_price * (1 - p.discount / 100.0))) as total_value
            FROM products p
            LEFT JOIN product_variants pv ON p.id = pv.product_id
            WHERE p.is_active = 1 AND p.brand IS NOT NULL
            GROUP BY p.brand
            ORDER BY product_count DESC
        """
        cursor = self.execute_query(query)
        return [{'brand': row[0], 'product_count': row[1], 'total_quantity': row[2] or 0, 'total_value': row[3] or 0} for row in cursor.fetchall()]

    def get_inventory_by_size(self, size_type: Optional[str] = None) -> list:
        """
        Получает статистику по остаткам размеров.
        Можно фильтровать по типу размера ('number', 'letter', 'jeans').
        """
        query = """
            SELECT
                s.value,
                s.type,
                SUM(pv.quantity) as total_quantity,
                SUM(pv.quantity * (p.sale_price * (1 - p.discount / 100.0))) as total_value
            FROM product_variants pv
            JOIN sizes s ON pv.size_id = s.id
            JOIN products p ON pv.product_id = p.id
            WHERE p.is_active = 1 AND pv.quantity > 0
        """
        params = []
        if size_type:
            query += " AND s.type = ?"
            params.append(size_type)

        query += " GROUP BY s.value, s.type ORDER BY s.type, s.value"

        cursor = self.execute_query(query, tuple(params))
        return [{'size': row[0], 'type': row[1], 'total_quantity': row[2] or 0, 'total_value': row[3] or 0} for row in cursor.fetchall()]

    def get_most_viewed_products(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Получает список самых просматриваемых товаров.
        
        Args:
            limit: Максимальное количество товаров
            
        Returns:
            Список словарей с информацией о товарах и их просмотрах
        """
        cursor = self.execute_query(
            """
            SELECT 
                p.id, p.name, p.brand, p.category, p.sale_price,
                COUNT(pv.id) as view_count,
                COUNT(DISTINCT pv.user_id) as unique_viewers
            FROM products p
            LEFT JOIN product_views pv ON p.id = pv.product_id
            WHERE p.is_active = 1
            GROUP BY p.id
            ORDER BY view_count DESC, unique_viewers DESC
            LIMIT ?
            """,
            (limit,)
        )
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_recent_views(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Получает недавние просмотры за указанное количество часов.
        
        Args:
            hours: Количество часов для поиска
            
        Returns:
            Список словарей с информацией о недавних просмотрах
        """
        cursor = self.execute_query(
            """
            SELECT 
                pv.id, pv.user_id, pv.product_id, pv.view_type, pv.created_at,
                p.name as product_name, p.brand, p.category,
                u.first_name, u.last_name, u.user_name
            FROM product_views pv
            JOIN products p ON pv.product_id = p.id
            JOIN users u ON pv.user_id = u.user_id
            WHERE pv.created_at >= datetime('now', '-{} hours')
            ORDER BY pv.created_at DESC
            """.format(hours)
        )
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    # =====================================================================================
    # БЛОК 19: ОТЛАДОЧНЫЕ МЕТОДЫ
    # -------------------------------------------------------------------------------------
    # Вспомогательные методы, используемые в процессе разработки и тестирования.
    # - Получение и очистка временных данных (ID сообщений).
    # - Вывод сводной информации о состоянии базы данных.
    # - Тестирование запросов на фильтрацию.
    # =====================================================================================

    def get_and_clear_register_msg_id(self, user_id: int) -> Optional[int]:
        """Получает и очищает сохранённый ID сообщения о регистрации"""
        msg_id = self.get_register_msg_id(user_id)
        if msg_id:
            self.clear_register_msg_id(user_id)
        return msg_id

    def debug_database_content(self) -> dict:
        """
        Возвращает статистику по товарам, категориям, брендам, сезонам и примеры товаров.
        """
        result = {
            'total_active_products': 0,
            'products_with_media': 0,
            'available_categories': [],
            'available_brands': [],
            'available_seasons': [],
            'category_counts': {},
            'sample_products': []
        }
        # Всего активных товаров
        cursor = self.execute_query("SELECT COUNT(*) FROM products WHERE is_active = 1")
        result['total_active_products'] = cursor.fetchone()[0]
        # Товаров с медиа
        cursor = self.execute_query("SELECT COUNT(DISTINCT product_id) FROM product_media WHERE is_main = 1")
        result['products_with_media'] = cursor.fetchone()[0]
        # Категории
        cursor = self.execute_query("SELECT DISTINCT category FROM products WHERE is_active = 1")
        result['available_categories'] = [row[0] for row in cursor.fetchall() if row[0]]
        # Бренды
        cursor = self.execute_query("SELECT DISTINCT brand FROM products WHERE is_active = 1")
        result['available_brands'] = [row[0] for row in cursor.fetchall() if row[0]]
        # Сезоны
        cursor = self.execute_query("SELECT DISTINCT season FROM products WHERE is_active = 1")
        result['available_seasons'] = [row[0] for row in cursor.fetchall() if row[0]]
        # Количество товаров по категориям
        cursor = self.execute_query("SELECT category, COUNT(*) FROM products WHERE is_active = 1 GROUP BY category")
        result['category_counts'] = {row[0]: row[1] for row in cursor.fetchall()}
        # Примеры товаров
        cursor = self.execute_query("SELECT id, name, category, brand FROM products WHERE is_active = 1 LIMIT 5")
        result['sample_products'] = [
            {'id': row[0], 'name': row[1], 'category': row[2], 'brand': row[3]} for row in cursor.fetchall()
        ]
        return result

    def test_filter_query(self, **filters) -> dict:
        """
        Тестирует фильтрацию товаров по переданным фильтрам.
        Возвращает количество найденных товаров и success/error.
        """
        try:
            media = self.get_filtered_product_media(**filters)
            return {'results': {'success': True, 'count': len(media)}}
        except Exception as e:
            return {'results': {'success': False, 'error': str(e)}}

    def debug_subcategories(self) -> dict:
        """Отладочная функция для проверки подкатегорий в БД"""
        cursor = self.execute_query(
            "SELECT id, name, category, subcategory FROM products WHERE is_active = 1"
        )
        products = cursor.fetchall()
        
        result = {
            'total_products': len(products),
            'by_category': {},
            'sample_products': []
        }
        
        for product in products:
            product_id, name, category, subcategory = product
            if category not in result['by_category']:
                result['by_category'][category] = []
            result['by_category'][category].append({
                'id': product_id,
                'name': name,
                'subcategory': subcategory
            })
            
            if len(result['sample_products']) < 5:
                result['sample_products'].append({
                    'id': product_id,
                    'name': name,
                    'category': category,
                    'subcategory': subcategory
                })
        
        return result


# Инициализация глобального экземпляра базы данных
data_base = BotDatabase(f'{name_bot}')