from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
import asyncio
from aiogram.exceptions import TelegramBadRequest
from data_base.models import data_base
from keyboards.kb import NavigationCallback, create_main_menu_keyboard
from utils.breadcrambs import decode_breadcrumbs
from utils.filter_manager import FilterManager
from utils.functions import get_caption
from utils import logger
from utils.slider_manager import SliderManager, format_media
from utils.message_manager import MessageManager
from routers.start_router import animate_caption
from utils.category_utils import get_category_label, get_subcategory_label

router = Router()


@router.callback_query(NavigationCallback.filter(F.action == "main"))
async def process_main_menu(callback: CallbackQuery, callback_data: NavigationCallback, state: FSMContext,
                            manager: MessageManager):
    """Обработка главного меню"""
    # Немедленно отвечаем на callback чтобы убрать "Завантаження"
    await callback.answer()
    
    # Отмена предыдущей анимации
    data = await state.get_data()
    if "animation_task" in data and not data["animation_task"].done():
        data["animation_task"].cancel()
        try:
            await data["animation_task"]
        except asyncio.CancelledError:
            pass

    current_level = callback_data.current_level
    breadcrumbs = decode_breadcrumbs(callback_data.breadcrumbs)

    if current_level == "catalog":
        data = await state.get_data()
        if "animation_task" in data and not data["animation_task"].done():
            data["animation_task"].cancel()
            logger.debug("Анимация остановлена")

        # Загружаем фильтры пользователя из базы в FSM
        await FilterManager.load_filters_from_db(state)
        active_filters = await FilterManager.get_active_filters(state)
        clean_filters = {k: v for k, v in active_filters.items() if v is not None and k != "sizes"}
        product_media = []
        sizes_dict = active_filters.get("sizes")
        if isinstance(sizes_dict, dict) and sizes_dict:
            size_values = [size for sublist in sizes_dict.values() for size in sublist]
            product_media = data_base.get_filtered_product_media(sizes=size_values, **clean_filters)
        else:
            product_media = data_base.get_filtered_product_media(**clean_filters)

        await state.update_data(
            product_media=product_media,
            catalog_msg_id=callback.message.message_id  # Сохраняем ID текущего сообщения
        )

        # Загружаем корзину пользователя из базы в FSM
        user_id = callback.from_user.id
        cart_items = data_base.get_cart(user_id)
        await state.update_data(cart_items=cart_items)
        # Запускаем слайдер, передавая текущее сообщение
        user_id = callback.from_user.id
        data_base.increment_restart_count(user_id)  # Считаем запуск слайдера как активность
        
        # Форматируем данные и запускаем слайдер
        media, ids = format_media(product_media)
        slider_manager = SliderManager(manager, state)
        await slider_manager.start_slider(media_list=media, product_ids=ids, source="main", user_id=user_id, cart_items=cart_items, breadcrumbs="main")

    elif current_level == "filters":
        # Показываем новое меню фильтров с красивым капшеном
        active_filters = await FilterManager.get_active_filters(state)
        text = FilterManager.create_beautiful_caption(active_filters)
        # Устанавливаем "filters" как корневой уровень breadcrumbs
        filters_breadcrumbs = "filters"
        markup = await FilterManager.create_simple_filters_keyboard(filters_breadcrumbs, active_filters, user_id=callback.from_user.id, state=state)
        await manager.edit(text, reply_markup=markup)
    else:
        # Запускаем анимацию для главного меню
        active_filters = await FilterManager.get_active_filters(state)
        start_kb = create_main_menu_keyboard(callback.from_user.id, "", "main", active_filters)
        # Передаем user_id в состояние перед вызовом get_caption
        await state.update_data(user_id=callback.from_user.id)
        caption = await get_caption(state)

        # Если callback.message это media (например, фото), отправляем новое текстовое сообщение
        if hasattr(callback.message, 'photo') and callback.message.photo:
            new_msg = await manager.send(caption, reply_markup=start_kb, edit_mode=False)
            message_id = new_msg.message_id
            # Удаляем старое media-сообщение
            try:
                await callback.message.delete()
            except TelegramBadRequest as e:
                if "message to delete not found" not in str(e):
                    logger.warning(f"Не удалось удалить media-сообщение: {e}")
        else:
            try:
                await manager.edit(caption, reply_markup=start_kb)
                message_id = callback.message.message_id
            except TelegramBadRequest as e:
                logger.error(f"Ошибка при редактировании сообщения: {e}")
                return

        # Запускаем анимацию
        animation_task = asyncio.create_task(
            animate_caption(manager, start_kb, message_id, state)
        )
        await state.update_data({
            "animation_task": animation_task,
            "animation_message_id": message_id
        })





