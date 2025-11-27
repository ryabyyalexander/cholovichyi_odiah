from typing import Dict, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from enums import Categories, Seasons, Brands, Filters
from enums.categories_enum import JacketsCategory, JeansCategory, JerseyCategory
from enums.sizes_enums import JacketSizes, JerseySizes, JeansSizes
from keyboards.kb import create_keyboard, NavigationCallback
from data_base.models import data_base
from utils.breadcrambs import encode_breadcrumbs
from utils.category_utils import get_subcategory_label, get_category_label
import logging
from utils.lexicon import btn

logger = logging.getLogger(__name__)


class FilterManager:
    FILTER_KEYS = ["category", "subcategory", "size", "season", "brand"]

    @staticmethod
    async def get_active_filters(state: FSMContext) -> Dict[str, Optional[str]]:
        data = await state.get_data()
        return data.get("active_filters", {
            "category": None,
            "subcategory": None,
            "size": None,
            "season": None,
            "brand": None
        })

    @staticmethod
    def _reset_dependent_filters(active_filters: Dict[str, Optional[str]], filter_type: str):
        """Сбрасывает зависимые фильтры при изменении основного фильтра"""
        if filter_type == "category":
            active_filters["subcategory"] = None
            active_filters["size"] = None
        elif filter_type == "subcategory":
            active_filters["size"] = None

    @staticmethod
    async def set_filter(state: FSMContext, filter_type: str, value: str):
        logger.debug(f"set_filter: filter_type={filter_type}, value={value}")
        active_filters = await FilterManager.get_active_filters(state)
        
        # Сбрасываем зависимые фильтры
        FilterManager._reset_dependent_filters(active_filters, filter_type)
        
        # Устанавливаем новый фильтр
        active_filters[filter_type] = value
        logger.debug(f"set_filter: updated active_filters={active_filters}")
        
        await state.update_data(active_filters=active_filters)
        # Сохраняем фильтры в БД
        data = await state.get_data()
        user_id = data.get("user_id")
        if user_id:
            data_base.set_user_filters(user_id, active_filters)

    @staticmethod
    async def set_complex_size_filter(state: FSMContext, size_data: str):
        """
        Устанавливает, снимает или сбрасывает выбор для сложного фильтра размеров.
        Теперь поддерживает список размеров для каждой категории.
        size_data: Строка в формате 'категория_размер', например 'jacket_50'.
        """
        logger.debug(f"set_complex_size_filter: size_data='{size_data}'")
        try:
            size_category, size_value = size_data.split('_', 1)
        except ValueError:
            logger.error(f"Некорректный формат size_data: {size_data}")
            return

        active_filters = await FilterManager.get_active_filters(state)
        sizes_dict = active_filters.get("sizes", {})
        if not isinstance(sizes_dict, dict):
            sizes_dict = {}

        current_selection = sizes_dict.get(size_category, [])

        # Если размер уже в списке, снимаем выбор (удаляем всю категорию)
        if size_value in current_selection:
            del sizes_dict[size_category]
            logger.debug(f"Снят выбор для категории '{size_category}'")
        else:
            # Иначе, устанавливаем новый выбор, сбрасывая предыдущий для этой категории
            sizes_dict[size_category] = [size_value]
            logger.debug(f"Установлен новый размер для '{size_category}': ['{size_value}']")

        active_filters["sizes"] = sizes_dict
        active_filters["size"] = None

        logger.debug(f"set_complex_size_filter: updated active_filters={active_filters}")

        await state.update_data(active_filters=active_filters)
        data = await state.get_data()
        user_id = data.get("user_id")
        if user_id:
            data_base.set_user_filters(user_id, active_filters)

    @staticmethod
    async def add_neighbor_size_filter(state: FSMContext, size_category: str):
        """
        Добавляет соседний (больший) размер к уже выбранному.
        Работает только если в категории выбран ровно один размер.
        """
        logger.debug(f"add_neighbor_size_filter: size_category='{size_category}'")
        active_filters = await FilterManager.get_active_filters(state)
        sizes_dict = active_filters.get("sizes", {})
        
        current_selection = sizes_dict.get(size_category)
        
        # Проверяем, что выбран ровно один размер
        if not current_selection or len(current_selection) != 1:
            logger.warning(f"Невозможно добавить соседний размер для {size_category}, т.к. выбор не равен 1.")
            return
            
        size_value = current_selection[0]
        
        # Определяем Enum с размерами на основе категории
        size_enum_map = {
            "jacket": JacketSizes,
            "jersey": JerseySizes,
            "jeans": JeansSizes
        }
        size_enum = size_enum_map.get(size_category)
        
        if not size_enum:
            logger.error(f"Не найден Enum размеров для категории: {size_category}")
            return
            
        # Находим следующий размер
        try:
            all_sizes = list(size_enum)
            current_index = all_sizes.index(size_enum(size_value))
            if current_index + 1 < len(all_sizes):
                neighbor_size = all_sizes[current_index + 1].value
                # Добавляем соседний размер в список
                sizes_dict[size_category].append(neighbor_size)
                logger.debug(f"Добавлен соседний размер для '{size_category}': '{neighbor_size}'")
            else:
                logger.debug(f"Для размера '{size_value}' нет большего соседа.")
                return # Ничего не делаем, если это последний размер
        except (ValueError, IndexError) as e:
            logger.error(f"Ошибка при поиске соседнего размера для {size_value}: {e}")
            return

        active_filters["sizes"] = sizes_dict
        await state.update_data(active_filters=active_filters)
        
        data = await state.get_data()
        user_id = data.get("user_id")
        if user_id:
            data_base.set_user_filters(user_id, active_filters)

    @staticmethod
    async def clear_filter(state: FSMContext, filter_type: str):
        """Сбрасывает конкретный фильтр"""
        active_filters = await FilterManager.get_active_filters(state)
        
        # --- НОВАЯ ЛОГИКА СБРОСА ---
        if filter_type == "size":
            # Если сбрасываем размер, очищаем и простой, и сложный фильтры
            active_filters["size"] = None
            if "sizes" in active_filters:
                active_filters["sizes"] = {} # или del active_filters["sizes"]
        else:
            active_filters[filter_type] = None
        # --- КОНЕЦ НОВОЙ ЛОГИКИ ---
        
        # Сбрасываем зависимые фильтры
        FilterManager._reset_dependent_filters(active_filters, filter_type)
        
        await state.update_data(active_filters=active_filters)
        # Сохраняем фильтры в БД
        data = await state.get_data()
        user_id = data.get("user_id")
        if user_id:
            data_base.set_user_filters(user_id, active_filters)

    @staticmethod
    async def clear_all_filters(state: FSMContext):
        empty_filters = {
            "category": None,
            "subcategory": None,
            "size": None,
            "season": None,
            "brand": None,
            "sizes": {} # <-- ДОБАВЛЕНО: Явно очищаем сложный фильтр
        }
        await state.update_data(active_filters=empty_filters)
        # Сохраняем фильтры в БД
        data = await state.get_data()
        user_id = data.get("user_id")
        if user_id:
            data_base.set_user_filters(user_id, empty_filters)

    @staticmethod
    async def clear_size_filters(state: FSMContext):
        """Сбрасывает только сложные фильтры размеров ('sizes')."""
        active_filters = await FilterManager.get_active_filters(state)
        
        # Очищаем сложный фильтр размеров
        if "sizes" in active_filters:
            active_filters["sizes"] = {}
        
        # Также на всякий случай очищаем и простой фильтр размера
        active_filters["size"] = None
        
        logger.debug(f"clear_size_filters: updated active_filters={active_filters}")
        
        await state.update_data(active_filters=active_filters)
        # Сохраняем фильтры в БД
        data = await state.get_data()
        user_id = data.get("user_id")
        if user_id:
            data_base.set_user_filters(user_id, active_filters)

    @staticmethod
    async def load_filters_from_db(state: FSMContext):
        data = await state.get_data()
        user_id = data.get("user_id")
        if user_id:
            filters = data_base.get_user_filters(user_id)
            if filters:
                await state.update_data(active_filters=filters)

    @staticmethod
    def create_beautiful_caption(active_filters: Dict[str, Optional[str]]) -> str:
        """Создает красивый капшен с активными фильтрами и контекстными объяснениями для каждого шага"""
        # --- СТАРЫЙ КАПШН (оставляем как было) ---
        if not any(active_filters.get(key) for key in FilterManager.FILTER_KEYS):
            base_caption = ("""<blockquote>
🔍 Фільтри товарів

📋 Оберіть параметри для пошуку товарів:

<b>Сезон</b> — весна-літо чи осінь-зима.
<b>Категоріі</b> — куртки, джинси, трикотаж
<b>Підкатегоріі</b> — уточніть тип речі, якщо потрібно.
<b>Розмір</b> — оберіть свій розмір, щоб бачити лише те, що підійде.
<b>Бренд</b> — якщо віддаєте перевагу певній марці.

💡 <b>Пояснення:</b>
Натисніть на будь-який фільтр, щоб обрати тільки необхідне.

👵 <i>Порада: якщо не впевнені, обирайте лише категорію або розмір — так простіше!</i>

</blockquote>"""
            )
        else:
            # Формируем красивый капшн с активными фильтрами
            caption_parts = ["🔍 <b>Активні фільтри:</b>\n"]
            filter_icons = {
                "category": "📂",
                "subcategory": "🗂",
                "size": "📏",
                "season": "🌦",
                "brand": "🏷"
            }
            filter_names = {
                "category": "Категорія",
                "subcategory": "Підкатегорія",
                "size": "Розмір",
                "season": "Сезон",
                "brand": "Бренд"
            }
            explanations_selected = {
                "category": lambda v: f"Знайдено товари з категорії <b>{v}</b>. Можна додати розмір або бренд для точнішого пошуку.",
                "subcategory": lambda v: f"Ви обрали підкатегорію <b>{v}</b>. Додайте розмір для ще точнішого підбору.",
                "size": lambda v: f"Показано товари у розмірі <b>{v}</b>. Можна змінити категорію або додати бренд.",
                "season": lambda v: f"Показано асортимент для сезону <b>{v}</b>. Додайте категорію чи розмір для точного підбору.",
                "brand": lambda v: f"Відображаються товари бренду <b>{v}</b>. Можна додати категорію чи розмір."
            }
            explanations_unselected = {
                "category": "Оберіть, що саме шукаєте: куртка, джинси, светр тощо.",
                "subcategory": "Уточніть тип речі, наприклад: коротка куртка, класичні джинси...",
                "size": "Вкажіть свій розмір — так ви побачите лише те, що вам підійде.",
                "season": "Виберіть сезон: весна-літо чи осінь-зима. Це допоможе знайти потрібний одяг.",
                "brand": "Можна обрати улюблений бренд, якщо маєте вподобання."
            }
            selected_keys = [k for k, v in active_filters.items() if v]
            unselected_keys = [k for k in FilterManager.FILTER_KEYS if not active_filters.get(k)]
            for key in FilterManager.FILTER_KEYS:
                value = active_filters.get(key)
                icon = filter_icons.get(key, "•")
                name = filter_names.get(key, key.title())
                if value:
                    display_value = FilterManager._get_display_value(key, value, active_filters)
                    caption_parts.append(f"{icon} <b>{name}:</b> {display_value}")
                    if key in explanations_selected:
                        caption_parts.append(f"<i>{explanations_selected[key](display_value)}</i>")
                else:
                    if key in explanations_unselected:
                        caption_parts.append(f"<i>{explanations_unselected[key]}</i>")
            clean_filters = {k: v for k, v in active_filters.items() if v is not None and k != "sizes"}
            products_count = 0
            sizes_dict = active_filters.get("sizes")
            if isinstance(sizes_dict, dict) and sizes_dict:
                # Собираем все значения размеров в плоский список
                size_values = [size for sublist in sizes_dict.values() for size in sublist]
                # Один вызов к БД
                products_count = data_base.get_filtered_product_count(sizes=size_values, **clean_filters)
            else:
                products_count = data_base.get_filtered_product_count(**clean_filters)
            if products_count == 0:
                caption_parts.append(f"\n📊 <i><b>За вашим запитом нічого не знайдено</b></i>")
            else:
                caption_parts.append(f"\n<i><b>Знайдено:\n{products_count} мод. товару</b></i>\n\nНатисніть ▶️ {products_count} мод. щоб переглянути товари з урахуванням фільтрів")
            if len(selected_keys) == 1 and selected_keys[0] == "season":
                caption_parts.append("\n👵 <b>Пояснення:</b>\nВи обрали сезон. Додайте категорію або розмір для точнішого підбору!")
            elif len(selected_keys) == 1 and selected_keys[0] == "category":
                caption_parts.append("\n👵 <b>Пояснення:</b>\nВи обрали категорію. Додайте розмір або бренд для кращого результату!")
            elif len(selected_keys) == 0:
                caption_parts.append("\n👵 <b>Пояснення:</b>\nОбирайте фільтри поступово — це допоможе знайти саме те, що потрібно!")
            elif len(unselected_keys) == 0:
                caption_parts.append("\n👵 <b>Пояснення:</b>\nВи використали всі фільтри! Це найточніший підбір для вас.")
            else:
                caption_parts.append("\n👵 <b>Пояснення:</b>\nМожна додати ще фільтри для більш точного пошуку.")
            base_caption = "<blockquote>{}</blockquote>".format("\n\n".join(caption_parts))
        # --- ДОБАВЛЯЕМ ИНФОРМАЦИЮ О ВЫБРАННЫХ РАЗМЕРАХ ВНИЗУ ---
        sizes_dict = active_filters.get("sizes")
        if isinstance(sizes_dict, dict) and sizes_dict:
            # Словарь для перевода ключей в красивые названия
            size_category_labels = {
                "jacket": "куртка",
                "jersey": "трикотаж",
                "jeans": "джинси"
            }

            # Формируем строку, используя красивые названия
            # Метод .get(k, k) безопасен: если ключ не найден, он вернет сам ключ
            sizes_str = ", ".join(
                [f"<code>{size_category_labels.get(k, k)}:</code> {v}" for k, v in sizes_dict.items() if v]
            )

            if sizes_str:
                base_caption += f"\n\n<code>✅ Вибрані розміри:\n</code> {sizes_str}"

                # --- ОБНОВЛЕННЫЙ БЛОК: СЧЕТЧИК ТОВАРОВ ПО РАЗМЕРАМ И ДРУГИМ ФИЛЬТРАМ ---
                products_count_by_size = 0
                size_values = [size for sublist in sizes_dict.values() for size in sublist]
                
                # Собираем остальные активные фильтры
                other_filters = {k: v for k, v in active_filters.items() if v is not None and k not in ['sizes', 'size']}

                if size_values:
                    # Считаем товары, соответствующие любому из выбранных размеров И другим фильтрам
                    products_count_by_size = data_base.get_filtered_product_count(sizes=size_values, **other_filters)
                
                if products_count_by_size > 0:
                    base_caption += f"\n\n<code>Натисніть ▶️ {products_count_by_size} мод. щоб переглянути товари з урахуванням розмерів</code>"

        return base_caption

    @staticmethod
    def _get_display_value(filter_key: str, value: str, active_filters: Dict[str, Optional[str]]) -> str:
        """Получает красивое отображение значения фильтра"""
        try:
            if filter_key == "category":
                return get_category_label(value)
            elif filter_key == "subcategory":
                cat = active_filters.get("category")
                return get_subcategory_label(cat, value) if cat else value
            elif filter_key == "size":
                cat = active_filters.get("category")
                if cat == "куртки":
                    return JacketSizes(value).label
                elif cat == "джинси":
                    return JeansSizes(value).label
                elif cat == "трикотаж":
                    return JerseySizes(value).label
                else:
                    return value
            elif filter_key == "season":
                logger.debug(f"_get_display_value: season value='{value}'")
                try:
                    season_enum = Seasons(value)
                    logger.debug(f"_get_display_value: season enum found, label='{season_enum.label}'")
                    return season_enum.label
                except ValueError as e:
                    logger.error(f"_get_display_value: season value '{value}' not found in enum: {e}")
                    return value
            elif filter_key == "brand":
                return Brands(value).label
            else:
                return value
        except Exception as e:
            logger.error(f"_get_display_value: error for {filter_key}='{value}': {e}")
            return value

    @staticmethod
    async def create_simple_filters_keyboard(breadcrumbs: str,
                                       active_filters: Dict[str, Optional[str]],
                                       user_id: Optional[int] = None, state: Optional[FSMContext] = None) -> InlineKeyboardMarkup:
        """Создает простую клавиатуру фильтров - все фильтры на одном экране"""
        keyboard = []
        
        # Кодируем breadcrumbs для безопасной передачи в callback_data
        encoded_breadcrumbs = encode_breadcrumbs(breadcrumbs)

        # Создаем кнопки для каждого фильтра
        filter_buttons = [
            ("С е з о н", "season", Seasons),
            ("К а т е г о р і я", "category", Categories),
            ("П і д к а т е г о р і я", "subcategory", None),
            ("Р о з м і р и", "size", None),
            ("Б р е н д", "brand", Brands)
        ]


        for display_name, filter_key, enum_class in filter_buttons:
            # Пропускаем подкатегорию если категория не выбрана
            if filter_key == "subcategory" and not active_filters.get("category"):
                continue

            current_value = active_filters.get(filter_key)
            value_label = None  # Инициализируем как None
            is_complex_size = False  # Флаг для отслеживания сложного фильтра

            # --- НОВАЯ УЛУЧШЕННАЯ ЛОГИКА ---
            if filter_key == "size":
                sizes_dict = active_filters.get("sizes")
                # 1. Проверяем сложный фильтр размеров
                if isinstance(sizes_dict, dict) and any(sizes_dict.values()):
                    # "Выпрямляем" список списков размеров и применяем .upper()
                    valid_sizes = [s.upper() for sublist in sizes_dict.values() for s in sublist if s]
                    value_label = " ".join([f"✅ {s}" for s in valid_sizes])
                    is_complex_size = True
                # 2. Если сложного нет, проверяем простой фильтр
                elif current_value:
                    try:
                        cat = active_filters.get("category")
                        if cat == "куртки":
                            value_label = JacketSizes(current_value).label
                        elif cat == "джинси":
                            value_label = JeansSizes(current_value).label
                        elif cat == "трикотаж":
                            value_label = JerseySizes(current_value).label
                        else:
                            value_label = current_value
                    except ValueError:
                        value_label = current_value
            # Логика для всех остальных фильтров (остается как было)
            elif current_value:
                try:
                    if filter_key == "category":
                        value_label = get_category_label(current_value)
                    elif filter_key == "subcategory":
                        cat = active_filters.get("category")
                        value_label = get_subcategory_label(cat, current_value) if cat else current_value
                    elif filter_key == "season":
                        value_label = Seasons(current_value).label
                    elif filter_key == "brand":
                        value_label = Brands(current_value).label
                except ValueError:
                    value_label = current_value
            # --- КОНЕЦ НОВОЙ ЛОГИКИ ---

            # Формируем текст кнопки с индикатором выбора
            if value_label:
                if is_complex_size:
                    # Для сложного фильтра галочки уже встроены в value_label
                    text = f"{display_name}  :  {value_label}"
                else:
                    # Для всех остальных добавляем галочку
                    text = f"{display_name}  :  ✅  {value_label}"
            else:
                text = f"{display_name}  :  Не вибрано"

            keyboard.append(InlineKeyboardButton(
                text=text,
                callback_data=NavigationCallback(
                    action="edit_filter",
                    current_level=filter_key,
                    breadcrumbs=encoded_breadcrumbs
                ).pack()
            ))

        # Кнопки действий
        action_buttons = []

        # Кнопка применения фильтров
        has_filters = any(active_filters.get(key) for key in FilterManager.FILTER_KEYS)
        clean_filters = {k: v for k, v in active_filters.items() if v is not None and k != "sizes"}
        # Получаем реальное количество товаров по фильтрам
        products_count = 0
        sizes_dict = active_filters.get("sizes")
        if isinstance(sizes_dict, dict) and sizes_dict:
            # "Выпрямляем" список размеров
            size_values = [size for sublist in sizes_dict.values() for size in sublist]
            products_count = data_base.get_filtered_product_count(sizes=size_values, **clean_filters)
        else:
            products_count = data_base.get_filtered_product_count(**clean_filters)
        if products_count > 0 or not has_filters:
            if has_filters:
                catalog_button_text = f"▶️ {products_count} мод." if products_count > 0 else "▶️ "
            else:
                catalog_button_text = f"▶️ {products_count} мод." if products_count > 0 else "▶️ Каталог"
            action_buttons.append(InlineKeyboardButton(
                text=catalog_button_text,
                callback_data=NavigationCallback(
                    action="apply_filters",
                    current_level="",
                    breadcrumbs=encoded_breadcrumbs
                ).pack()
            ))

        # Кнопка сброса только если выбран хотя бы один фильтр
        # Проверяем как простые фильтры, так и сложный фильтр размеров ('sizes')
        has_simple_filters = any(active_filters.get(key) for key in FilterManager.FILTER_KEYS)
        sizes_dict = active_filters.get("sizes", {})
        has_complex_size_filters = isinstance(sizes_dict, dict) and any(sizes_dict.values())

        if has_simple_filters or has_complex_size_filters:
            action_buttons.append(InlineKeyboardButton(
                text="❌ Скинути",
                callback_data=NavigationCallback(
                    action="clear_filters",
                    current_level="",
                    breadcrumbs=encoded_breadcrumbs
                ).pack()
            ))

        # Кнопка закрытия в ряду с action_buttons
        close_btn = InlineKeyboardButton(
            text=btn['x'],
            callback_data=NavigationCallback(
                action="main",
                current_level="",
                breadcrumbs=encoded_breadcrumbs
            ).pack()
        )
        action_buttons = [close_btn] + action_buttons

        # Формируем финальную клавиатуру
        final_keyboard = []

        # Добавляем кнопки фильтров по одной в ряд
        for button in keyboard:
            final_keyboard.append([button])

        # Добавляем кнопки действий в один ряд (включая закрытие)
        if action_buttons:
            final_keyboard.append(action_buttons)

        # --- ДОБАВЛЯЕМ КНОПКУ "Корзина" (🛍) рядом с избранным и персональным ---
        cart_count = data_base.get_cart_count(user_id if user_id is not None else 0)
        cart_button = None
        if cart_count > 0:
            cart_button = InlineKeyboardButton(
                text=f"🛍 {cart_count} тов.",
                callback_data="cart_slider:filters"
            )

        # --- ДОБАВЛЯЕМ КНОПКУ "Мої збережені" (⭐️ Лайк) и персональную (🎯) ---
        favorite_button = None
        if user_id:
            fav_count = data_base.get_favorite_product_count(user_id)
            if fav_count > 0:
                favorite_button = InlineKeyboardButton(
                    text=f"❤️  {fav_count} мод.",
                    callback_data="favorites_slider:filters"
                )
        personal_row = None
        if user_id:
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
                except json.JSONDecodeError:
                    pass
            if has_sizes:
                total_count = 0
                if user_size_json:
                    try:
                        size_obj = json.loads(user_size_json)
                        for size_key in ["jacket", "jersey", "jeans"]:
                            size_value = size_obj.get(size_key)
                            if size_value:
                                try:
                                    if data_base.size_exists(size_value):
                                        count = data_base.get_filtered_product_count(size=size_value)
                                        total_count += count
                                except ValueError:
                                    pass
                    except json.JSONDecodeError:
                        pass
                button_text = "🎯  "
                if total_count > 0:
                    button_text += f"{total_count} мод."
                personal_row = [
                    InlineKeyboardButton(
                        text=button_text,
                        callback_data=NavigationCallback(
                            action="show_personal_slider",
                            current_level="",
                            breadcrumbs=encoded_breadcrumbs
                        ).pack()
                    )
                ]
                if favorite_button:
                    personal_row.append(favorite_button)
                if cart_button:
                    personal_row.append(cart_button)
            else:
                personal_row = []
                if favorite_button:
                    personal_row.append(favorite_button)
                if cart_button:
                    personal_row.append(cart_button)
        elif cart_button or favorite_button:
            personal_row = []
            if favorite_button:
                personal_row.append(favorite_button)
            if cart_button:
                personal_row.append(cart_button)
        # Теперь personal_row вставляем первой строкой клавиатуры
        if personal_row:
            final_keyboard = [personal_row] + final_keyboard

        return InlineKeyboardMarkup(inline_keyboard=final_keyboard)

    @staticmethod
    def create_filter_selection_keyboard(filter_type: str, breadcrumbs: str,
                                         active_filters: Dict[str, Optional[str]]) -> InlineKeyboardMarkup:
        """Создает клавиатуру для выбора конкретного фильтра"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        # Кодируем breadcrumbs для безопасной передачи в callback_data
        encoded_breadcrumbs = encode_breadcrumbs(breadcrumbs)
        
        # Создаем основную клавиатуру в зависимости от типа фильтра
        if filter_type == "category":
            main_keyboard = create_keyboard(Categories, breadcrumbs, "select_filter", add_back=False, add_close=False, active_filters=active_filters)
        elif filter_type == "subcategory":
            category = active_filters.get("category")
            if category == "куртки":
                main_keyboard = create_keyboard(JacketsCategory, breadcrumbs, "select_filter", add_back=False, add_close=False, active_filters=active_filters)
            elif category == "джинси":
                main_keyboard = create_keyboard(JeansCategory, breadcrumbs, "select_filter", add_back=False, add_close=False, active_filters=active_filters)
            elif category == "трикотаж":
                main_keyboard = create_keyboard(JerseyCategory, breadcrumbs, "select_filter", add_back=False, add_close=False, active_filters=active_filters)
            else:
                main_keyboard = create_keyboard(Categories, breadcrumbs, "select_filter", add_back=False, add_close=False, active_filters=active_filters)
        elif filter_type == "size":
            # --- НОВАЯ УМНАЯ ЛОГИКА ВЫБОРА КЛАВИАТУРЫ РАЗМЕРОВ ---
            category = active_filters.get("category")

            # 1. Если категория уже выбрана, показываем размеры для нее
            if category:
                if category == "куртки":
                    main_keyboard = create_keyboard(JacketSizes, breadcrumbs, "select_filter", add_back=False, add_close=False, adjust=(4,), active_filters=active_filters)
                elif category == "джинси":
                    main_keyboard = create_keyboard(JeansSizes, breadcrumbs, "select_filter", add_back=False, add_close=False, adjust=(4,), active_filters=active_filters)
                elif category == "трикотаж":
                    main_keyboard = create_keyboard(JerseySizes, breadcrumbs, "select_filter", add_back=False, add_close=False, adjust=(4,), active_filters=active_filters)
                else: # На случай появления новых категорий в будущем или если категория не соответствует
                    from keyboards.kb import create_size_filter_keyboard
                    selected_sizes = active_filters.get("sizes", {})
                    if not isinstance(selected_sizes, dict): selected_sizes = {}
                    main_keyboard = create_size_filter_keyboard(breadcrumbs, "select_filter", selected_sizes, adjust=(4,), active_filters=active_filters)

            # 2. Если категория не выбрана, пытаемся определить ее по другим фильтрам
            else:
                filters_for_check = {k: v for k, v in active_filters.items() if k != 'category' and v is not None}
                available_categories = data_base.get_unique_categories_for_filters(**filters_for_check)

                # 2.1. Если осталась только одна возможная категория, показываем ее размеры
                if len(available_categories) == 1:
                    category = available_categories[0]
                    # Временно добавляем категорию в фильтры для корректной работы create_keyboard
                    active_filters_for_kb = active_filters.copy()
                    active_filters_for_kb['category'] = category
                    if category == "куртки":
                        main_keyboard = create_keyboard(JacketSizes, breadcrumbs, "select_filter", add_back=False, add_close=False, adjust=(4,), active_filters=active_filters_for_kb)
                    elif category == "джинси":
                        main_keyboard = create_keyboard(JeansSizes, breadcrumbs, "select_filter", add_back=False, add_close=False, adjust=(4,), active_filters=active_filters_for_kb)
                    elif category == "трикотаж":
                        main_keyboard = create_keyboard(JerseySizes, breadcrumbs, "select_filter", add_back=False, add_close=False, adjust=(4,), active_filters=active_filters_for_kb)
                    else: # На случай появления новых категорий
                        from keyboards.kb import create_size_filter_keyboard
                        selected_sizes = active_filters.get("sizes", {})
                        if not isinstance(selected_sizes, dict): selected_sizes = {}
                        main_keyboard = create_size_filter_keyboard(breadcrumbs, "select_filter", selected_sizes, adjust=(4,), active_filters=active_filters)

                # 2.2. Если категорий несколько или 0, показываем сложную клавиатуру
                else:
                    from keyboards.kb import create_size_filter_keyboard
                    selected_sizes = active_filters.get("sizes", {})
                    if not isinstance(selected_sizes, dict):
                        selected_sizes = {}
                    main_keyboard = create_size_filter_keyboard(breadcrumbs, "select_filter", selected_sizes, adjust=(4,), active_filters=active_filters)
        elif filter_type == "season":
            # РАЗМЕЩЕНИЕ КНОПОК СЕЗОНОВ: 1-я кнопка в первом ряду, остальные по 2
            # Ручная настройка: измените adjust=(1, 2) на нужное размещение
            main_keyboard = create_keyboard(Seasons, breadcrumbs, "select_filter", add_back=False, add_close=False, adjust=(1, 2), active_filters=active_filters)
        elif filter_type == "brand":
            # РАЗМЕЩЕНИЕ КНОПОК БРЕНДОВ: по 3 в ряду
            # Ручная настройка: измените adjust=(3,) на нужное размещение
            main_keyboard = create_keyboard(Brands, breadcrumbs, "select_filter", add_back=False, add_close=False, adjust=(1,), active_filters=active_filters)
        else:
            main_keyboard = create_keyboard(Filters, breadcrumbs, "filters", add_back=False, add_close=False)

        # Добавляем кнопки действий
        action_buttons = []
        
        # Кнопка сброса текущего фильтра (только если он установлен)
        current_value = active_filters.get(filter_type)
        if current_value:
            filter_names = {
                "category": "Категорію",
                "subcategory": "Підкатегорію", 
                "size": "Розмір",
                "season": "Сезон",
                "brand": "Бренд"
            }
            filter_name = filter_names.get(filter_type, filter_type.title())
            action_buttons.append(InlineKeyboardButton(
                text=f"❌  {filter_name}",
                callback_data=NavigationCallback(
                    action="clear_single_filter",
                    current_level=filter_type,
                    breadcrumbs=encoded_breadcrumbs
                ).pack()
            ))

        # Кнопка "Назад"
        action_buttons.append(InlineKeyboardButton(
            text="← Назад",
            callback_data=NavigationCallback(
                action="back",
                current_level="",
                breadcrumbs=encoded_breadcrumbs
            ).pack()
        ))

        # --- НОВАЯ ЛОГИКА: Кнопка сброса размеров ---
        # Показываем кнопку, только если это фильтр размеров и есть выбранные размеры
        if filter_type == "size":
            sizes_dict = active_filters.get("sizes", {})
            if isinstance(sizes_dict, dict) and any(sizes_dict.values()):
                action_buttons.append(InlineKeyboardButton(
                    text="❌ Скинути",
                    callback_data=NavigationCallback(
                        action="clear_size_filters",
                        current_level=filter_type,
                        breadcrumbs=encoded_breadcrumbs
                    ).pack()
                ))
        # --- КОНЕЦ НОВОЙ ЛОГИКИ ---

        # --- ДОБАВЛЯЕМ КНОПКУ "ПОКАЗАТЬ ТОВАРЫ" ---
        # Логика аналогична create_simple_filters_keyboard
        has_filters = any(active_filters.get(key) for key in FilterManager.FILTER_KEYS)
        clean_filters = {k: v for k, v in active_filters.items() if v is not None and k != "sizes"}
        products_count = 0
        sizes_dict = active_filters.get("sizes")
        if isinstance(sizes_dict, dict) and sizes_dict:
            size_values = [size for sublist in sizes_dict.values() for size in sublist]
            products_count = data_base.get_filtered_product_count(sizes=size_values, **clean_filters)
        else:
            products_count = data_base.get_filtered_product_count(**clean_filters)

        if products_count > 0:
            catalog_button_text = f"▶️ {products_count} мод."
            action_buttons.insert(0, InlineKeyboardButton(
                text=catalog_button_text,
                callback_data=NavigationCallback(
                    action="apply_filters",
                    current_level="",
                    breadcrumbs=encoded_breadcrumbs
                ).pack()
            ))

        # Объединяем основную клавиатуру с кнопками действий
        final_keyboard = main_keyboard.inline_keyboard.copy()
        if action_buttons:
            final_keyboard.append(action_buttons)
        # Кнопка закрытия всегда последней строкой
        # final_keyboard.append([
        #     InlineKeyboardButton(
        #         text="╳ Закрити",
        #         callback_data=NavigationCallback(
        #             action="main",
        #             current_level="main",
        #             breadcrumbs=encoded_breadcrumbs
        #         ).pack()
        #     )
        # ])
        return InlineKeyboardMarkup(inline_keyboard=final_keyboard)

    @staticmethod
    def format_active_filters(active_filters: Dict[str, Optional[str]]) -> str:
        """Создает текстовое представление активных фильтров для отладки"""
        display_names = {
            "category": "Категорія",
            "subcategory": "Підкатегорія",
            "size": "Розмір",
            "season": "Сезон",
            "brand": "Бренд"
        }
        items = []
        for key, value in active_filters.items():
            if value:
                display_value = FilterManager._get_display_value(key, value, active_filters)
                items.append(f"{display_names.get(key, key.title())}: {display_value}")
        return " | ".join(items) if items else "Фільтри не вибрані"