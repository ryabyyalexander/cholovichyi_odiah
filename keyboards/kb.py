from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from enum import Enum
from typing import Type
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from utils import admins
from utils.breadcrambs import encode_breadcrumbs
from utils.lexicon import btn, LOYALTY_LEXICON
from enums.sizes_enums import JacketSizes, JerseySizes, JeansSizes
from data_base.models import data_base
from enums.main_menu_enum import RegisteredMainMenu


class NavigationCallback(CallbackData, prefix="nav"):
    action: str
    current_level: str
    breadcrumbs: str


def create_main_menu_keyboard(user_id: int, breadcrumbs: str = "", action: str = "main",
                              active_filters: dict = {}) -> InlineKeyboardMarkup:
    """
    Создает главное меню:
    - Кнопки "Каталог" и "Фильтры" показываются только если есть активные товары
    - Кнопка "Профиль" показывается всегда
    - Кнопка "Для меня" показывается если есть сохраненные размеры
    """
    builder = InlineKeyboardBuilder()

    # Проверяем, есть ли активные товары в базе
    has_active_products = False
    if data_base:
        has_active_products = data_base.execute_query(
            "SELECT 1 FROM products WHERE is_active = 1 LIMIT 1"
        ).fetchone() is not None

    # Ensure active_filters is a dict
    if active_filters is None:
        active_filters = {}
    has_filters = active_filters and any(active_filters.values())

    # Добавляем кнопки меню
    for item in RegisteredMainMenu:
        # Пропускаем кнопку MY_SIZE - добавим её отдельно если нужно
        if item == RegisteredMainMenu.MY_SIZE:
            continue

        # Для кнопок CATALOG и FILTERS проверяем наличие активных товаров
        if item in [RegisteredMainMenu.CATALOG, RegisteredMainMenu.FILTERS] and not has_active_products:
            continue

        # Кнопка PROFILE показывается всегда
        if item == RegisteredMainMenu.PROFILE:
            button_text = f"{item.emoji} {item.label}"
            builder.button(
                text=button_text,
                callback_data=NavigationCallback(
                    action=action,
                    current_level=item.value,
                    breadcrumbs=encode_breadcrumbs(breadcrumbs)
                )
            )
            continue

        # Меняем текст кнопки Каталог в зависимости от наличия фильтров
        if item == RegisteredMainMenu.CATALOG:
            # Получаем количество товаров по фильтрам
            clean_filters = {k: v for k, v in (active_filters or {}).items() if
                             v is not None and k != "sizes"} if active_filters else {}
            products_count = 0
            sizes_dict = (active_filters or {}).get("sizes")
            if isinstance(sizes_dict, dict) and sizes_dict:
                size_values = [size for sublist in sizes_dict.values() for size in sublist]
                if size_values:
                    products_count = data_base.get_filtered_product_count(sizes=size_values, **clean_filters)
            else:
                products_count = data_base.get_filtered_product_count(**clean_filters)
            if has_filters:
                button_text = f"{item.emoji} {products_count} мод." if products_count > 0 else f"{item.emoji}"
            else:
                button_text = f"{item.emoji}{item.label} {products_count} мод." if products_count > 0 else f"{item.emoji}{item.label}"
        else:
            button_text = f"{item.emoji} {item.label}"

        builder.button(
            text=button_text,
            callback_data=NavigationCallback(
                action=action,
                current_level=item.value,
                breadcrumbs=encode_breadcrumbs(breadcrumbs)
            )
        )

    # Размещаем кнопки: по 2 в ряд (если только профиль) или по 3 (если есть каталог и фильтры)
    if has_active_products:
        builder.adjust(3)
    else:
        builder.adjust(2)  # Только для кнопки профиля и других не скрытых кнопок

    # --- ДОБАВЛЯЕМ КНОПКУ "Обране" (⭐️ Лайк) ---
    favorite_button = None
    fav_count = data_base.get_favorite_product_count(user_id)
    if fav_count > 0:
        favorite_button = InlineKeyboardButton(
            text=f"❤️  {fav_count} мод.",
            callback_data="favorites_slider:main"
        )

    # --- ДОБАВЛЯЕМ КНОПКУ "Для мене" (Мої розміри) ---
    personal_button = None
    import json
    user = data_base.sql_get_user(user_id, 'size')
    user_size_json = user[0] if user and user[0] else None
    has_sizes = False
    if user_size_json:
        try:
            size_obj = json.loads(user_size_json)
            for size_key in ["jacket", "jersey", "jeans"]:
                size_value = size_obj.get(size_key)
                if size_value and data_base.size_exists(size_value):
                    has_sizes = True
                    break
        except Exception:
            pass
    if has_sizes:
        total_count = 0
        if user_size_json:
            try:
                size_obj = json.loads(user_size_json)
                for size_key in ["jacket", "jersey", "jeans"]:
                    size_value = size_obj.get(size_key)
                    if size_value and data_base.size_exists(size_value):
                        count = data_base.get_filtered_product_count(size=size_value)
                        total_count += count
            except Exception:
                pass
        button_text = "🎯  "
        if total_count > 0:
            button_text += f"{total_count} мод."
        personal_button = InlineKeyboardButton(
            text=button_text,
            callback_data=NavigationCallback(
                action="show_personal_slider",
                current_level="main",
                breadcrumbs=encode_breadcrumbs(breadcrumbs)
            ).pack()
        )

    # --- ДОБАВЛЯЕМ КНОПКУ "Корзина" (🛍) ---
    cart_count = data_base.get_cart_count(user_id)
    cart_button = None
    if cart_count > 0:
        cart_button = InlineKeyboardButton(
            text=f"🛍 {cart_count} тов.",
            callback_data="cart_slider:main"
        )

    # --- Формируем персональный ряд ---
    personal_row = []
    if personal_button:
        personal_row.append(personal_button)
    if favorite_button:
        personal_row.append(favorite_button)
    if cart_button:
        personal_row.append(cart_button)
    if personal_row:
        builder.row(*personal_row)

    return builder.as_markup()