@router.callback_query(NavigationCallback.filter(F.action == "filters"))
async def process_filters(callback: CallbackQuery, callback_data: NavigationCallback, state: FSMContext,
                          manager: MessageManager):
    await callback.answer()
    data = await state.get_data()
    if "animation_task" in data and not data["animation_task"].done():
        data["animation_task"].cancel()
        try:
            await data["animation_task"]
        except asyncio.CancelledError:
            pass
    breadcrumbs = decode_breadcrumbs(callback_data.breadcrumbs)
    
    # Если breadcrumbs пустые, устанавливаем "filters" как корневой уровень
    if not breadcrumbs:
        breadcrumbs = "filters"
    
    active_filters = await FilterManager.get_active_filters(state)
    text = FilterManager.create_beautiful_caption(active_filters)
    markup = await FilterManager.create_simple_filters_keyboard(breadcrumbs, active_filters, user_id=callback.from_user.id, state=state)
    await manager.edit(text, reply_markup=markup)


@router.callback_query(NavigationCallback.filter(F.action == "edit_filter"))
async def process_edit_filter(callback: CallbackQuery, callback_data: NavigationCallback, state: FSMContext,
                              manager: MessageManager):
    await callback.answer()
    filter_type = callback_data.current_level
    breadcrumbs = decode_breadcrumbs(callback_data.breadcrumbs)
    
    # Упрощаем breadcrumbs - используем только тип фильтра
    new_breadcrumbs = filter_type
    
    active_filters = await FilterManager.get_active_filters(state)
    filter_titles = {
        "category": "Категорія",
        "subcategory": "Підкатегорія",
        "size": "Розмір",
        "season": "Сезон",
        "brand": "Бренд"
    }
    text = f"<blockquote>🔍 <b>Вибір фільтра</b>\n\n📋 <i>Виберіть значення для фільтра:</i> <b>{filter_titles.get(filter_type, filter_type.title())}</b>\n\n💡 <i>Поточне значення буде замінено</i></blockquote>"
    markup = FilterManager.create_filter_selection_keyboard(filter_type, new_breadcrumbs, active_filters)
    await manager.edit(text, reply_markup=markup)


@router.callback_query(NavigationCallback.filter(F.action == "select_filter"))
async def process_select_filter(callback: CallbackQuery, callback_data: NavigationCallback, state: FSMContext):
    """
    Обрабатывает выбор значения для фильтра.
    - Для простых фильтров: сохраняет и возвращает в меню фильтров.
    - Для сложных размеров: сохраняет и ОБНОВЛЯЕТ ТЕКУЩУЮ КЛАВИАТУРУ.
    """
    filter_type = callback_data.breadcrumbs.split(':')[-1]
    value = callback_data.current_level
    
    is_complex_size = '_' in value and value.startswith(('jacket', 'jersey', 'jeans'))

    if is_complex_size:
        # --- НОВАЯ ЛОГИКА ДЛЯ СЛОЖНЫХ РАЗМЕРОВ ---
        # 1. Сохраняем выбор
        await FilterManager.set_complex_size_filter(state, value)
        
        # 2. Получаем обновленные фильтры
        active_filters = await FilterManager.get_active_filters(state)
        
        # 3. Пересобираем и обновляем ТУ ЖЕ САМУЮ клавиатуру выбора размеров
        keyboard = FilterManager.create_filter_selection_keyboard(
            filter_type='size',  # Мы знаем, что это фильтр размеров
            breadcrumbs=callback_data.breadcrumbs,
            active_filters=active_filters
        )
        
        # Просто обновляем клавиатуру, не меняя текст
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer() # Отправляем пустое уведомление, чтобы кнопка перестала "грузиться"

    else:
        # --- СТАРАЯ ЛОГИКА ДЛЯ ПРОСТЫХ ФИЛЬТРОВ (остается без изменений) ---
        # 1. Сохраняем фильтр
        await FilterManager.set_filter(state, filter_type, value)
        
        # 2. Получаем обновленные данные
        active_filters = await FilterManager.get_active_filters(state)
        caption = FilterManager.create_beautiful_caption(active_filters)
        
        # 3. Возвращаемся в главное меню фильтров
        new_breadcrumbs = "main:filters" 
        keyboard = await FilterManager.create_simple_filters_keyboard(
            breadcrumbs=new_breadcrumbs,
            active_filters=active_filters,
            user_id=callback.from_user.id
        )

        await callback.message.edit_text(caption, reply_markup=keyboard)
        await callback.answer()


