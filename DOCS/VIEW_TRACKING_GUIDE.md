# Руководство по системе отслеживания просмотров товаров

## Обзор

Система отслеживания просмотров позволяет собирать и анализировать данные о том, как пользователи просматривают товары в боте. Это помогает понять поведение пользователей и оптимизировать каталог товаров.

## Структура базы данных

### Таблица `product_views`

```sql
CREATE TABLE product_views (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    media_id INTEGER,
    view_type TEXT DEFAULT 'slider' CHECK(view_type IN ('slider', 'single', 'gallery')),
    view_duration INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (media_id) REFERENCES product_media(id) ON DELETE CASCADE
);
```

**Поля:**
- `user_id` - ID пользователя
- `product_id` - ID товара
- `media_id` - ID медиа (опционально)
- `view_type` - Тип просмотра: 'slider', 'single', 'gallery'
- `view_duration` - Длительность просмотра в секундах
- `created_at` - Время создания записи

## Использование

### 1. Быстрая запись просмотра

```python
from utils.view_tracker import view_tracker

# Быстрая запись просмотра без отслеживания времени
view_tracker.quick_view(
    user_id=12345,
    product_id=1,
    view_type='slider'
)
```

### 2. Отслеживание сессии просмотра

```python
# Начало сессии просмотра
session_key = view_tracker.start_view_session(
    user_id=12345,
    product_id=1,
    view_type='single'
)

# ... пользователь просматривает товар ...

# Завершение сессии (автоматически записывает в БД)
duration = view_tracker.end_view_session(session_key)
print(f"Длительность просмотра: {duration} секунд")
```

### 3. Получение статистики

#### Статистика пользователя
```python
user_stats = view_tracker.get_user_stats(user_id=12345)
print(f"Всего просмотров: {user_stats['total_views']}")
print(f"Уникальных товаров: {user_stats['unique_products']}")
print(f"Средняя длительность: {user_stats['avg_duration']:.1f} сек")
print(f"Просмотры в слайдере: {user_stats['slider_views']}")
print(f"Одиночные просмотры: {user_stats['single_views']}")
```

#### Статистика товара
```python
product_stats = view_tracker.get_product_stats(product_id=1)
print(f"Всего просмотров: {product_stats['total_views']}")
print(f"Уникальных зрителей: {product_stats['unique_viewers']}")
print(f"Средняя длительность: {product_stats['avg_duration']:.1f} сек")
```

### 4. Получение истории и аналитики

#### История просмотров пользователя
```python
view_history = view_tracker.get_user_view_history(user_id=12345, limit=20)
for view in view_history:
    print(f"Товар {view['product_id']} - {view['view_type']} - {view['created_at']}")
```

#### Популярные товары
```python
popular_products = view_tracker.get_popular_products(limit=10)
for product in popular_products:
    print(f"ID {product['id']} - {product['name']} - {product['view_count']} просмотров")
```

#### Недавняя активность
```python
recent_activity = view_tracker.get_recent_activity(hours=24)
print(f"Активность за 24 часа: {len(recent_activity)} записей")
```

## Интеграция с существующим кодом

### В SliderManager

Система уже интегрирована в `SliderManager`. При запуске слайдера и смене слайдов автоматически записываются просмотры:

```python
# В методе start_slider
if user_id and first_product_id:
    data_base.add_product_view(
        user_id=user_id,
        product_id=first_product_id,
        view_type='slider',
        view_duration=0
    )

# В методе update_photo
if user_id and product_id:
    data_base.add_product_view(
        user_id=user_id,
        product_id=product_id,
        view_type='slider',
        view_duration=0
    )
```

### Добавление в другие части бота

Для добавления отслеживания в другие части бота:

```python
from utils.view_tracker import view_tracker

# При показе товара
view_tracker.quick_view(
    user_id=message.from_user.id,
    product_id=product_id,
    view_type='single'  # или 'gallery'
)
```

## Прямое использование базы данных

### Добавление просмотра
```python
from data_base.models import data_base

data_base.add_product_view(
    user_id=12345,
    product_id=1,
    media_id=5,  # опционально
    view_type='slider',
    view_duration=10
)
```

### Получение данных
```python
# Статистика пользователя
stats = data_base.get_user_view_stats(user_id=12345)

# История просмотров
history = data_base.get_user_product_views(user_id=12345, limit=50)

# Статистика товара
product_stats = data_base.get_product_view_stats(product_id=1)

# Популярные товары
popular = data_base.get_most_viewed_products(limit=10)

# Недавние просмотры
recent = data_base.get_recent_views(hours=24)
```

## Очистка данных

Для удаления старых записей о просмотрах:

```python
# Удалить записи старше 90 дней
deleted_count = view_tracker.cleanup_old_data(days=90)
print(f"Удалено {deleted_count} старых записей")

# Или напрямую через базу данных
deleted_count = data_base.delete_old_views(days=90)
```

## Тестирование

Запустите тестовый файл для проверки функциональности:

```bash
python test_view_tracking.py
```

## Возможности аналитики

Собранные данные позволяют:

1. **Анализировать популярность товаров** - какие товары просматриваются чаще
2. **Изучать поведение пользователей** - как долго они смотрят товары
3. **Оптимизировать каталог** - убирать непопулярные товары, продвигать популярные
4. **Персонализировать рекомендации** - показывать товары на основе истории просмотров
5. **Отслеживать активность** - мониторить активность пользователей в реальном времени

## Производительность

- Индексы оптимизированы для быстрых запросов
- Старые данные автоматически очищаются
- Минимальное влияние на производительность бота
- Асинхронная запись данных

## Безопасность

- Данные привязаны к пользователям
- Нет доступа к личной информации
- Только анонимная статистика просмотров
- Соответствие GDPR (можно удалить данные пользователя) 