def create_keyboard(
        enum_class: Type[Enum],
        breadcrumbs: str = "",
        action: str = "",
        add_back: bool = True,
        add_close: bool = False,
        adjust: tuple = (3,),
        active_filters: dict = None
):
    builder = InlineKeyboardBuilder()
    if breadcrumbs is None:
        breadcrumbs = ""
    if active_filters is None:
        active_filters = {}

    # Определяем, для какого типа фильтра мы строим клавиатуру
    filter_key_map = {
        "Categories": "category",
        "JacketsCategory": "subcategory",
        "JeansCategory": "subcategory",
        "JerseyCategory": "subcategory",
        "Seasons": "season",
        "Brands": "brand",
        "JacketSizes": "size",
        "JerseySizes": "size",
        "JeansSizes": "size"
    }
    current_filter_key = filter_key_map.get(enum_class.__name__)

    # --- НОВАЯ ЛОГИКА УЧЕТА ФИЛЬТРА РАЗМЕРОВ ---
    sizes_dict = active_filters.get("sizes", {})
    size_values = [size for sublist in sizes_dict.values() for size in sublist]

    for item in enum_class:
        # Создаем копию активных фильтров для проверки
        # Исключаем сам фильтр, для которого строим кнопки, и старые 'sizes'
        filters_to_check = {k: v for k, v in active_filters.items() if k != current_filter_key and v is not None and k != 'sizes'}

        # Если мы строим клавиатуру категорий и есть выбранные размеры,
        # показываем только те категории, для которых выбран размер.
        if enum_class.__name__ == "Categories" and sizes_dict:
            category_map = {"jacket": "куртки", "jersey": "трикотаж", "jeans": "джинси"}
            allowed_categories = [category_map[cat_key] for cat_key in sizes_dict.keys()]
            if item.value not in allowed_categories:
                continue
        
        # ---- УЛУЧШЕННАЯ ЛОГИКА: ВЫВЕДЕНИЕ КАТЕГОРИИ ИЗ РАЗМЕРА ----
        # Если категория не установлена явно, но выбраны размеры только одного типа (например, только джинсовые)
        # мы можем вывести категорию и добавить ее в проверку для большей точности.
        if 'category' not in filters_to_check and sizes_dict:
            if len(sizes_dict) == 1: # Условие: размеры выбраны только для одного типа категорий
                category_map = {"jacket": "куртки", "jersey": "трикотаж", "jeans": "джинси"}
                inferred_category_key = list(sizes_dict.keys())[0]
                filters_to_check['category'] = category_map[inferred_category_key]
        # ---- КОНЕЦ УЛУЧШЕННОЙ ЛОГИКИ ----

        # Добавляем в проверку текущий элемент (потенциальную кнопку)
        if current_filter_key:
            filters_to_check[current_filter_key] = item.value

        # Добавляем плоский список размеров в проверку
        if size_values:
            filters_to_check['sizes'] = size_values

        # Универсальная проверка для всех типов кнопок
        if enum_class.__name__ != 'CreateProduct' and data_base.get_filtered_product_count(**filters_to_check) == 0:
            continue

        emoji = getattr(item, 'emoji', '')
        label = getattr(item, 'label', '')
        builder.button(
            text=f"{emoji} {label}".strip(),
            callback_data=NavigationCallback(
                action=action,
                current_level=item.value,
                breadcrumbs=encode_breadcrumbs(breadcrumbs)
            )
        )

    builder.adjust(*adjust)

    if add_back:
        back_button = InlineKeyboardBuilder()
        back_button.button(
            text="←  Назад",
            callback_data=NavigationCallback(
                action="back",
                current_level="",
                breadcrumbs=encode_breadcrumbs(breadcrumbs)
            )
        )
        builder.attach(back_button)

    if add_close:
        builder.row(InlineKeyboardButton(text=btn['x'],
                                         callback_data=NavigationCallback(action="main",
                                                                          # current_level="main",
                                                                          breadcrumbs="").pack()))

    return builder.as_markup()


def combine_keyboards(
        *keyboards: InlineKeyboardMarkup,
        breadcrumbs: str,
        add_back: bool = True,
        back_action: str = "back",
        adjust: tuple = (3,)
) -> InlineKeyboardMarkup:
    """
    Объединяет несколько клавиатур в одну.

    :param keyboards: Клавиатуры для объединения
    :param breadcrumbs: Текущие хлебные крошки
    :param add_back:добавить кнопку "Назад"
    :param back_action: Действие для кнопки "Назад"
    :param adjust: Кортеж с количеством кнопок в каждом ряду
    :return: Объединенная клавиатура
    """
    builder = InlineKeyboardBuilder()

    # Добавляем все кнопки из всех клавиатур
    for kb in keyboards:
        for row in kb.inline_keyboard:
            for button in row:
                builder.button(
                    text=button.text,
                    callback_data=button.callback_data
                )
    
    # Добавляем кнопку "Назад" если нужно
    if add_back:
        builder.button(
            text="←  Назад",
            callback_data=NavigationCallback(
                action=back_action,
                current_level="main",
                breadcrumbs=encode_breadcrumbs(breadcrumbs)
            )
        )

    # Выравниваем кнопки по указанному шаблону (всегда применяем adjust)
    builder.adjust(*adjust)

    return builder.as_markup()


