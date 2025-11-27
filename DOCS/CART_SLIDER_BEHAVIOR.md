# Поведение слайдера корзины (`source="cart"`)

## Обзор

Параметр `source="cart"` определяет специальное поведение слайдера для отображения товаров из корзины пользователя. Это один из 5 типов слайдеров в системе, который имеет уникальные особенности и теперь работает по образцу слайдера избранного.

## 🎯 **Как формируется слайдер корзины**

Слайдер корзины формируется в функции `handle_cart_slider` в файле `routers/profile_router.py`:

```python
@router.callback_query(F.data.startswith("cart_slider"))
async def handle_cart_slider(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    """Запускает слайдер с товарами из корзины (папка корзины с отметкой cart)"""
    user_id = callback.from_user.id
    # Определяем источник запуска
    if ":" in callback.data:
        _, source = callback.data.split(":", 1)
    else:
        source = "profile"
    
    # Определяем breadcrumbs на основе источника
    if source == "filters":
        breadcrumbs = "filters"
    elif source == "profile":
        breadcrumbs = "profile"
    else:
        breadcrumbs = "main"
    
    # Получаем товары из корзины
    cart_items = data_base.get_cart(user_id)
    if not cart_items:
        await callback.answer("Ваш кошик порожній!")
        return
    
    # Получаем медиа для каждого товара из корзины
    media_list = []
    product_ids = []
    for item in cart_items:
        product_id = item.get("product_id")
        product_media = data_base.get_product_media(product_id)
        if product_media:
            main_media = None
            for media in product_media:
                if media[3]:
                    main_media = media
                    break
            if not main_media and product_media:
                main_media = product_media[0]
            if main_media:
                orig_caption = main_media[4] or ""
                size = item.get("size_value")
                qty = item.get("quantity", 1)
                caption = f"🛍 корзина\n"
                if size:
                    caption += f"Розмір: {size}\n"
                caption += f"Кількість: {qty}\n"
                if orig_caption:
                    caption += f"{orig_caption}"
                media_list.append({
                    "path": main_media[1],
                    "media_type": main_media[2],
                    "caption": caption
                })
                product_ids.append(product_id)
    
    if not media_list:
        await callback.answer("У товарів з кошика немає медіа!")
        return
    
    # Сохраняем данные для возврата к корзине
    await state.update_data(
        return_to_cart=True,
        cart_source=source
    )
    
    # Запускаем слайдер с товарами из корзины
    slider_manager = SliderManager(manager, state)
    # Для слайдера корзины всегда используем source="cart"
    slider_source = "cart"
    await slider_manager.start_slider(
        media_list=media_list,
        product_ids=product_ids,
        source=slider_source,
        user_id=user_id,
        cart_items=cart_items,
        breadcrumbs=breadcrumbs
    )
    await callback.answer(f"Запущено слайдер з {len(media_list)} товарами з кошика!")
```

**Процесс формирования:**
1. **Получение товаров из корзины** - `data_base.get_cart(user_id)`
2. **Извлечение медиа** - для каждого товара из корзины получается главное фото
3. **Форматирование caption** - добавляется пометка "🛍 корзина" с информацией о размере и количестве
4. **Сохранение контекста** - breadcrumbs и источник для возврата
5. **Запуск слайдера** - через `SliderManager.start_slider()`

## 📍 **Точки входа**

Слайдер корзины можно запустить из **3 мест**:

### 1. **Главное меню** (`keyboards/kb.py`)
```python
callback_data="cart_slider:main"
```
- Кнопка: `🛍 {count} тов.`
- Показывается только если есть товары в корзине

### 2. **Фильтры** (`utils/filter_manager.py`)
```python
callback_data="cart_slider:filters"
```
- Кнопка: `🛍 {count} тов.`
- Показывается в персональном ряду фильтров

### 3. **Профиль** (`routers/profile_router.py`)
```python
# callback_data="cart_slider"  # без двоеточия
```
- Кнопка в разделе "🛍 Кошик"
- Запускается без указания источника (по умолчанию "profile")

## 🧭 **Навигация после закрытия**

Навигация определяется в зависимости от **breadcrumbs**:

```python
elif source == "cart":
    # Для корзины определяем возврат по breadcrumbs (как у избранного)
    if breadcrumbs == "main" or breadcrumbs == "":
        close_callback = NavigationCallback(action="main", current_level="main", breadcrumbs="").pack()
    else:
        close_callback = NavigationCallback(action="filters", current_level="filters", breadcrumbs="").pack()
```

**Логика возврата:**
- **Из главного меню** → возврат в главное меню
- **Из фильтров** → возврат к фильтрам  
- **Из профиля** → возврат к фильтрам (fallback)

## 📍 **Где сохраняются breadcrumbs**

Breadcrumbs сохраняются в **FSM состоянии** в нескольких местах:

### 1. **При запуске слайдера** (`utils/slider_manager.py`)
```python
await self.state.update_data(
    index=0,
    msg_id=msg.message_id,
    playing=slider_autoplay,
    media_list=formatted_media,
    product_ids=product_ids,
    slider_media_list=formatted_media,
    slider_product_ids=product_ids,
    speed=slider_speed,
    expanded=True,
    slider_source=source,
    slider_breadcrumbs=breadcrumbs,  # Сохраняем breadcrumbs
    user_id=user_id,  # Сохраняем user_id в состоянии
    favorites_data=favorites_data,  # Сохраняем данные о избранном
    cart_data=cart_data  # Сохраняем данные о корзине
)
```

### 2. **При формировании заголовка** (`utils/slider_manager.py`)
```python
# Добавляем реальные breadcrumbs с стрелкой: откуда пришел → где сейчас
if breadcrumbs and breadcrumbs != "":
    if breadcrumbs == "filters":
        from_icon = "🔍"
    elif breadcrumbs == "profile":
        from_icon = "👤"
    else:
        from_icon = "🏠"
    header = f"<code>{from_icon} → {header}</code>"
```

### 3. **В обработчике закрытия** (`routers/slider_router.py`)
```python
@router.callback_query(NavigationCallback.filter(F.action == "main"), StateFilter("slider_viewing"))
async def handle_close_slider_from_favorites(callback: CallbackQuery, state: FSMContext):
    """Обработчик закрытия слайдера с возвратом к избранному, корзине или фильтрам"""
    try:
        data = await state.get_data()
        return_to_cart = data.get("return_to_cart", False)
        cart_source = data.get("cart_source", "")
        
        # Обработка возврата к корзине
        if return_to_cart and cart_source == "profile":
            # Возвращаемся к списку корзины
            from routers.profile_router import handle_cart
            chat_id = callback.message.chat.id
            message_manager = MessageManager(bot, state, chat_id)
            await state.update_data(return_to_cart=False, cart_source="")
            # Создаем фейковый callback для возврата к корзине
            class FakeCallback:
                def __init__(self, from_user, data):
                    self.from_user = from_user
                    self.data = data
                async def answer(self, text=None, show_alert=False, **kwargs):
                    pass
            
            fake_callback = FakeCallback(callback.from_user, NavigationCallback(action="main", current_level="cart", breadcrumbs="profile").pack())
            await handle_cart(fake_callback, state, message_manager)
            await callback.answer("← Повернувся до кошика")
        elif return_to_cart and cart_source == "filters":
            # Возвращаемся к фильтрам
            from routers.filters_router import process_filters_menu
            chat_id = callback.message.chat.id
            message_manager = MessageManager(bot, state, chat_id)
            await state.update_data(return_to_cart=False, cart_source="")
            await process_filters_menu(callback, state, message_manager)
            await callback.answer("← Повернувся до фільтрів")
        elif return_to_cart and cart_source == "main":
            # Возвращаемся на главное меню
            from routers.navigation_router import process_main_menu
            chat_id = callback.message.chat.id
            message_manager = MessageManager(bot, state, chat_id)
            await state.update_data(return_to_cart=False, cart_source="")
            # Создаем NavigationCallback для главного меню
            callback_data = NavigationCallback(action="main", current_level="", breadcrumbs="")
            await process_main_menu(callback, callback_data, state, message_manager)
            await callback.answer("← Повернувся до головного меню")
        else:
            await callback.answer("Слайдер закрито")
    except Exception as e:
        logger.error(f"Error in handle_close_slider_from_favorites: {e}")
        await callback.answer("⚠️ Помилка при закритті слайдера", show_alert=True)
```