@router.callback_query(NavigationCallback.filter(F.action == "add_neighbor_size"))
async def process_add_neighbor_size(callback: CallbackQuery, callback_data: NavigationCallback, state: FSMContext):
    """Обработка добавления соседнего размера."""
    size_category = callback_data.current_level
    
    # 1. Добавляем соседний размер
    await FilterManager.add_neighbor_size_filter(state, size_category)
    
    # 2. Получаем обновленные фильтры
    active_filters = await FilterManager.get_active_filters(state)
    
    # 3. Пересобираем и обновляем клавиатуру, как в process_select_filter
    keyboard = FilterManager.create_filter_selection_keyboard(
        filter_type='size',
        breadcrumbs=callback_data.breadcrumbs,
        active_filters=active_filters
    )
    
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer("✅ Сусідній розмір додано")


@router.callback_query(NavigationCallback.filter(F.action == "clear_size_filters"))
async def process_clear_size_filters(callback: CallbackQuery, callback_data: NavigationCallback, state: FSMContext):
    """Обработка сброса фильтров размеров."""
    # 1. Очищаем фильтры размеров в состоянии
    await FilterManager.clear_size_filters(state)
    
    # 2. Получаем обновленные (пустые) фильтры
    active_filters = await FilterManager.get_active_filters(state)
    
    # 3. Пересобираем и обновляем клавиатуру выбора размеров
    keyboard = FilterManager.create_filter_selection_keyboard(
        filter_type='size',
        breadcrumbs=callback_data.breadcrumbs,
        active_filters=active_filters
    )
    
    # Обновляем только клавиатуру
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer("Усі розміри скинуто")


@router.callback_query(NavigationCallback.filter(F.action == "clear_single_filter"))
async def process_clear_single_filter(callback: CallbackQuery, callback_data: NavigationCallback, state: FSMContext,
                                      manager: MessageManager):
    """Обработка сброса одного фильтра"""
    await callback.answer()
    filter_type = callback_data.current_level
    breadcrumbs = decode_breadcrumbs(callback_data.breadcrumbs)
    
    # Сбрасываем конкретный фильтр
    await FilterManager.clear_filter(state, filter_type)
    
    # Возвращаемся к главному экрану фильтров
    active_filters = await FilterManager.get_active_filters(state)
    text = FilterManager.create_beautiful_caption(active_filters)
    # Используем "filters" как breadcrumbs для возврата
    return_breadcrumbs = "filters"
    markup = await FilterManager.create_simple_filters_keyboard(return_breadcrumbs, active_filters, user_id=callback.from_user.id, state=state)
    await manager.edit(text, reply_markup=markup)


@router.callback_query(NavigationCallback.filter(F.action == "clear_filters"))
async def process_clear_filters(callback: CallbackQuery, callback_data: NavigationCallback, state: FSMContext,
                                manager: MessageManager):
    await callback.answer()
    await FilterManager.clear_all_filters(state)
    breadcrumbs = decode_breadcrumbs(callback_data.breadcrumbs)
    
    # Если breadcrumbs пустые, устанавливаем "filters" как корневой уровень
    if not breadcrumbs:
        breadcrumbs = "filters"
    
    active_filters = await FilterManager.get_active_filters(state)
    text = FilterManager.create_beautiful_caption(active_filters)
    markup = await FilterManager.create_simple_filters_keyboard(breadcrumbs, active_filters, user_id=callback.from_user.id, state=state)
    await manager.edit(text, reply_markup=markup)