# kb.py

def get_slider_keyboard(paused=False, expanded=True, index=0, total=0, user_id: int = 0, is_favorite=False,
                        product_id=None, source="main", is_in_cart=False,
                        selected_size=None, selected_product_id=None, show_sizes_for_product=None,
                        breadcrumbs: str = "", active_filters: dict = {}, detailed_sizes: dict = None):
    if active_filters is None:
        active_filters = {}
    if breadcrumbs is None:
        breadcrumbs = ""
    import logging
    logger = logging.getLogger(__name__)
    logger.debug(
        f"get_slider_keyboard: user_id={user_id}, is_favorite={is_favorite}, product_id={product_id}, source={source}")

    # --- НОВОЕ: если только один элемент, не показываем элементы управления ---
    if total == 1:
        # Только кнопка закрытия, "Детальніше", избранное и корзина
        if source == "filters":
            close_callback = NavigationCallback(action="filters", current_level="filters", breadcrumbs="").pack()
        elif source == "sizes":
            if breadcrumbs == "main" or breadcrumbs == "":
                close_callback = NavigationCallback(action="main", current_level="main", breadcrumbs="").pack()
            else:
                close_callback = NavigationCallback(action="filters", current_level="filters", breadcrumbs="").pack()
        elif source == "favorites":
            if breadcrumbs == "main" or breadcrumbs == "":
                close_callback = NavigationCallback(action="main", current_level="main", breadcrumbs="").pack()
            else:
                close_callback = NavigationCallback(action="filters", current_level="filters", breadcrumbs="").pack()
        elif source == "cart":
            if breadcrumbs == "main" or breadcrumbs == "":
                close_callback = NavigationCallback(action="main", current_level="main", breadcrumbs="").pack()
            else:
                close_callback = NavigationCallback(action="filters", current_level="filters", breadcrumbs="").pack()
        else:
            close_callback = NavigationCallback(action="main", current_level="main", breadcrumbs="").pack()
        # Кнопки: закрытия, инфо, избранное, корзина
        detail_row = []
        size_row = None
        if product_id and product_id > 0:
            star = btn['star_full'] if is_favorite else btn['star_clear']
            fav_count = data_base.get_product_favorites_count(product_id)
            if fav_count > 1:
                star += f" {fav_count}"
            cart_btn_text = btn['cart_remove'] if is_in_cart else btn['cart_add']
            cart_btn_callback = f"remove_from_cart:{product_id}" if is_in_cart else (
                f"show_sizes:{product_id}" if product_id else "show_sizes")

            # Собираем основной ряд кнопок
            detail_row = [
                InlineKeyboardButton(text=btn['x'], callback_data=close_callback),
                InlineKeyboardButton(text="ІНФО", callback_data=f"detail_view:{product_id}"),
            ]

            # Добавляем кнопку "Избранное" (звезду) только если это НЕ слайдер корзины
            if source != "cart":
                detail_row.append(InlineKeyboardButton(text=star, callback_data=f"toggle_favorite:{product_id}"))

            # Добавляем кнопку корзины
            detail_row.append(InlineKeyboardButton(text=cart_btn_text, callback_data=cart_btn_callback))

            # --- Добавляем ряд с размерами, если show_sizes_for_product == product_id ---
            if show_sizes_for_product == product_id:
                if selected_size and selected_product_id == product_id:
                    quantity_buttons = create_quantity_buttons(product_id, selected_size)
                    if quantity_buttons:
                        size_row = quantity_buttons
                else:
                    size_buttons = create_size_buttons(product_id, user_id, detailed_sizes=detailed_sizes)
                    if size_buttons:
                        size_row = size_buttons
                    else:
                        size_row = create_no_size_button(product_id)
        else:
            detail_row = [
                InlineKeyboardButton(text="ІНФО", callback_data="detail_view")
            ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[detail_row])
        if size_row:
            keyboard.inline_keyboard.append(size_row)

        # --- Добавляем кнопки для корзины даже при одном товаре ---
        if source == "cart":
            # Показываем кнопки только если в корзине есть товары
            if user_id:
                cart_items = data_base.get_cart(user_id)
                if cart_items:
                    # Кнопки в одном ряду
                    cart_buttons = [InlineKeyboardButton(text="🧹  Очистити", callback_data="cart_clear")]
                    if data_base.is_user_active(user_id):
                        cart_buttons.append(InlineKeyboardButton(text="🚀  Оформити", callback_data="order_cart"))
                    keyboard.inline_keyboard.append(cart_buttons)

        # --- Добавляем кнопку очистки фильтров (для случая с одним товаром) ---
        if user_id and active_filters and source not in ("favorites", "cart", "sizes"):
            has_simple_filters = any(
                active_filters.get(key) for key in ["category", "subcategory", "size", "season", "brand"])
            sizes_dict = active_filters.get("sizes", {})
            has_complex_size_filters = isinstance(sizes_dict, dict) and any(sizes_dict.values())

            if has_simple_filters or has_complex_size_filters:
                keyboard.inline_keyboard.append([
                    InlineKeyboardButton(
                        text="🧹 Очистити фільтри",
                        callback_data=NavigationCallback(
                            action="clear_filters",
                            current_level="",
                            breadcrumbs="filters"
                        ).pack()
                    )
                ])

        # --- Добавляем кнопку "Оформити", если товар в корзине ---
        if is_in_cart and source != "cart" and data_base.is_user_active(user_id):
            order_button = [InlineKeyboardButton(text="🚀 Оформити", callback_data="order_cart")]
            keyboard.inline_keyboard.append(order_button)

        return keyboard

    # Логика кнопки:
    # - Если клавиатура открыта (expanded=True) → "ᐅ" (play) - потому что мы в режиме паузы
    # - Если клавиатура закрыта (expanded=False) → "||" (pause) - потому что автопроигрывание запущено
    button_text = "ᐅ" if expanded else "||"
    button_callback = "play" if expanded else "pause"

    control_buttons = [
        InlineKeyboardButton(text=button_text, callback_data=button_callback)
    ]
    # Кнопка корзины: ➕ или ➖
    cart_btn_text = btn['cart_remove'] if is_in_cart else btn['cart_add']
    cart_btn_callback = f"remove_from_cart:{product_id}" if is_in_cart else (
        f"show_sizes:{product_id}" if product_id else "show_sizes")
    # Кнопка избранного (звезда)
    star = btn['star_full'] if is_favorite else btn['star_clear']
    fav_count = data_base.get_product_favorites_count(product_id)
    if fav_count > 1:
        star += f" {fav_count}"

    # Собираем кнопки навигации
    arrow_button = [
        InlineKeyboardButton(text=f"{index + 1}/{total}", callback_data="info"),
        InlineKeyboardButton(text="←", callback_data="prev"),
        InlineKeyboardButton(text="→", callback_data="next"),
    ]
    # Добавляем кнопку "Избранное" (звезду) только если это НЕ слайдер корзины
    if source != "cart":
        arrow_button.append(InlineKeyboardButton(text=star, callback_data=f"toggle_favorite:{product_id}"))

    # Определяем callback для кнопки закрытия в зависимости от источника и breadcrumbs
    if source == "filters":
        close_callback = NavigationCallback(action="filters", current_level="filters", breadcrumbs="").pack()
    elif source == "sizes":
        # Для "Мої розміри" определяем возврат по breadcrumbs (как у избранного)
        if breadcrumbs == "main" or breadcrumbs == "":
            close_callback = NavigationCallback(action="main", current_level="main", breadcrumbs="").pack()
        else:
            close_callback = NavigationCallback(action="filters", current_level="filters", breadcrumbs="").pack()
    elif source == "favorites":
        # Для избранного определяем возврат по breadcrumbs
        if breadcrumbs == "main" or breadcrumbs == "":
            close_callback = NavigationCallback(action="main", current_level="main", breadcrumbs="").pack()
        else:
            close_callback = NavigationCallback(action="filters", current_level="filters", breadcrumbs="").pack()
    elif source == "cart":
        # Для корзины всегда возврат на главную, независимо от breadcrumbs
        close_callback = NavigationCallback(action="main", current_level="main", breadcrumbs="").pack()
    else:
        close_callback = NavigationCallback(action="main", current_level="main", breadcrumbs="").pack()

    # Кнопка "Детальніше" с кнопками избранного и закрытия (только если есть product_id и он не равен 0)
    detail_button = []
    if product_id and product_id > 0:
        # Кнопка избранного (звезда)
        star = btn['star_full'] if is_favorite else btn['star_clear']
        logger.debug(f"get_slider_keyboard: creating star button - is_favorite={is_favorite}, star={star}")
        detail_button = [
            InlineKeyboardButton(text=btn['x'], callback_data=close_callback),
            InlineKeyboardButton(text="ІНФО", callback_data=f"detail_view:{product_id}"),
            InlineKeyboardButton(text=cart_btn_text, callback_data=cart_btn_callback)
        ]
        if is_in_cart and source != "cart" and data_base.is_user_active(user_id):
            detail_button.append(InlineKeyboardButton(text="🚀", callback_data="order_cart"))
    else:
        # Если нет product_id или он равен 0, показываем кнопку "Детальніше" без звездочки
        detail_button = [
            InlineKeyboardButton(text="ІНФО", callback_data="detail_view")
        ]

    close_button = [
        InlineKeyboardButton(text=btn['x'], callback_data=close_callback)
    ]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[control_buttons])

    # Показываем расширенную клавиатуру всегда, кроме случая когда нажат play (expanded=False)
    if expanded:
        keyboard.inline_keyboard.extend([arrow_button])

        # Добавляем кнопку "Детальніше" если есть product_id
        if detail_button:
            keyboard.inline_keyboard.extend([detail_button])

        # --- Добавляем ряд с размерами только после нажатия ➕ ---
        if expanded and not is_in_cart and product_id and product_id > 0:
            if show_sizes_for_product == product_id:
                if selected_size and selected_product_id == product_id:
                    quantity_buttons = create_quantity_buttons(product_id, selected_size)
                    if quantity_buttons:
                        keyboard.inline_keyboard.append(quantity_buttons)
                else:
                    size_buttons = create_size_buttons(product_id, user_id, detailed_sizes=detailed_sizes)
                    if size_buttons:
                        keyboard.inline_keyboard.append(size_buttons)
                    else:
                        no_size_button = create_no_size_button(product_id)
                        keyboard.inline_keyboard.append(no_size_button)

        # --- Добавляем кнопки для корзины ---
        if source == "cart":
            # Показываем кнопки только если в корзине есть товары
            if user_id:
                cart_items = data_base.get_cart(user_id)
                if cart_items:
                    # Кнопки в одном ряду
                    cart_buttons = [InlineKeyboardButton(text="🧹  Очистити", callback_data="cart_clear")]
                    if data_base.is_user_active(user_id):
                        cart_buttons.append(InlineKeyboardButton(text="🚀 Оформити", callback_data="order_cart"))
                    keyboard.inline_keyboard.append(cart_buttons)

        # --- Добавляем кнопки для избранного ---
        if source == "favorites":
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text="🧹 Очистити обране", callback_data="favorites_clear_all")
            ])

        # if user_id in admins:
        #     admin_buttons = []
        #     admin_buttons.append(InlineKeyboardButton(text="🔍  Фільтри", callback_data=NavigationCallback(action="filters",
        #                                                                     current_level="filters", breadcrumbs="").pack()))
        #
        #     if cart_not_empty:
        #         admin_buttons.append(InlineKeyboardButton(text="🛍  Ваш кошик", callback_data="cart"))
        #     keyboard.inline_keyboard.extend([admin_buttons])

        # Кнопка закрытия для слайдера избранного - убрана, так как не нужна
        # if source == "favorites":
        #     keyboard.inline_keyboard.extend([close_button])

        # --- Добавляем кнопку возврата в главное меню для слайдеров favorites и sizes ---
    # --- Добавляем кнопку очистки фильтров для слайдера фильтров ---
    # Не показывать кнопку очистки фильтров в избранном, корзине и моих размерах
    if user_id and active_filters and source not in ("favorites", "cart", "sizes") and expanded:
        # Проверяем как простые фильтры, так и сложный фильтр размеров ('sizes')
        has_simple_filters = any(
            active_filters.get(key) for key in ["category", "subcategory", "size", "season", "brand"])
        sizes_dict = active_filters.get("sizes", {})
        has_complex_size_filters = isinstance(sizes_dict, dict) and any(sizes_dict.values())

        if has_simple_filters or has_complex_size_filters:
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text="🧹 Очистити фільтри",
                    callback_data=NavigationCallback(
                        action="clear_filters",
                        current_level="",
                        breadcrumbs="filters"
                    ).pack()
                )
            ])

    # --- Добавляем кнопку "Оформити", если товар в корзине ---
    # if is_in_cart and source != "cart":
    #     order_button = [InlineKeyboardButton(text="🚀 Оформити", callback_data="order_cart")]
    #     keyboard.inline_keyboard.append(order_button)

    # --- Добавляем кнопку редактирования для админов (только если слайдер на паузе) ---
    if user_id in admins and expanded:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text="✏️ Редагувати",
                callback_data="edit_product"
            )
        ])

    return keyboard

