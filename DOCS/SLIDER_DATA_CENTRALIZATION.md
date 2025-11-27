# Централизация данных слайдеров в FSM

## Обзор

Реализована централизованная система управления данными слайдеров через FSM (Finite State Machine) для всех типов слайдеров: каталог, избранное, "для меня".

## Проблема

Ранее данные слайдеров хранились в разных местах и обрабатывались по-разному:
- Некоторые данные в FSM, некоторые в базе данных
- Разные ключи для одинаковых данных
- Отсутствие единообразия в управлении состоянием
- Сложность синхронизации данных между компонентами

## Решение

Создан `SliderDataManager` - централизованный менеджер данных слайдеров, который:

1. **Единая точка доступа** - все данные слайдера получаются и устанавливаются через один интерфейс
2. **Приоритет данных** - сначала проверяется FSM, если данных нет - берется из базы
3. **Единообразие** - все типы слайдеров используют одинаковую структуру данных
4. **Fallback механизм** - автоматическое восстановление данных из базы при необходимости

## Архитектура

### SliderDataManager

```python
class SliderDataManager:
    # Ключи данных слайдера в FSM
    SLIDER_KEYS = {
        # Основные данные
        'media_list': 'media_list',
        'product_ids': 'product_ids', 
        'index': 'index',
        'msg_id': 'msg_id',
        'playing': 'playing',
        'expanded': 'expanded',
        'speed': 'speed',
        'cycle_count': 'cycle_count',
        
        # Источник и контекст
        'slider_source': 'slider_source',
        'user_id': 'user_id',
        
        # Дополнительные данные
        'cart_items': 'cart_items',
        'return_to_favorites': 'return_to_favorites',
        'favorites_source': 'favorites_source',
        
        # Резервные ключи (для обратной совместимости)
        'slider_media_list': 'slider_media_list',
        'slider_product_ids': 'slider_product_ids',
        'photo_list': 'photo_list',
        'cycle_length': 'cycle_length',
        'first_photo_shown': 'first_photo_shown'
    }
```

### Основные методы

#### Получение данных
- `get_slider_data(state)` - все данные слайдера
- `get_media_list(state)` - список медиа (FSM → база)
- `get_product_ids(state)` - список ID товаров
- `get_current_product_id(state)` - ID текущего товара
- `get_cart_items(state)` - корзина (FSM → база)
- `get_slider_settings(state)` - настройки слайдера
- `get_user_id(state)` - ID пользователя
- `get_slider_source(state)` - источник слайдера

#### Установка данных
- `set_slider_data(state, **kwargs)` - установка любых данных
- `set_slider_settings(state, **kwargs)` - установка настроек
- `set_user_id(state, user_id)` - установка ID пользователя
- `update_cart_items(state)` - обновление корзины из базы

#### Управление состоянием
- `is_slider_active(state)` - проверка активности слайдера
- `clear_slider_data(state)` - очистка всех данных

## Интеграция с компонентами

### SliderManager

Обновлен для использования централизованного менеджера:

```python
# Было
data = await self.state.get_data()
media_list = data.get("media_list", [])
product_ids = data.get("product_ids", [])

# Стало
media_list = await SliderDataManager.get_media_list(self.state)
product_ids = await SliderDataManager.get_product_ids(self.state)
```

### Роутеры

Все роутеры обновлены для использования централизованного менеджера:

- `slider_router.py` - управление слайдером
- `profile_router.py` - слайдер избранного
- `catalog_router.py` - каталог товаров
- `navigation_router.py` - навигация
- `start_router.py` - старт бота

## Преимущества

### 1. Единообразие
Все слайдеры теперь используют одинаковую структуру данных и методы доступа.

### 2. Надежность
Fallback механизм обеспечивает восстановление данных из базы при их отсутствии в FSM.

### 3. Простота поддержки
Один интерфейс для всех операций с данными слайдера.

### 4. Производительность
Данные кэшируются в FSM и не загружаются повторно из базы.

### 5. Обратная совместимость
Поддержка старых ключей данных для плавного перехода.

## Примеры использования

### Запуск слайдера
```python
# Устанавливаем данные через централизованный менеджер
await SliderDataManager.set_slider_data(
    state,
    media_list=media_list,
    product_ids=product_ids,
    slider_source="favorites"
)

# Запускаем слайдер
slider_manager = SliderManager(manager, state)
await slider_manager.start_slider(media_list, product_ids, source="favorites")
```

### Обновление слайдера
```python
# Получаем данные через централизованный менеджер
media_list = await SliderDataManager.get_media_list(state)
settings = await SliderDataManager.get_slider_settings(state)

# Обновляем настройки
await SliderDataManager.set_slider_settings(
    state,
    index=new_index,
    playing=False,
    expanded=True
)
```

### Обработка корзины
```python
# Обновляем корзину в FSM
await SliderDataManager.update_cart_items(state)

# Получаем актуальную корзину
cart_items = await SliderDataManager.get_cart_items(state)
```

## Миграция

### Автоматическая миграция
Система автоматически мигрирует старые данные в новую структуру при первом обращении.

### Резервные ключи
Поддерживаются старые ключи для обеспечения обратной совместимости:
- `slider_media_list` → `media_list`
- `slider_product_ids` → `product_ids`
- `photo_list` → `media_list`

## Мониторинг

### Логирование
Все операции с данными логируются для отладки:
```
Slider data updated in FSM: ['media_list', 'product_ids', 'slider_source']
Got media_list from FSM: 15 items
Got media_list from database (favorites): 8 items
```

### Отладка
Для отладки можно использовать методы:
```python
# Получить все данные слайдера
slider_data = await SliderDataManager.get_slider_data(state)
print(slider_data)

# Проверить активность слайдера
is_active = await SliderDataManager.is_slider_active(state)
print(f"Slider active: {is_active}")
```

## Заключение

Централизация данных слайдеров в FSM обеспечивает:
- Единообразное управление данными для всех типов слайдеров
- Надежное восстановление данных из базы при необходимости
- Упрощение кода и повышение надежности
- Легкость добавления новых типов слайдеров

Система готова к использованию и обеспечивает плавную миграцию существующего кода. 