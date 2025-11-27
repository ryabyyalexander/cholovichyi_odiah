import sqlite3
import json
from utils import logger

# Вспомогательная функция для выполнения запросов внутри этого модуля
def _execute_query(cursor: sqlite3.Cursor, query: str, params: tuple = ()):
    cursor.execute(query, params)
    return cursor

def setup_database(db_name: str):
    """Инициализирует структуру базы данных: создает таблицы и запускает миграции."""
    db_path = f"{db_name}.db"
    with sqlite3.connect(db_path) as db:
        cursor = db.cursor()
        _create_tables(cursor)

        # Предзаполняем таблицы, если они пусты
        if not _execute_query(cursor, "SELECT 1 FROM sizes LIMIT 1").fetchone():
            _initialize_sizes(cursor)
            _create_indexes(cursor)

        if not _execute_query(cursor, "SELECT 1 FROM subscriptions LIMIT 1").fetchone():
            _initialize_subscriptions(cursor)

        db.commit() # Сохраняем изменения после создания таблиц и инициализации

        # Запускаем миграции. Они используют прямое подключение для сложных операций.
        _migrate_active_msg_id(db_path)
        _migrate_user_cascade_tables(db_path)
        _migrate_rename_weather_to_loyalty_tiers(db_path)
        _migrate_sales_status_add_reserved(db_path)
        _migrate_add_order_id_to_reservations(db_path)

    logger.info("Database schema initialized and migrations checked.")