def get_product_detail_keyboard(product_id: int, current_index: int = 0, total_photos: int = 0, user_id: int = None) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для детального просмотра товара.
    
    Args:
        product_id: ID товара
        current_index: Текущий индекс фото
        total_photos: Общее количество фото
        user_id: ID пользователя для проверки прав админа
        
    Returns:
        InlineKeyboardMarkup с кнопками навигации и управления
    """
    builder = InlineKeyboardBuilder()
    
    # Кнопки навигации по фото - первые 3 в один ряд
    nav_buttons = []
    
    # Кнопка "Предыдущее фото"
    if current_index > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="←", callback_data=f"detail_prev:{product_id}:{current_index}")
        )
    else:
        nav_buttons.append(
            InlineKeyboardButton(text="•", callback_data="no_action")
        )
    
    # Индикатор текущего фото
    nav_buttons.append(
        InlineKeyboardButton(text=f"{current_index + 1}/{total_photos}", callback_data="no_action")
    )
    
    # Кнопка "Следующее фото"
    if current_index < total_photos - 1:
        nav_buttons.append(
            InlineKeyboardButton(text="→", callback_data=f"detail_next:{product_id}:{current_index}")
        )
    else:
        nav_buttons.append(
            InlineKeyboardButton(text="•", callback_data="no_action")
        )
    
    # Размещаем первые 3 кнопки в один ряд
    builder.row(*nav_buttons)
    
    
    
    # Кнопка возврата к слайдеру - по одной в ряду
    builder.row(
        InlineKeyboardButton(
            text="←  Назад",
            callback_data=f"detail_back_to_slider:{product_id}"
        )
    )
    
    # Кнопка закрытия - по одной в ряду (всегда последней)
    # builder.row(
    #     InlineKeyboardButton(
    #         text="╳",
    #         callback_data=NavigationCallback(action="main", current_level="main", breadcrumbs="").pack()
    #     )
    # )
    
    return builder.as_markup()


def edit_product_keyboard(product_id: int) -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру для редактирования продукта.
    """
    builder = InlineKeyboardBuilder()

    # Получаем статус товара
    product = data_base.sql_get_product(product_id)
    is_active = product.get('is_active', 0) if product else 0

    # Основные кнопки редактирования
    builder.row(
        InlineKeyboardButton(text="📂 Категорія", callback_data=f"edit_category:{product_id}"),
        InlineKeyboardButton(text="🗂 Підкатегорії", callback_data=f"edit_subcategory:{product_id}"),
        InlineKeyboardButton(text="🌦 Сезон", callback_data=f"edit_season:{product_id}"),
        InlineKeyboardButton(text="✏️ Назва", callback_data=f"edit_name:{product_id}"),
        InlineKeyboardButton(text="™️ Бренд", callback_data=f"edit_brand:{product_id}"),
        InlineKeyboardButton(text="📝 Опис", callback_data=f"edit_desc:{product_id}"),
        InlineKeyboardButton(text="💵 Закуп", callback_data=f"edit_purchase_price:{product_id}"),
        InlineKeyboardButton(text="💰 Ціна", callback_data=f"edit_price:{product_id}"),
        InlineKeyboardButton(text="🔥 Знижка", callback_data=f"edit_discount:{product_id}"),
        InlineKeyboardButton(text="👑 Скидка лояльности", callback_data=f"edit_loyalty_tiers:{product_id}"),
        InlineKeyboardButton(text="📏 Розміри", callback_data=f"edit_sizes:{product_id}"),
        InlineKeyboardButton(text="🖼 Фото", callback_data=f"edit_photos:{product_id}"),
        InlineKeyboardButton(text="❌ Видалити", callback_data=f"product_delete:{product_id}")
    )

    # Кнопки активации/деактивации
    if is_active:
        builder.row(InlineKeyboardButton(text="🚫 Деактивувати", callback_data=f"deactivate_product:{product_id}"))
    else:
        builder.row(InlineKeyboardButton(text="✅ Активувати", callback_data=f"activate_product:{product_id}"))

    builder.adjust(2, 3, 1, 4, 2, 2)
    builder.row(
        InlineKeyboardButton(text="←  Назад", callback_data=f"return_to_product:{product_id}")
    )
    return builder.as_markup()


