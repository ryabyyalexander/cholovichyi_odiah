# Анализ типов слайдеров в проекте

## Обзор

В проекте реализована универсальная система слайдеров, которая поддерживает различные типы источников данных и контекстов использования. Все слайдеры используют единый `SliderManager` с параметром `source` для определения поведения.

## Архитектура слайдеров

### Основные компоненты

1. **`SliderManager`** - центральный класс управления слайдерами
2. **`SliderRouter`** - обработчики пользовательских действий
3. **`get_slider_keyboard()`** - создание клавиатур для разных типов слайдеров
4. **FSM (Finite State Machine)** - управление состоянием слайдеров

### Параметр `source`

Ключевой параметр, определяющий тип слайдера:
- `"main"` - главный каталог (72 продукта)
- `"favorites"` - избранное пользователя
- `"filters"` - отфильтрованные товары
- `"cart"` - корзина пользователя
- `"sizes"` - товары по размерам пользователя

## Типы слайдеров

### 1. **Главный слайдер** (`source="main"`)

**Описание**: Основной каталог товаров, отображающий все активные товары (72 продукта)

**Запуск**:
```python
# Из главного меню через "Каталог"
await slider_manager.start_slider(
    media_list=media, 
    product_ids=ids, 
    source="main", 
    user_id=user_id
)
```

**Особенности**:
- Отображает все активные товары без фильтрации
- Автопроигрывание включено по умолчанию
- Базовый функционал без специальных кнопок
- Кнопка возврата ведет в главное меню

**Использование**:
- `routers/catalog_router.py` - запуск из главного меню
- `routers/navigation_router.py` - обработка навигации
- `routers/product_view_router.py` - просмотр товаров

### 2. **Слайдер избранного** (`source="favorites"`)

**Описание**: Отображает товары из избранного пользователя

**Запуск**:
```python
# Из профиля через кнопку "❤️"
await slider_manager.start_slider(
    media_list=media_list,
    product_ids=product_ids,
    source="favorites",
    user_id=user_id
)
```

**Особенности**:
- Динамическое обновление при добавлении/удалении из избранного
- Кнопка "❤️" для управления избранным
- Специальная логика возврата к источнику
- Автоматическое закрытие при пустом избранном

**Уникальное поведение**:
```python
# При удалении товара из избранного в слайдере
if slider_source == "favorites":
    # Получаем новый список избранных
    favorites = data_base.get_user_favorites(user_id)
    if not favorites:
        # Закрываем слайдер если избранное пустое
        await manager.edit("<b>У вас немає товарів у обраному!</b>")
        return
    # Обновляем слайдер с новым списком
```

**Использование**:
- `routers/profile_router.py` - запуск из профиля
- Динамическое обновление при изменении избранного

### 3. **Слайдер фильтров** (`source="filters"`)

**Описание**: Отображает товары, отфильтрованные по выбранным критериям

**Запуск**:
```python
# Из экрана фильтров через "Применить фильтры"
await slider_manager.start_slider(
    media_list=media, 
    product_ids=ids, 
    source="filters", 
    user_id=user_id
)
```

**Особенности**:
- Возврат к экрану фильтров
- Поддержка всех типов фильтров (категории, размеры, бренды, сезоны)
- Показ сообщения если товары не найдены
- Fallback на все товары при пустом результате

**Фильтрация**:
```python
active_filters = await FilterManager.get_active_filters(state)
clean_filters = {k: v for k, v in active_filters.items() if v is not None}
product_media = data_base.get_filtered_product_media(**clean_filters)

if not product_media:
    await callback.answer("❗ За вибраними фільтрами нічого не знайдено!")
    product_media = data_base.get_all_product_media()  # Fallback
```

**Использование**:
- `routers/navigation_router.py` - обработка фильтров
- `utils/filter_manager.py` - управление фильтрами

### 4. **Слайдер корзины** (`source="cart"`)

**Описание**: Отображает товары из корзины пользователя

**Запуск**:
```python
# Из главного меню или фильтров через кнопку корзины
await slider_manager.start_slider(
    media_list=media_list,
    product_ids=product_ids,
    source="cart",
    user_id=user_id,
    cart_items=cart_items
)
```

**Особенности**:
- Показывает информацию о размерах и количестве товаров
- Специальный caption с пометкой "🛍 корзина"
- Кнопка "📝 Оформити замовлення" (закомментирована)
- Отображение итоговой суммы корзины

**Формирование caption**:
```python
caption = f"🛍 корзина\n"
if size:
    caption += f"Розмір: {size}\n"
caption += f"Кількість: {qty}\n"
if orig_caption:
    caption += f"{orig_caption}"
```

**Использование**:
- `routers/profile_router.py` - запуск из главного меню и фильтров
- Отображение корзины в слайдере

### 5. **Слайдер "Для меня"** (`source="sizes"`)

**Описание**: Отображает товары, подходящие по размерам пользователя

**Запуск**:
```python
# Из главного меню через кнопку "🎯"
await slider_manager.start_slider(
    media_list=media, 
    product_ids=ids, 
    source="sizes", 
    user_id=user_id
)
```