def _create_tables(cursor: sqlite3.Cursor):
    """Создает все таблицы, если они не существуют."""
    # Таблицы пользователей
    _execute_query(cursor, """
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT, user_name TEXT,
        phone TEXT, size TEXT, is_admin BOOLEAN DEFAULT 0, is_active BOOLEAN DEFAULT 0,
        restart_count INTEGER DEFAULT 0, user_blocked BOOLEAN DEFAULT 0,
        registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, active_msg_id TEXT,
        slider_speed TEXT, filters TEXT DEFAULT NULL, loyalty_points INTEGER DEFAULT 0,
        referrer_id INTEGER, level TEXT DEFAULT NULL, total_spent INTEGER DEFAULT 0
    );
    """)
    # Таблицы товаров
    _execute_query(cursor, """
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT, vendor_code TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
        short_description TEXT, purchase_price REAL NOT NULL CHECK(purchase_price >= 0),
        sale_price REAL NOT NULL CHECK(sale_price >= 0), discount INTEGER DEFAULT 0 CHECK(discount BETWEEN 0 AND 100),
        season TEXT NOT NULL CHECK(season IN ('весна-літо', 'осінь-зима', 'season')),
        loyalty_tiers TEXT, category TEXT, subcategory TEXT, brand TEXT, country TEXT,
        is_active BOOLEAN DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    # Таблицы размеров
    _execute_query(cursor, """
    CREATE TABLE IF NOT EXISTS sizes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT NOT NULL CHECK(type IN ('number', 'letter', 'jeans')),
        value TEXT NOT NULL UNIQUE, equivalent_letter TEXT
    );
    """)
    # Таблицы вариантов товаров
    _execute_query(cursor, """
    CREATE TABLE IF NOT EXISTS product_variants (
        product_id INTEGER NOT NULL, size_id INTEGER NOT NULL, quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0),
        PRIMARY KEY (product_id, size_id),
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
        FOREIGN KEY (size_id) REFERENCES sizes(id)
    );
    """)
    # Таблицы медиа
    _execute_query(cursor, """
    CREATE TABLE IF NOT EXISTS product_media (
        id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, telegram_file_id TEXT NOT NULL,
        media_type TEXT NOT NULL CHECK(media_type IN ('photo', 'video', 'document')),
        is_main BOOLEAN DEFAULT 0, caption TEXT DEFAULT 0,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
    );
    """)
    # Таблица избранного
    _execute_query(cursor, """
    CREATE TABLE IF NOT EXISTS favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id, product_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
    );
    """)
    # Таблица истории лояльности
    _execute_query(cursor, """
    CREATE TABLE IF NOT EXISTS loyalty_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, event TEXT NOT NULL,
        points INTEGER NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    );
    """)
    # Таблица просмотров товаров
    _execute_query(cursor, """
    CREATE TABLE IF NOT EXISTS product_views (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
        media_id INTEGER, view_type TEXT DEFAULT 'slider' CHECK(view_type IN ('slider', 'single', 'gallery')),
        view_duration INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
        FOREIGN KEY (media_id) REFERENCES product_media(id) ON DELETE CASCADE
    );
    """)
    # Таблица корзины
    _execute_query(cursor, """
    CREATE TABLE IF NOT EXISTS cart (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
        size_id INTEGER, quantity INTEGER NOT NULL DEFAULT 1 CHECK(quantity > 0),
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
        FOREIGN KEY (size_id) REFERENCES sizes(id)
    );
    """)
    # Таблица поступлений товаров
    _execute_query(cursor, """
    CREATE TABLE IF NOT EXISTS inventory_receipts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, size_id INTEGER,
        quantity INTEGER NOT NULL CHECK(quantity > 0), purchase_price REAL NOT NULL CHECK(purchase_price >= 0),
        receipt_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, notes TEXT, admin_id INTEGER,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
        FOREIGN KEY (size_id) REFERENCES sizes(id), FOREIGN KEY (admin_id) REFERENCES users(user_id)
    );
    """)
    # Таблица продаж
    _execute_query(cursor, """
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        total_amount REAL NOT NULL CHECK(total_amount >= 0),
        discount_amount REAL DEFAULT 0 CHECK(discount_amount >= 0),
        final_amount REAL NOT NULL CHECK(final_amount >= 0),
        status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'confirmed', 'cancelled', 'completed', 'reserved')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, confirmed_at TIMESTAMP, completed_at TIMESTAMP,
        admin_notes TEXT, FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    );
    """)
    # Таблица позиций продаж
    _execute_query(cursor, """
    CREATE TABLE IF NOT EXISTS sale_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
        size_id INTEGER, quantity INTEGER NOT NULL CHECK(quantity > 0),
        unit_price REAL NOT NULL CHECK(unit_price >= 0), total_price REAL NOT NULL CHECK(total_price >= 0),
        purchase_price REAL NOT NULL CHECK(purchase_price >= 0),
        profit REAL GENERATED ALWAYS AS (total_price - (purchase_price * quantity)) STORED,
        FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
        FOREIGN KEY (size_id) REFERENCES sizes(id)
    );
    """)
    # Таблица истории активации товаров
    _execute_query(cursor, """
    CREATE TABLE IF NOT EXISTS product_activation_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, admin_id INTEGER NOT NULL,
        action TEXT NOT NULL CHECK(action IN ('activated', 'deactivated')), reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
        FOREIGN KEY (admin_id) REFERENCES users(user_id)
    );
    """)
    # Таблица архива сообщений
    _execute_query(cursor, """
    CREATE TABLE IF NOT EXISTS message_archive (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    # Таблица тем подписок
    _execute_query(cursor, """
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, topic_key TEXT NOT NULL UNIQUE, description TEXT NOT NULL
    );
    """)
    # Таблица подписок пользователей
    _execute_query(cursor, """
    CREATE TABLE IF NOT EXISTS user_subscriptions (
        user_id INTEGER NOT NULL, subscription_id INTEGER NOT NULL, filters TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (user_id, subscription_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (subscription_id) REFERENCES subscriptions(id) ON DELETE CASCADE
    );
    """)
    # Таблица получателей архивных сообщений
    _execute_query(cursor, """
    CREATE TABLE IF NOT EXISTS archived_message_recipients (
        archive_id INTEGER NOT NULL, user_id INTEGER NOT NULL, PRIMARY KEY (archive_id, user_id),
        FOREIGN KEY (archive_id) REFERENCES message_archive(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    );
    """)
    # Таблица резервов
    _execute_query(cursor, """
    CREATE TABLE IF NOT EXISTS reservations (
        id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER, user_id INTEGER NOT NULL,
        admin_id INTEGER NOT NULL, product_id INTEGER NOT NULL, size_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1,
        status TEXT NOT NULL CHECK(status IN ('active', 'temporary', 'completed', 'cancelled')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, expires_at TIMESTAMP, final_price REAL,
        FOREIGN KEY (order_id) REFERENCES sales(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (admin_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
        FOREIGN KEY (size_id) REFERENCES sizes(id) ON DELETE CASCADE
    );
    """)
    # Таблица листа ожидания
    _execute_query(cursor, """
    CREATE TABLE IF NOT EXISTS waiting_list (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
        size_id INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'notified', 'expired')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id, product_id, size_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
        FOREIGN KEY (size_id) REFERENCES sizes(id) ON DELETE CASCADE
    );
    """)

def _create_indexes(cursor: sqlite3.Cursor):
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
            _execute_query(cursor, index_query)
        except sqlite3.Error as e:
            logger.error(f"Error creating index: {e}")

def _initialize_sizes(cursor: sqlite3.Cursor):
    """Инициализирует таблицу размеров при первом запуске"""
    sizes_data = [
        ('number', '46', 'xs'), ('number', '48', 's'), ('number', '50', 'm'), ('number', '52', 'l'),
        ('number', '54', 'xl'), ('number', '56', '2xl'), ('number', '58', '3xl'), ('number', '60', '4xl'),
        ('jeans', '31', 'xs'), ('jeans', '32', 's'), ('jeans', '33', 'm'), ('jeans', '34', 'm'),
        ('jeans', '35', 'l'), ('jeans', '36', 'l'), ('jeans', '38', 'xl'), ('jeans', '40', '2xl'),
        ('jeans', '42', '3xl'),
        ('letter', 'xs', None), ('letter', 's', None), ('letter', 'm', None), ('letter', 'l', None),
        ('letter', 'xl', None), ('letter', '2xl', None), ('letter', '3xl', None), ('letter', '4xl', None),
        ('letter', 'one size', None)
    ]
    cursor.executemany("INSERT INTO sizes (type, value, equivalent_letter) VALUES (?, ?, ?)", sizes_data)

def _initialize_subscriptions(cursor: sqlite3.Cursor):
    """Инициализирует темы подписок."""
    topics = [
        ('new_arrivals', 'Новые поступления'),
        ('sales_and_discounts', 'Акции и скидки'),
        ('brand_news', 'Новости бренда'),
        ('size_discounts', 'Скидка на мой размер')
    ]
    cursor.executemany("INSERT INTO subscriptions (topic_key, description) VALUES (?, ?)", topics)
    logger.info("Таблица подписок инициализирована.")

def _migrate_add_order_id_to_reservations(db_path: str):
    try:
        with sqlite3.connect(db_path) as db:
            cursor = db.cursor()
            cursor.execute("PRAGMA table_info(reservations);")
            columns = [info[1] for info in cursor.fetchall()]
            if 'order_id' not in columns:
                cursor.execute("ALTER TABLE reservations ADD COLUMN order_id INTEGER REFERENCES sales(id) ON DELETE CASCADE;")
                logger.info("Миграция базы данных: в таблицу reservations добавлен столбец order_id.")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при миграции таблицы reservations: {e}")

def _migrate_sales_status_add_reserved(db_path: str):
    try:
        with sqlite3.connect(db_path) as db:
            cursor = db.cursor()
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='sales';")
            schema_result = cursor.fetchone()
            if not schema_result or "'reserved'" in schema_result[0]:
                return

            logger.info("Начинаем миграцию таблицы 'sales' для добавления статуса 'reserved'.")
            cursor.execute("ALTER TABLE sales RENAME TO sales_old;")
            _create_tables(cursor) # Re-create sales table with new schema
            cursor.execute("""
            INSERT INTO sales (id, user_id, total_amount, discount_amount, final_amount, status, created_at, confirmed_at, completed_at, admin_notes)
            SELECT id, user_id, total_amount, discount_amount, final_amount, status, created_at, confirmed_at, completed_at, admin_notes FROM sales_old;
            """)
            cursor.execute("DROP TABLE sales_old;")
            db.commit()
            logger.info("Миграция таблицы 'sales' успешно завершена.")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при миграции таблицы 'sales': {e}")
        # Simple rollback attempt
        try:
            with sqlite3.connect(db_path) as db:
                db.execute("DROP TABLE IF EXISTS sales;")
                db.execute("ALTER TABLE sales_old RENAME TO sales;")
        except sqlite3.Error as rollback_e:
            logger.error(f"Критическая ошибка: не удалось откатить миграцию 'sales'. {rollback_e}")
        raise

def _migrate_rename_weather_to_loyalty_tiers(db_path: str):
    try:
        with sqlite3.connect(db_path) as db:
            cursor = db.cursor()
            cursor.execute("PRAGMA table_info(products);")
            columns = [info[1] for info in cursor.fetchall()]
            if 'weather' in columns and 'loyalty_tiers' not in columns:
                cursor.execute("ALTER TABLE products RENAME COLUMN weather TO loyalty_tiers;")
                logger.info("Миграция базы данных: столбец 'weather' переименован в 'loyalty_tiers'.")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при миграции столбца 'weather' на 'loyalty_tiers': {e}")

def _migrate_active_msg_id(db_path: str):
    try:
        with sqlite3.connect(db_path) as db:
            cursor = db.cursor()
            cursor.execute("SELECT user_id, active_msg_id FROM users WHERE active_msg_id IS NOT NULL AND active_msg_id != ''")
            users_to_migrate = cursor.fetchall()
            if not users_to_migrate: return

            for user_id, old_active_msg_id in users_to_migrate:
                try:
                    if isinstance(old_active_msg_id, str):
                        json.loads(old_active_msg_id)
                        continue
                    msg_id = int(old_active_msg_id)
                    new_msg_ids_json = json.dumps({"active": msg_id})
                    cursor.execute("UPDATE users SET active_msg_id = ? WHERE user_id = ?", (new_msg_ids_json, user_id))
                except (json.JSONDecodeError, ValueError, TypeError):
                    continue
            db.commit()
    except sqlite3.Error as e:
        logger.error(f"Ошибка при миграции active_msg_id: {e}")

def _migrate_user_cascade_tables(db_path: str):
    with sqlite3.connect(db_path) as db:
        cursor = db.cursor()
        # loyalty_history
        cursor.execute("PRAGMA foreign_key_list(loyalty_history);")
        loyalty_fk = cursor.fetchall()
        if not any('users' in str(row) and 'CASCADE' in str(row) for row in loyalty_fk):
            cursor.execute("ALTER TABLE loyalty_history RENAME TO loyalty_history_old;")
            _create_tables(cursor) # Re-create table
            cursor.execute("INSERT INTO loyalty_history SELECT * FROM loyalty_history_old;")
            cursor.execute("DROP TABLE loyalty_history_old;")
        # product_views
        cursor.execute("PRAGMA foreign_key_list(product_views);")
        views_fk = cursor.fetchall()
        if not any(row[2] == 'users' and row[6] == 'CASCADE' for row in views_fk):
            cursor.execute("ALTER TABLE product_views RENAME TO product_views_old;")
            _create_tables(cursor) # Re-create table
            cursor.execute("INSERT INTO product_views SELECT * FROM product_views_old;")
            cursor.execute("DROP TABLE product_views_old;")
        db.commit()