def loyalty_tiers_keyboard(product_id: int, current_tiers: list) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора уровней лояльности.
    """
    from data_base.constants import LOYALTY_DISCOUNTS, LOYALTY_ICONS
    builder = InlineKeyboardBuilder()

    for tier_name, discount in LOYALTY_DISCOUNTS.items():
        is_selected = tier_name in current_tiers
        icon = LOYALTY_ICONS.get(tier_name, '')
        text = f"{'✅' if is_selected else ''} {icon} {tier_name.capitalize()} ({discount}%)"
        builder.button(
            text=text,
            callback_data=f"toggle_loyalty_tier:{product_id}:{tier_name}"
        )

    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(text="←  Назад", callback_data=f"menu:{product_id}")
    )
    return builder.as_markup()


def get_selection_keyboard(options: list, action: str, product_id: int, exists_func=None) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора из списка опций.
    Если передан exists_func(option), то добавляет только те опции, для которых exists_func(option) == True.
    """
    builder = InlineKeyboardBuilder()

    for option in options:
        if exists_func and not exists_func(option):
            continue
        builder.button(
            text=option,
            callback_data=f"{action}:{product_id}:{option}"
        )

    builder.adjust(3)  # 3 кнопки в ряду
    builder.row(
        InlineKeyboardButton(text="←  Назад", callback_data=f"menu:{product_id}")
    )
    return builder.as_markup()