**Особенности**:
- Фильтрация по сохраненным размерам пользователя
- Автоматический подбор товаров
- Кнопка "🎯" в главном меню
- Возврат к фильтрам

**Фильтрация по размерам**:
```python
user = data_base.sql_get_user(user_id, 'size')
user_sizes = {
    'jacket_size': user.get('jacket_size'),
    'jersey_size': user.get('jersey_size'), 
    'jeans_size': user.get('jeans_size')
}
# Фильтрация товаров по размерам пользователя
```

**Использование**:
- `routers/navigation_router.py` - обработка кнопки "🎯"
- Персональные рекомендации

## Клавиатуры слайдеров

### Единая клавиатура `get_slider_keyboard()`

Все слайдеры используют единую функцию создания клавиатуры с параметрами:

```python
def get_slider_keyboard(
    paused=False, 
    expanded=True, 
    index=0, 
    total=0, 
    user_id=None, 
    is_favorite=False,
    product_id=None, 
    source="main", 
    is_in_cart=False
):
```

### Кнопки по типам слайдеров

#### Общие кнопки (все слайдеры):
- **Навигация**: `←` `→` - переключение товаров
- **Автопроигрывание**: `||` `ᐅ` - пауза/воспроизведение
- **Корзина**: `➕` `➖` - добавление/удаление из корзины
- **Детали**: `інфо` - детальный просмотр товара

#### Специальные кнопки:
- **Избранное**: `⭐` `☆` - только если есть `product_id`
- **Размеры**: появляются после нажатия `➕`
- **Оформление заказа**: `📝 Оформити замовлення` - только для корзины (закомментирована)

### Логика возврата

```python
# Определяем callback для кнопки закрытия в зависимости от источника
if source == "filters":
    close_callback = NavigationCallback(action="filters", current_level="filters", breadcrumbs="").pack()
elif source == "sizes":
    close_callback = NavigationCallback(action="filters", current_level="filters", breadcrumbs="").pack()
elif source == "favorites":
    close_callback = NavigationCallback(action="filters", current_level="filters", breadcrumbs="").pack()
else:
    close_callback = NavigationCallback(action="main", current_level="main", breadcrumbs="").pack()
```

## Состояние FSM

### Основные ключи состояния:

```python
{
    "index": 0,                    # Текущий индекс слайда
    "playing": False,              # Автопроигрывание активно
    "expanded": True,              # Клавиатура открыта
    "media_list": [...],           # Список медиа
    "product_ids": [...],          # ID товаров
    "user_id": 123,                # ID пользователя
    "favorites_data": {...},       # Кэш избранного
    "cart_data": {...},            # Кэш корзины
    "slider_source": "main",       # Тип слайдера
    "speed": 3,                    # Скорость автопроигрывания
    "cycle_count": 0               # Счетчик циклов
}
```

### Кэширование данных

Для оптимизации производительности используется кэширование:
- `favorites_data` - статус избранного для всех товаров в слайдере
- `cart_data` - статус корзины для всех товаров в слайдере

## Отличия в поведении

### 1. **Caption товаров**

- **Корзина**: Добавляется информация о размере и количестве
- **Избранное**: Добавляется пометка "⭐ favorite"
- **Остальные**: Стандартный caption товара

### 2. **Отображение корзины**

- **Корзина**: Показывается блок с итоговой суммой
- **Фильтры**: Показывается компактный блок корзины
- **Остальные**: Стандартное отображение

### 3. **Динамическое обновление**

- **Избранное**: Автоматическое обновление при изменении избранного
- **Корзина**: Обновление при изменении корзины
- **Остальные**: Статичные списки товаров

## Интеграция с другими компонентами

### 1. **Фильтры**
```python
# Получение отфильтрованных товаров
active_filters = await FilterManager.get_active_filters(state)
product_media = data_base.get_filtered_product_media(**active_filters)
```

### 2. **Корзина**
```python
# Проверка статуса корзины
is_in_cart = data_base.is_product_in_cart(user_id, product_id, size_value=size_value)
```

### 3. **Избранное**
```python
# Проверка статуса избранного
is_favorite = data_base.is_product_in_favorites(user_id, product_id)
```

### 4. **Отслеживание просмотров**
```python
# Запись просмотра товара
data_base.add_product_view(
    user_id=user_id,
    product_id=product_id,
    view_type='slider',
    view_duration=slider_speed
)
```

## Заключение

Система слайдеров в проекте представляет собой универсальное решение с:

- **5 основными типами** слайдеров с уникальным поведением
- **Единым интерфейсом** управления через `SliderManager`
- **Контекстным поведением** на основе параметра `source`
- **Кэшированием данных** для оптимизации производительности
- **Динамическим обновлением** для избранного и корзины
- **Централизованным управлением** через FSM

Каждый тип слайдера имеет свои особенности, но все используют общую архитектуру, что обеспечивает консистентность интерфейса и упрощает поддержку кода. 