@router.callback_query(NavigationCallback.filter(F.action == "apply_filters"))
async def process_apply_filters(callback: CallbackQuery, callback_data: NavigationCallback, state: FSMContext,
                                manager: MessageManager):
    active_filters = await FilterManager.get_active_filters(state)
    clean_filters = {k: v for k, v in active_filters.items() if v is not None}
    logger.debug(f"process_apply_filters: clean_filters={clean_filters}")

    # --- Новый блок: поддержка фильтрации по нескольким размерам ---
    product_media = []
    sizes_dict = active_filters.get("sizes")
    if isinstance(sizes_dict, dict) and sizes_dict:
        # Собираем все значения из всех списков в один плоский список
        size_values = [size for sublist in sizes_dict.values() for size in sublist]
        product_media = data_base.get_filtered_product_media(sizes=size_values, **{k: v for k, v in clean_filters.items() if k != "size" and k != "sizes"})
    else:
        product_media = data_base.get_filtered_product_media(**clean_filters)

    logger.debug(f"process_apply_filters: found {len(product_media)} products")
    if not product_media:
        await callback.answer("❗ За вибраними фільтрами нічого не знайдено! Показую всі товари.")
        product_media = data_base.get_all_product_media()
    await state.update_data(product_media=product_media)
    user_id = callback.from_user.id
    data_base.increment_restart_count(user_id)  # Считаем запуск слайдера как активность
    # Форматируем данные и запускаем слайдер
    media, ids = format_media(product_media)
    slider_manager = SliderManager(manager, state)
    await slider_manager.start_slider(media_list=media, product_ids=ids, source="filters", user_id=user_id, breadcrumbs="filters")


@router.callback_query(NavigationCallback.filter(F.action == "show_personal_slider"))
async def process_show_personal_slider(callback: CallbackQuery, callback_data: NavigationCallback, state: FSMContext, manager: MessageManager):
    """
    Обработка кнопки '🎯 Підходить мені':
    Получает размеры пользователя, фильтрует товары по этим размерам и запускает слайдер.
    """
    user_id = callback.from_user.id
    user = data_base.sql_get_user(user_id, 'size')
    size_json = user[0] if user and user[0] else '{}'
    import json
    try:
        size_obj = json.loads(size_json)
    except Exception:
        size_obj = {}
    # Собираем все размеры пользователя (куртка, трикотаж, джинсы)
    user_sizes = set()
    for key in ("jacket", "jersey", "jeans"):
        val = size_obj.get(key)
        if val:
            user_sizes.add(val)
    if not user_sizes:
        await manager.edit("<b>Вкажіть хоча б один розмір у профілі!</b>")
        await callback.answer()
        return
    # Собираем все товары, подходящие по любому из размеров
    product_media = []
    product_ids_set = set()
    for size in user_sizes:
        media = data_base.get_filtered_product_media(size=size)
        for item in media:
            pid = item[1]
            if pid not in product_ids_set:
                product_media.append(item)
                product_ids_set.add(pid)
    if not product_media:
        await manager.edit("<b>Немає товарів, які підходять під ваші розміри.</b>")
        await callback.answer()
        return
    cart_items = data_base.get_cart(user_id)
    await state.update_data(cart_items=cart_items)
    # --- определяем source для возврата ---
    # Для кнопки "Мої розміри" всегда используем source="sizes"
    source = "sizes"
    
    # Определяем breadcrumbs на основе callback_data
    # Кнопка "Мої розміри" может быть в главном меню или в фильтрах
    if callback_data.breadcrumbs:
        breadcrumbs = decode_breadcrumbs(callback_data.breadcrumbs)
        # Если breadcrumbs содержат тип фильтра, значит мы в фильтрах
        if breadcrumbs in ["category", "subcategory", "size", "season", "brand"]:
            breadcrumbs = "filters"
        elif breadcrumbs == "" or breadcrumbs == "main":
            breadcrumbs = "main"
    else:
        breadcrumbs = "main"
    
    # Форматируем данные и запускаем слайдер
    media, ids = format_media(product_media)
    slider_manager = SliderManager(manager, state)
    await slider_manager.start_slider(media_list=media, product_ids=ids, source=source, user_id=user_id, cart_items=cart_items, breadcrumbs=breadcrumbs)
    await callback.answer()