def sizes_selection_keyboard(product_id, current_sizes):
    """
    Клавиатура выбора размеров с отображением текущего количества
    """
    builder = InlineKeyboardBuilder()

    # Кнопки размеров
    for enum_group in [JacketSizes, JerseySizes, JeansSizes]:
        for size in enum_group:
            size_val = size.value
            qty = current_sizes.get(size_val, 0)
            text = f"✅ {size_val} ({qty})" if qty > 0 else size_val
            callback_data = f"select_qty:{product_id}:{size_val}" if qty > 0 else f"add_size:{product_id}:{size_val}"
            builder.button(text=text, callback_data=callback_data)

    builder.row(
        InlineKeyboardButton(text="←  Назад", callback_data=f"menu:{product_id}")
    )

    # РАЗМЕЩЕНИЕ КНОПОК: по 3 в ряду
    # Ручная настройка: измените числа в adjust() для нужного размещения
    # Например: (3,) - все кнопки по 3 в ряду
    # (2, 3, 2) - первый ряд 2 кнопки, второй 3, третий 2
    builder.adjust(3, 3, 2, 3, 3, 3, 3, 3, 3, 1)
    # Кнопка "Закрити" всегда последней строкой
    # builder.row(
    #     InlineKeyboardButton(text="╳", callback_data=NavigationCallback(action="main", current_level="main", breadcrumbs="").pack())
    # )
    return builder.as_markup()


def qty_selection_keyboard(product_id: int, size_val: str) -> InlineKeyboardMarkup:
    """Клавиатура выбора количества (0-5)"""
    builder = InlineKeyboardBuilder()
    for qty in [0, 1, 2, 3, 4, 5]:
        builder.button(text=str(qty), callback_data=f"update_qty:{product_id}:{size_val}:{qty}")
    builder.adjust(3)
    builder.row(
        InlineKeyboardButton(text="←  Назад", callback_data=f"menu:{product_id}")
    )
    # Кнопка "Закрити" всегда последней строкой
    # builder.row(
    #     InlineKeyboardButton(text="╳", callback_data=NavigationCallback(action="main", current_level="main", breadcrumbs="").pack())
    # )
    return builder.as_markup()



def kb_media_edit(product_id, list_media):
    builder = InlineKeyboardBuilder()
    [builder.button(text=f"media {i + 1}", callback_data=f"select_media:{product_id}:{list_media['id']}") for i in list_media]
    return builder.as_markup()