## 🎯 **Особенности слайдера корзины**

1. **Динамическое обновление** - при изменении корзины слайдер автоматически обновляется
2. **Автоматическое закрытие** - если корзина становится пустой, слайдер закрывается
3. **Специальный caption** - добавляется пометка "🛍 корзина" с информацией о размере и количестве
4. **Кэширование данных** - статус корзины кэшируется в `cart_data`
5. **Контекстная навигация** - возврат зависит от источника запуска

## 🔄 **Динамическое обновление**

### При удалении товара из корзины
```python
# Обновляем слайдер корзины с новым списком
try:
    data = await state.get_data()
    slider_source = data.get("slider_source", "main")
    # Только если это слайдер корзины
    if slider_source == "cart":
        # Получаем новый список корзины
        cart_items = data_base.get_cart(user_id)
        if not cart_items:
            # Если корзина стала пустой — закрываем слайдер и показываем сообщение
            await manager.edit("<b>Ваш кошик порожній!</b>", reply_markup=None)
            return
        # Формируем новый media_list и product_ids
        media_list = []
        product_ids = []
        for item in cart_items:
            pid = item.get("product_id")
            product_media = data_base.get_product_media(pid)
            if product_media:
                main_media = None
                for media in product_media:
                    if media[3]:
                        main_media = media
                        break
                if not main_media and product_media:
                    main_media = product_media[0]
                if main_media:
                    orig_caption = main_media[4] or ""
                    size = item.get("size_value")
                    qty = item.get("quantity", 1)
                    caption = f"🛍 корзина\n"
                    if size:
                        caption += f"Розмір: {size}\n"
                    caption += f"Кількість: {qty}\n"
                    if orig_caption:
                        caption += f"{orig_caption}"
                    media_list.append({
                        "path": main_media[1],
                        "media_type": main_media[2],
                        "caption": caption
                    })
                    product_ids.append(pid)
        # Получаем текущий индекс
        current_index = data.get("index", 0)
        # Если текущий индекс больше нового списка — корректируем
        if current_index >= len(product_ids):
            current_index = max(0, len(product_ids) - 1)
        # Обновляем состояние
        await state.update_data(
            media_list=media_list,
            product_ids=product_ids,
            index=current_index
        )
        # Обновляем слайдер
        slider_manager = SliderManager(manager, state)
        await slider_manager.update_photo(
            current_index,
            paused=not data.get("playing", False),
            expanded=data.get("expanded", True),
            user_id=user_id
        )
except Exception as e:
    logger.error(f"Error updating slider after cart change: {e}")
    pass
```

### При добавлении товара в корзину
Аналогичная логика применяется в обработчиках:
- `handle_add_to_cart` - добавление в корзину
- `handle_select_size` - выбор размера
- `handle_select_quantity` - выбор количества

## 📋 **Сравнение с избранным**

| Аспект | Слайдер корзины | Слайдер избранного |
|--------|-----------------|-------------------|
| **Callback data** | `cart_slider:source` | `favorites_slider:source` |
| **Caption** | `🛍 корзина\nРозмір: L\nКількість: 2` | `⭐ favorite` |
| **Динамическое обновление** | При изменении корзины | При изменении избранного |
| **Автоматическое закрытие** | При пустой корзине | При пустом избранном |
| **Навигация** | По breadcrumbs | По breadcrumbs |
| **Кэширование** | `cart_data` | `favorites_data` |

## ✅ **Заключение**

Слайдер корзины теперь работает по единому образцу со слайдером избранного:

✅ **Единообразная архитектура** с избранным  
✅ **Динамическое обновление** при изменении корзины  
✅ **Контекстная навигация** по breadcrumbs  
✅ **Автоматическое закрытие** при пустой корзине  
✅ **Специальный caption** с информацией о товарах  
✅ **Кэширование данных** для оптимизации  

Это делает систему слайдеров более консистентной и предсказуемой для пользователей. 