# Диагностика и тесты
@router.callback_query(F.data == "debug_db")
async def debug_database(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    await callback.answer()
    debug_info = data_base.debug_database_content()
    message = f"🔍 <b>Диагностика базы данных</b>\n\n"
    message += f"📦 Всего активных товаров: <b>{debug_info['total_active_products']}</b>\n"
    message += f"🖼️ Товаров с медиа: <b>{debug_info['products_with_media']}</b>\n\n"
    if debug_info['available_categories']:
        message += f"📂 Категории: {', '.join(debug_info['available_categories'])}\n"
    if debug_info['available_brands']:
        message += f"🏷️ Бренды: {', '.join(debug_info['available_brands'])}\n"
    if debug_info['available_seasons']:
        message += f"🌤️ Сезоны: {', '.join(debug_info['available_seasons'])}\n"
    message += "\n📊 <b>Количество товаров по категориям:</b>\n"
    for category, count in debug_info['category_counts'].items():
        message += f"• {category}: {count}\n"
    if debug_info['sample_products']:
        message += "\n📝 <b>Примеры товаров:</b>\n"
        for product in debug_info['sample_products'][:3]:
            message += f"• ID {product['id']}: {product['name']}\n"
            message += f"  Категория: {product['category']}, Бренд: {product['brand']}\n"
    await manager.edit(message)


@router.callback_query(F.data == "test_filters")
async def test_filters(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    await callback.answer()
    active_filters = await FilterManager.get_active_filters(state)
    clean_filters = {k: v for k, v in active_filters.items() if v is not None}
    test_result = data_base.test_filter_query(**clean_filters)
    if test_result['results']['success']:
        message = f"✅ <b>Тест фильтров успешен!</b>\n\n"
        message += f"🔍 Найдено товаров: <b>{test_result['results']['count']}</b>\n"
        message += f"📋 Активные фильтры: {FilterManager.format_active_filters(active_filters)}"
    else:
        message = f"❌ <b>Ошибка в фильтрах!</b>\n\n"
        message += f"🔧 Ошибка: {test_result['results']['error']}\n"
        message += f"📋 Активные фильтры: {FilterManager.format_active_filters(active_filters)}"
    await manager.edit(message)


@router.callback_query(NavigationCallback.filter(F.action == "back"))
async def process_back(callback: CallbackQuery, callback_data: NavigationCallback, state: FSMContext,
                       manager: MessageManager):
    await callback.answer()
    breadcrumbs = decode_breadcrumbs(callback_data.breadcrumbs)

    # Если breadcrumbs содержат тип фильтра, возвращаемся к фильтрам
    if breadcrumbs in ["category", "subcategory", "size", "season", "brand"]:
        # Возвращаемся к фильтрам с красивым капшеном
        active_filters = await FilterManager.get_active_filters(state)
        text = FilterManager.create_beautiful_caption(active_filters)
        # Устанавливаем правильные breadcrumbs для фильтров
        filters_breadcrumbs = "filters"
        markup = await FilterManager.create_simple_filters_keyboard(filters_breadcrumbs, active_filters, user_id=callback.from_user.id, state=state)
        await manager.edit(text, reply_markup=markup)
    else:
        # Обычная навигация назад - возвращаемся к главному меню
        await process_main_menu(callback, callback_data, state, manager)


@router.callback_query(F.data == "debug_subcategories")
async def debug_subcategories(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    await callback.answer()
    debug_info = data_base.debug_subcategories()
    message = f"🔍 <b>Отладка подкатегорий</b>\n\n"
    message += f"📦 Всего товаров: <b>{debug_info['total_products']}</b>\n\n"
    
    for category, products in debug_info['by_category'].items():
        message += f"📂 <b>{get_category_label(category)}:</b> {len(products)} товаров\n"
        subcategories = {}
        for product in products:
            subcat = product['subcategory']
            subcat_label = get_subcategory_label(category, subcat)
            if subcat not in subcategories:
                subcategories[subcat_label] = 0
            subcategories[subcat_label] += 1
        
        for subcat, count in subcategories.items():
            message += f"  • {subcat}: {count}\n"
        message += "\n"
    
    message += "📝 <b>Примеры товаров:</b>\n"
    for product in debug_info['sample_products']:
        message += f"• ID {product['id']}: {product['name']}\n"
        message += f"  {get_category_label(product['category'])}/{get_subcategory_label(product['category'], product['subcategory'])}\n"
    
    await manager.edit(message)