def media_grid_keyboard(product_id: int, media_list: list) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру-сетку для управления медиа товара.
    
    Args:
        product_id: ID товара
        media_list: Список медиа с информацией [id, file_id, type, is_main, caption]
        
    Returns:
        InlineKeyboardMarkup с сеткой фото и кнопками управления
    """
    builder = InlineKeyboardBuilder()
    
    # Создаем сетку 2x2 или 3x3 в зависимости от количества фото
    max_photos = min(len(media_list), 9)  # Максимум 9 фото в сетке
    
    for i in range(max_photos):
        media = media_list[i]
        media_id = media[0]  # ID медиа
        is_main = media[3]   # is_main флаг
        
        # Иконка для фото (⭐️ если главное, ⬜️ если нет)
        icon = "⭐️" if is_main else "⬜️"
        
        # Кнопка фото
        builder.button(
            text=f"{icon} Фото {i+1}",
            callback_data=f"media_action:{product_id}:{media_id}:view"
        )
    
    # Если фото меньше 4, добавляем кнопку "Добавить фото"
    if len(media_list) < 9:
        builder.button(
            text="✅  Додати фото",
            callback_data=f"media_action:{product_id}:0:add"
        )
    
    # Кнопка возврата
    builder.button(
        text="← Назад",
        callback_data=f"media_action:{product_id}:0:back"
    )
    
    # Размещаем кнопки: фото по 3 в ряду, управление отдельно
    if len(media_list) <= 3:
        builder.adjust(3, 1, 1)  # 3 фото в ряду, добавить фото, управление
    elif len(media_list) <= 6:
        builder.adjust(3, 3, 1, 1)  # 2 ряда по 3 фото, добавить фото, управление
    else:
        builder.adjust(3, 3, 3, 1, 1)  # 3 ряда по 3 фото, добавить фото, управление
    
    # Кнопка "Закрити" всегда последней строкой
    # builder.row(
    #     InlineKeyboardButton(text="╳", callback_data=NavigationCallback(action="main", current_level="main", breadcrumbs="").pack())
    # )
    return builder.as_markup()


def media_actions_keyboard(product_id: int, media_id: int, is_main: bool) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру действий для конкретного медиа.
    
    Args:
        product_id: ID товара
        media_id: ID медиа
        is_main: Является ли медиа главным
        
    Returns:
        InlineKeyboardMarkup с кнопками действий
    """
    builder = InlineKeyboardBuilder()
    
    # Кнопка "Редактировать caption"
    builder.row(
        InlineKeyboardButton(
            text="📝  Редагувати підпис",
            callback_data=f"media_action:{product_id}:{media_id}:edit_caption"
        )
    )
    
    # Кнопка "Сделать главным" (только если не главное)
    if not is_main:
        builder.row(
            InlineKeyboardButton(
                text="⭐️ Зробити головним",
                callback_data=f"media_action:{product_id}:{media_id}:set_main"
            )
        )
    
    # Кнопка "Удалить"
    builder.row(
        InlineKeyboardButton(
            text="❌ Видалити",
            callback_data=f"media_action:{product_id}:{media_id}:delete"
        )
    )
    
    # Кнопка "Назад к сетке"
    builder.row(
        InlineKeyboardButton(
            text="←  Назад",
            callback_data=f"media_action:{product_id}:0:grid"
        )
    )
    
    # Кнопка "Закрити" всегда последней строкой
    # builder.row(
    #     InlineKeyboardButton(text="╳", callback_data=NavigationCallback(action="main", current_level="main", breadcrumbs="").pack())
    # )
    
    return builder.as_markup()


def confirm_delete_media_keyboard(product_id: int, media_id: int) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру подтверждения удаления медиа.
    
    Args:
        product_id: ID товара
        media_id: ID медиа для удаления
        
    Returns:
        InlineKeyboardMarkup с кнопками подтверждения
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="✅ Так, видалити",
            callback_data=f"media_action:{product_id}:{media_id}:confirm_delete"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="❌ Скасувати",
            callback_data=f"media_action:{product_id}:{media_id}:cancel_delete"
        )
    )
    
    # Кнопка "Закрити" всегда последней строкой
    builder.row(
        InlineKeyboardButton(text="╳", callback_data=NavigationCallback(action="main", current_level="main", breadcrumbs="").pack())
    )
    
    return builder.as_markup()


def order_points_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=LOYALTY_LEXICON['order_use_points_btn'], callback_data='order_use_points')]
        ]
    )


def create_size_buttons(product_id: int, user_id: int = None, detailed_sizes: dict = None) -> list:
    """
    Создает кнопки размеров для товара, используя детальную информацию о наличии и резервах.
    
    Args:
        product_id: ID товара
        user_id: ID пользователя для проверки корзины
        detailed_sizes: Словарь с детальной информацией о размерах.
        
    Returns:
        Список кнопок размеров или пустой список если размеров нет
    """
    from enums.sizes_enums import JacketSizes, JerseySizes, JeansSizes

    if not detailed_sizes:
        return []

    # Проверяем, какие размеры уже в корзине
    cart_sizes = set()
    if user_id:
        cart_items = data_base.get_cart(user_id)
        for item in cart_items:
            if item.get("product_id") == product_id:
                size = item.get("size_value")
                if size:
                    cart_sizes.add(size)

    size_buttons = []

    # Группируем размеры по типам
    size_groups = {
        "jacket": [s.value for s in JacketSizes],
        "jersey": [s.value for s in JerseySizes],
        "jeans": [s.value for s in JeansSizes]
    }

    for group_key, size_list in size_groups.items():
        for size in size_list:
            if size in detailed_sizes:
                details = detailed_sizes[size]
                qty = details['quantity']
                is_reserved = details['is_reserved']
                is_in_cart = size in cart_sizes
                is_letter = group_key == 'jersey'

                display_value = size.upper() if is_letter else size

                # Только добавляем кнопку, если товар в наличии или зарезервирован
                if qty > 0 or is_reserved:
                    if is_reserved:
                        text = f"❓{display_value}"
                        callback_data = f"join_waitlist:{product_id}:{size}"
                    else:  # qty > 0
                        text = f"✅ {display_value}" if is_in_cart else display_value
                        if qty > 1 and not is_in_cart:  # Не показываем кол-во, если в корзине
                            text += f"({qty})"
                        callback_data = f"select_size:{product_id}:{size}"
                    
                    size_buttons.append(InlineKeyboardButton(text=text, callback_data=callback_data))

    return size_buttons


