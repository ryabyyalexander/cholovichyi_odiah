# 🚀 Slider Quick Start Guide

## Быстрый старт

### 1. Запуск слайдера

```python
from utils.slider_manager import SliderManager, format_media

# Получение данных
product_media = data_base.get_filtered_product_media(**filters)

# Форматирование
media, ids = format_media(product_media)

# Запуск
slider_manager = SliderManager(manager, state)
await slider_manager.start_slider(
    media_list=media, 
    product_ids=ids, 
    source="main", 
    user_id=user_id
)
```

### 2. Основные действия

| Действие | Кнопка | Обработчик |
|----------|--------|------------|
| Навигация | ⬅️ ➡️ | `prev`, `next` |
| Автопроигрывание | ▶️ ⏸️ | `play`, `pause` |
| Корзина | ➕ ➖ | `add_to_cart`, `remove_from_cart` |
| Избранное | ❤️ 🤍 | `favorite_add`, `favorite_remove` |
| Детали | 📋 | `detail_view` |

### 3. Состояние FSM

```python
{
    "index": 0,              # Текущий слайд
    "playing": False,        # Автопроигрывание
    "expanded": True,        # Клавиатура открыта
    "media_list": [...],     # Список медиа
    "product_ids": [...],    # ID товаров
    "user_id": 123,          # ID пользователя
    "favorites_data": {...}, # Кэш избранного
    "cart_data": {...}       # Кэш корзины
}
```

### 4. Обновление слайда

```python
await slider_manager.update_photo(
    index=1,           # Индекс слайда
    paused=False,      # На паузе
    expanded=True,     # Клавиатура открыта
    user_id=user_id    # ID пользователя
)
```

### 5. Обработка ошибок

```python
try:
    await slider_manager.update_photo(index)
except TelegramBadRequest:
    # Fallback: отправка нового сообщения
    await manager.send_media_message(...)
```

## Полезные ссылки

- 📖 [Полная документация](SLIDER_ARCHITECTURE.md)
- 🔧 [Исходный код](../utils/slider_manager.py)
- 🎯 [Роутеры](../routers/slider_router.py)
- 🧪 [Тесты](../tests/)

## Частые вопросы

**Q: Как добавить новый тип медиа?**
A: Обновите `format_media()` и добавьте обработку в `update_photo()`

**Q: Как изменить скорость автопроигрывания?**
A: Установите `speed` в FSM: `await state.update_data(speed=5)`

**Q: Как добавить новую кнопку?**
A: Создайте обработчик в `SliderRouter` и обновите `get_slider_keyboard()`

**Q: Как отладить проблемы?**
A: Включите логирование: `logger.debug(f"Slider state: {await state.get_data()}")` 