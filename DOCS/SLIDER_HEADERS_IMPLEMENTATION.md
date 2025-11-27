# Реализация заголовков слайдеров

## 🎯 Цель
Добавить видимые, красивые украинские заголовки ко всем слайдерам, указывающие тип слайдера.

## 📋 Заголовки по типам слайдеров:
- 🛍 **Каталог** - для главного слайдера (`source="main"`)
- 🔍 **Фільтр** - для слайдера фильтров (`source="filters"`)
- ❤️ **Обране** - для слайдера избранного (`source="favorites"`)
- 🎯 **Мої розміри** - для слайдера "Для меня" (`source="sizes"`)
- 🛒 **Кошик** - для слайдера корзины (`source="cart"`)

## 🔧 Реализация

### 1. Метод `_get_slider_header()` в `SliderManager`

```python
def _get_slider_header(self, source: str) -> str:
    """Возвращает заголовок слайдера в зависимости от источника"""
    headers = {
        "main": "🛍 <b>Каталог</b>",
        "filters": "🔍 <b>Фільтр</b>", 
        "favorites": "❤️ <b>Обране</b>",
        "sizes": "🎯 <b>Мої розміри</b>",
        "cart": "🛒 <b>Кошик</b>"
    }
    header = headers.get(source, "🛍 <b>Каталог</b>")
    logger.debug(f"_get_slider_header: source='{source}', header='{header}'")
    return header
```

### 2. Обновление `get_full_slider_caption()`

```python
async def get_full_slider_caption(self, product_id: int, user_id: Optional[int], cart_items: Optional[list] = None, show_cart_block: bool = True, source: str = "main") -> str:
    """Формирует caption для слайдера с учетом актуального состояния корзины."""
    # Добавляем заголовок слайдера
    slider_header = self._get_slider_header(source)
    logger.debug(f"get_full_slider_caption: product_id={product_id}, source='{source}', header='{slider_header}'")
    
    caption = await self.create_slider_caption(product_id)
    if not show_cart_block:
        return f"{slider_header}\n\n{caption}"
    # ... остальная логика
```

### 3. Передача `source` в `update_photo()`

```python
# Получаем источник из состояния
slider_source = data.get("slider_source", "main")

caption = await self.get_full_slider_caption(product_id, user_id, cart_items=cart_items, show_cart_block=expanded, source=slider_source)
```

## 📍 Места запуска слайдеров

### Каталог (`source="main"`)
- `routers/navigation_router.py:66` - главное меню
- `routers/product_view_router.py:64` - просмотр товара
- `routers/catalog_router.py:67` - каталог

### Фильтры (`source="filters"`)
- `routers/navigation_router.py:248` - применение фильтров

### Избранное (`source="favorites"`)
- `routers/profile_router.py:821` - слайдер избранного

### Мої розміри (`source="sizes"`)
- `routers/navigation_router.py:297` - персональные размеры

### Кошик (`source="cart"`)
- `routers/profile_router.py:1000` - слайдер корзины

## 🔍 Логирование

Добавлено логирование для отладки:
- `_get_slider_header()` - логирует source и полученный заголовок
- `get_full_slider_caption()` - логирует product_id, source и заголовок

## ✅ Результат

Теперь каждый слайдер имеет четкий, красивый заголовок на украинском языке с соответствующим эмодзи, который помогает пользователю понять, в каком разделе он находится. 