def create_quantity_buttons(product_id: int, size: str, max_qty: int = 5) -> list:
    """
    Создает кнопки выбора количества.
    
    Args:
        product_id: ID товара
        size: Выбранный размер
        max_qty: Максимальное количество для показа
        
    Returns:
        Список кнопок количества
    """
    from data_base.models import data_base
    
    available_sizes = data_base.get_available_sizes(product_id)
    available_qty = available_sizes.get(size, 0)
    
    # Ограничиваем максимальное количество доступным
    max_qty = min(max_qty, available_qty)
    
    quantity_buttons = []
    
    # Создаем кнопки с числами от 1 до max_qty
    for qty in range(1, max_qty + 1):
        text = str(qty)
        callback_data = f"select_quantity:{product_id}:{size}:{qty}"
        quantity_buttons.append(InlineKeyboardButton(text=text, callback_data=callback_data))
    
    return quantity_buttons


def create_no_size_button(product_id: int) -> list:
    """
    Создает кнопку для добавления товара без размера.
    
    Args:
        product_id: ID товара
        
    Returns:
        Список с одной кнопкой
    """
    return [InlineKeyboardButton(text="Без розміру", callback_data=f"select_size:{product_id}:no_size")]


def create_size_filter_keyboard(breadcrumbs: str, action: str, selected_sizes: dict = None, adjust: tuple = (4,), active_filters: dict = None):
    """
    Создает клавиатуру для фильтра размеров по категориям.
    Поддерживает выбор нескольких размеров (пары) и добавление соседнего размера.
    selected_sizes: {'jacket': ['50', '52'], 'jeans': ['32']}
    """
    from enums.sizes_enums import JacketSizes, JerseySizes, JeansSizes
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    from utils.breadcrambs import encode_breadcrumbs
    from .kb import NavigationCallback

    selected_sizes = selected_sizes or {}
    if active_filters is None:
        active_filters = {}
    final_keyboard = []

    base_filters = {k: v for k, v in active_filters.items() if k != 'sizes' and v is not None}

    size_categories = {
        "jacket": ("🧥 Куртки", JacketSizes),
        "jersey": ("👕 Трикотаж", JerseySizes),
        "jeans": ("👖 Джинси", JeansSizes)
    }

    for cat_key, (cat_label, enum_class) in size_categories.items():
        buttons_row = []
        category_filters = base_filters.copy()
        category_filters['category'] = {"jacket": "куртки", "jersey": "трикотаж", "jeans": "джинси"}[cat_key]

        if not data_base.check_filter_combination_exists(**category_filters):
            continue

        # Получаем текущий выбор для данной категории
        current_selection = selected_sizes.get(cat_key, [])

        for item in enum_class:
            filters_to_check = category_filters.copy()
            filters_to_check['size'] = item.value

            if data_base.check_filter_combination_exists(**filters_to_check):
                emoji = getattr(item, 'emoji', '')
                label = getattr(item, 'label', '')
                # Проверяем, есть ли размер в списке выбранных
                is_selected = item.value in current_selection
                text = f"{'✅ ' if is_selected else ''}{emoji} {label}".strip()
                buttons_row.append(
                    InlineKeyboardButton(
                        text=text,
                        callback_data=NavigationCallback(
                            action=action,
                            current_level=f"{cat_key}_{item.value}",
                            breadcrumbs=encode_breadcrumbs(breadcrumbs)
                        ).pack()
                    )
                )
        
        if buttons_row:
            final_keyboard.append([InlineKeyboardButton(text=cat_label, callback_data="ignore")])
            # Разделяем кнопки на ряды
            for i in range(0, len(buttons_row), adjust[0]):
                final_keyboard.append(buttons_row[i:i+adjust[0]])

            # --- НОВАЯ ЛОГИКА: Добавление кнопки для соседнего размера ---
            if len(current_selection) == 1:
                # Проверяем, есть ли у последнего размера больший сосед
                try:
                    all_sizes = list(enum_class)
                    last_selected_size = current_selection[0]
                    current_index = all_sizes.index(enum_class(last_selected_size))
                    if current_index + 1 < len(all_sizes):
                         final_keyboard.append([
                            InlineKeyboardButton(
                                text="✅  Додати сусідній",
                                callback_data=NavigationCallback(
                                    action="add_neighbor_size",
                                    current_level=cat_key, # Передаем категорию для обработки
                                    breadcrumbs=encode_breadcrumbs(breadcrumbs)
                                ).pack()
                            )
                        ])
                except (ValueError, IndexError):
                    # Если размер не найден в enum, ничего не делаем
                    pass


    return InlineKeyboardMarkup(inline_keyboard=final_keyboard)
