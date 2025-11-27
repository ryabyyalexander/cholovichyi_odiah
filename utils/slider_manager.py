# utils/slider_manager.py

import asyncio
import random
from typing import List, Dict, Optional, Union

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio
from aiogram.fsm.context import FSMContext
from data_base.models import data_base
from utils import logger
from utils.message_manager import MessageManager
from utils.functions import get_euro_exchange_rate, get_usd_exchange_rate, get_cart_block_short, calculate_cashback
from keyboards.kb import get_slider_keyboard
from utils.category_utils import get_subcategory_label, get_category_label
from enums.sizes_enums import JacketSizes, JerseySizes, JeansSizes

DEFAULT_SLIDER_SPEED = 3
SHUFFLE_SLIDER = True


def format_media(raw_media: list) -> tuple[list, list]:
    """
    Форматирует сырые данные медиа в формат, подходящий для SliderManager.start_slider
    
    Args:
        raw_media: Список медиа из базы данных
        
    Returns:
        tuple: (media_list, product_ids) где media_list содержит словари с ключами path, media_type, caption
    """
    media_list = []
    product_ids = []
    
    for item in raw_media:
        if isinstance(item, dict):
            # Если уже в формате словаря
            media_list.append({
                "path": item["path"],
                "media_type": item.get("media_type", "photo"),
                "caption": item.get("caption", "")
            })
            product_ids.append(item.get("product_id", 0))
        elif isinstance(item, (list, tuple)) and len(item) >= 6:
            # [id, product_id, telegram_file_id, media_type, is_main, caption]
            media_list.append({
                "path": item[2],
                "media_type": item[3] if len(item) > 3 else "photo",
                "caption": item[5] if len(item) > 5 else ""
            })
            product_ids.append(item[1])
        elif isinstance(item, (list, tuple)) and len(item) >= 3:
            # [id, product_id, telegram_file_id]
            media_list.append({
                "path": item[2],
                "media_type": "photo",
                "caption": ""
            })
            product_ids.append(item[0])
    
    return media_list, product_ids


class SliderManager:
    def __init__(self, message_manager: MessageManager, state: FSMContext):
        self.mm = message_manager
        self.state = state
        self.chat_id = message_manager.chat_id
        self._current_task = None

    async def _stop_previous_slideshow(self):
        """Останавливает предыдущее слайд-шоу и отменяет задачу"""
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except (asyncio.CancelledError, Exception) as e:
                logger.debug(f"Slideshow task cancelled: {e}")

        # Останавливаем воспроизведение в состоянии
        await self.state.update_data(
            playing=False,
            expanded=False,
            cycle_count=0  # Добавляем сброс счетчика цикла
        )

    async def start_slider(self, media_list: List[Dict], product_ids: Optional[List[int]] = None, source: str = "main", user_id: Optional[int] = None, cart_items: Optional[list] = None, breadcrumbs: str = "") -> None:
        """Универсальный запуск слайдера для любого типа медиа."""
        data = await self.state.get_data()
        slider_autoplay = data.get('slider_autoplay', True)
        slider_speed = data.get('slider_speed', DEFAULT_SLIDER_SPEED)
        # Получаем cart_items из FSM, если есть
        cart_items = data.get('cart_items')
        
        # Отладочная информация для user_id
        logger.debug(f"start_slider: initial user_id={user_id}, chat_id={self.chat_id}")
        
        # Используем только явно переданный user_id или user_id из FSM
        if user_id is None:
            user_id = data.get('user_id')
        if not user_id:
            logger.warning("start_slider: user_id is not set, cannot start slider!")
            msg = await self.mm.send("Ошибка: не удалось определить пользователя для слайдера.")
            await asyncio.sleep(2)
            await self.mm.bot.delete_message(self.chat_id, msg.message_id)
            return
        user_id = int(user_id)
        logger.debug(f"start_slider: final user_id={user_id}")
        
        await self.state.update_data(
            playing=slider_autoplay,
            expanded=True,
            cycle_count=0,
            speed=slider_speed
        )
        await self._stop_previous_slideshow()

        if not media_list:
            msg = await self.mm.send("Нет медиа для отображения.")
            await asyncio.sleep(2)
            await self.mm.bot.delete_message(self.chat_id, msg.message_id)
            return

        # Перемешиваем медиа и product_ids, если SHUFFLE_SLIDER = True
        if SHUFFLE_SLIDER:
            combined = list(zip(media_list, product_ids)) if product_ids else [(m, 0) for m in media_list]
            random.shuffle(combined)
            if product_ids:
                media_list, product_ids = zip(*combined)
                product_ids = list(product_ids)
            else:
                media_list, _ = zip(*combined)
            media_list = list(media_list)

        # Форматируем media_list (теперь обязательно должен быть media_type)
        formatted_media = [
            {"path": item["path"], "caption": item.get("caption", ""), "media_type": item.get("media_type", "photo")}
            for item in media_list
            if "path" in item
        ]

        product_ids = product_ids or [0] * len(formatted_media)

        logger.debug(f"start_slider: product_ids={product_ids}, formatted_media length={len(formatted_media)}")

        # === СОХРАНЯЕМ ДАННЫЕ О ИЗБРАННОМ И КОРЗИНЕ ДЛЯ ВСЕХ ТОВАРОВ ===
        favorites_data = {}
        cart_data = {}
        
        if user_id:
            try:
                user_id = int(user_id)
                # Проверяем избранное и корзину для всех товаров
                for product_id in product_ids:
                    if product_id and product_id > 0:
                        favorites_data[product_id] = data_base.is_product_in_favorites(user_id, product_id)
                        cart_data[product_id] = data_base.is_product_in_cart(user_id, product_id)
                        logger.debug(f"start_slider: product_id={product_id}, is_favorite={favorites_data[product_id]}, is_in_cart={cart_data[product_id]}")
            except (ValueError, TypeError):
                logger.warning(f"start_slider: invalid user_id type: {type(user_id)}, value: {user_id}")
                user_id = None

        # Отправляем первое медиа
        first_media = formatted_media[0]
        first_product_id = product_ids[0]
        # Формируем caption с учетом корзины (всегда динамически)
        caption = await self.get_full_slider_caption(first_product_id, user_id, cart_items=cart_items, source=source, breadcrumbs=breadcrumbs, total_items=len(formatted_media), index=0)
        
        # После использования очищаем cart_items из FSM
        if cart_items is not None:
            await self.state.update_data(cart_items=None)
        
        # Получаем выбранный размер для первого товара
        size_value = data.get('selected_size') or data.get('size')
        # Получаем данные о избранном и корзине для первого товара
        is_favorite = data_base.is_product_in_favorites(user_id, first_product_id) if user_id and first_product_id and first_product_id > 0 else False
        is_in_cart = data_base.is_product_in_cart(user_id, first_product_id, size_value=size_value) if user_id and first_product_id and first_product_id > 0 else False
        
        logger.debug(f"start_slider: first product - is_favorite={is_favorite}, is_in_cart={is_in_cart}")
        
        # Логируем параметры для клавиатуры
        logger.debug(f"start_slider: keyboard params - user_id={user_id}, is_favorite={is_favorite}, product_id={first_product_id}, source={source}")
        
        # Получаем фильтры для любого слайдера (main, filters и др.)
        from utils.filter_manager import FilterManager
        active_filters = await FilterManager.get_active_filters(self.state)
        detailed_sizes = data_base.get_detailed_available_sizes(first_product_id) if first_product_id and first_product_id > 0 else {}
        msg = await self.mm.send_media_message(
            media_type=first_media["media_type"],
            file=first_media["path"],
            caption=caption,
            reply_markup=get_slider_keyboard(
                expanded=True,
                index=0,
                total=len(formatted_media),
                user_id=user_id,
                is_favorite=is_favorite,
                product_id=first_product_id,
                source=source,
                is_in_cart=is_in_cart,
                selected_size=None,
                selected_product_id=None,
                show_sizes_for_product=None,
                breadcrumbs=breadcrumbs,
                active_filters=active_filters,
                detailed_sizes=detailed_sizes
            )
        )
        # update_photo больше не нужен для первого слайда
        
        # Записываем просмотр первого товара с длительностью равной скорости слайдера
        if user_id and first_product_id and first_product_id > 0:
            data_base.add_product_view(
                user_id=user_id,
                product_id=first_product_id,
                view_type='slider',
                view_duration=slider_speed
            )
        await self.state.set_state("slider_viewing")
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
        logger.debug(f"start_slider: DEBUG - saved slider_source='{source}' to state")

    @staticmethod
    async def create_slider_caption(product_id: int, user_id: Optional[int] = None, breadcrumbs: str = "") -> str:
        """Создает капшен для слайдера на основе информации о продукте"""
        logger.debug(f"_create_slider_caption: product_id={product_id}, user_id={user_id}, breadcrumbs={breadcrumbs}")
        product = data_base.sql_get_product(product_id)
        if not product:
            logger.warning(f"_create_slider_caption: product not found for product_id={product_id}")
            return "Информация о товаре недоступна"

        logger.debug(f"_create_slider_caption: found product={product}")
        detailed_sizes = data_base.get_detailed_available_sizes(product_id)

        # Формируем строку с размерами
        sizes_text = "Доступні розміри:\n"
        if detailed_sizes:
            def format_size(size_value, details, is_letter=False):
                display_value = size_value.upper() if is_letter else size_value
                qty = details['quantity']
                is_reserved = details['is_reserved']

                if is_reserved:
                    return f"❓{display_value}"
                elif qty > 0:
                    return f"{display_value}" if qty == 1 else f"{display_value}({qty})"
                else:
                    return None

            jacket_sizes = [
                s for s in (format_size(size.value, detailed_sizes[size.value]) for size in JacketSizes if size.value in detailed_sizes) if s is not None
            ]
            jersey_sizes = [
                s for s in (format_size(size.value, detailed_sizes[size.value], is_letter=True) for size in JerseySizes if size.value in detailed_sizes) if s is not None
            ]
            jeans_sizes = [
                s for s in (format_size(size.value, detailed_sizes[size.value]) for size in JeansSizes if size.value in detailed_sizes) if s is not None
            ]

            sizes_parts = []
            if jacket_sizes: sizes_parts.append(", ".join(jacket_sizes))
            if jersey_sizes: sizes_parts.append(", ".join(jersey_sizes))
            if jeans_sizes: sizes_parts.append(", ".join(jeans_sizes))
            sizes_text += " | ".join(sizes_parts) if sizes_parts else "немає в наявності"
        else:
            sizes_text += "немає в наявності"

        # Рассчитываем цену со скидкой
        base_price = product['sale_price']
        discount_percentage = product['discount']
        price_after_discount = round(base_price - (base_price * discount_percentage / 100), 2)

        # --- Логика скидки лояльности ---
        loyalty_discount_percentage = 0
        loyalty_tier_applied = None
        price_after_loyalty = price_after_discount

        if user_id:
            user_level_data = data_base.sql_get_user(user_id, 'level')
            if user_level_data and user_level_data[0]:
                user_level = user_level_data[0].upper()
                loyalty_tiers_json = product.get('loyalty_tiers')
                if loyalty_tiers_json:
                    import json
                    from data_base.constants import LOYALTY_DISCOUNTS
                    try:
                        product_tiers = json.loads(loyalty_tiers_json)
                        available_discounts = {}
                        user_level_rank = list(LOYALTY_DISCOUNTS.keys()).index(user_level)
                        for tier in product_tiers:
                            if tier in LOYALTY_DISCOUNTS:
                                tier_rank = list(LOYALTY_DISCOUNTS.keys()).index(tier)
                                if tier_rank <= user_level_rank:
                                    available_discounts[tier] = LOYALTY_DISCOUNTS[tier]
                        
                        if available_discounts:
                            best_tier = max(available_discounts, key=available_discounts.get)
                            loyalty_discount_percentage = available_discounts[best_tier]
                            loyalty_tier_applied = best_tier
                            price_after_loyalty = round(price_after_discount - (price_after_discount * loyalty_discount_percentage / 100), 2)
                    except (json.JSONDecodeError, ValueError):
                        pass

        # --- Логика персональной скидки (кэшбэк) ---
        final_price = price_after_loyalty
        cashback_info = None
        if user_id:
            cashback_info = calculate_cashback(user_id, price_after_loyalty)
            if cashback_info and cashback_info.get("discount", 0) > 0:
                final_price = cashback_info["final_price"]

        # Получаем label для категории и подкатегории
        category_label = get_category_label(product['category'])
        subcategory_label = get_subcategory_label(product['category'], product['subcategory'])
        
        # Определяем иконку сезона
        season_icon = ""
        season_value = product.get('season', '').lower()
        if 'осінь' in season_value or 'зима' in season_value:
            season_icon = '❄️ '
        elif 'весна' in season_value or 'літо' in season_value:
            season_icon = '☀️ '

        # Определяем статус товара
        status_text = "" if product.get('is_active') else f"\n\n🔴 Неактивний"

        euro_rate = get_euro_exchange_rate()
        usd_rate = get_usd_exchange_rate()
        
        # Формируем строки с ценами
        price_lines = []
        if discount_percentage > 0:
            price_after_discount_uah = round(price_after_discount * euro_rate)
            price_lines.append(f"<code>Ціна </code><b>{base_price}€</b>")
            price_lines.append(f"<code>Знижка -{discount_percentage}%  {price_after_discount}€ • {price_after_discount_uah}грн.</code>")
        else:
            price_after_discount_uah = round(price_after_discount * euro_rate)
            price_lines.append(f"<code>Ціна {price_after_discount}€ • {price_after_discount_uah}грн.</code>")

        if loyalty_tier_applied:
            from data_base.constants import LOYALTY_ICONS
            price_after_loyalty_uah = round(price_after_loyalty * euro_rate)
            icon = LOYALTY_ICONS.get(loyalty_tier_applied, '')
            price_lines.append(f"<code>{icon} {loyalty_tier_applied.capitalize()} - {loyalty_discount_percentage}%  {price_after_loyalty}€ • {price_after_loyalty_uah}грн.</code>")

        price_section = '\n'.join(price_lines)

        return f"""<code>{season_icon}{product['season']}\n{category_label}/{subcategory_label}\n</code><b>{product['brand']}</b><code> • {product['country']}\nID {product_id} - {product['name']}</code>\n{product['short_description'] or ''}\n{price_section}\n<code>{sizes_text}{status_text}</code>"""

    async def get_full_slider_caption(self, product_id: int, user_id: Optional[int], cart_items: Optional[list] = None, show_cart_block: bool = True, source: str = "main", breadcrumbs: str = "", total_items: int = 0, index: int = 0) -> str:
        """Формирует caption для слайдера с учетом актуального состояния корзины. Если cart_items передан — использовать его, иначе брать корзину из базы."""
        # Добавляем заголовок слайдера
        slider_header = await self._get_slider_header(source, breadcrumbs, total_items, index)
        logger.debug(f"get_full_slider_caption: product_id={product_id}, source='{source}', breadcrumbs='{breadcrumbs}', total_items={total_items}, header='{slider_header}'")

        caption = await self.create_slider_caption(product_id, user_id, breadcrumbs)
        if not show_cart_block:
            return f"{slider_header}\n\n{caption}"
        if cart_items is not None:
            if not cart_items:
                cart_block = ""
            else:
                # Проверяем есть ли текущий товар в корзине
                is_current_product_in_cart = any(item.get("product_id") == product_id for item in cart_items)
                if is_current_product_in_cart:
                    # Получаем информацию о текущем товаре в корзине
                    current_size = None
                    current_qty = None
                    for item in cart_items:
                        if item.get("product_id") == product_id:
                            current_size = item.get("size_value")
                            current_qty = item.get("quantity", 1)
                            break
                    cart_block = get_cart_block_short(user_id, product_id, current_size, current_qty)
                else:
                    cart_block = ""
        else:
            # Получаем информацию о текущем товаре в корзине
            current_size = None
            current_qty = None
            if user_id and product_id:
                cart_items_for_product = data_base.get_cart(user_id)
                for item in cart_items_for_product:
                    if item.get("product_id") == product_id:
                        current_size = item.get("size_value")
                        current_qty = item.get("quantity", 1)
                        break
            cart_block = get_cart_block_short(user_id, product_id, current_size, current_qty) if user_id else ""
        if cart_block:
            caption = f"{slider_header}\n\n{caption}\n\n{cart_block}"
        else:
            caption = f"{slider_header}\n\n{caption}"
        return caption

    async def _get_slider_header(self, source: str, breadcrumbs: str = "", total_items: int = 0, index: int = 0) -> str:
        """Возвращает заголовок слайдера в зависимости от источника и breadcrumbs"""
        logger.debug(f"_get_slider_header: DEBUG - source='{source}', breadcrumbs='{breadcrumbs}', total_items={total_items}")

        # Проверяем наличие активных фильтров
        from utils.filter_manager import FilterManager
        from aiogram.fsm.context import FSMContext

        # Получаем состояние из self.state
        data = await self.state.get_data()
        active_filters = await FilterManager.get_active_filters(self.state)
        # Проверяем как простые фильтры, так и сложный фильтр размеров ('sizes')
        has_simple_filters = any(active_filters.get(key) for key in ["category", "subcategory", "size", "season", "brand"])
        sizes_dict = active_filters.get("sizes", {})
        has_complex_size_filters = isinstance(sizes_dict, dict) and any(sizes_dict.values())
        has_filters = has_simple_filters or has_complex_size_filters

        logger.debug(f"_get_slider_header: DEBUG - has_filters={has_filters}, active_filters={active_filters}")

        # Определяем заголовок на основе source и наличия фильтров
        if source == "main":
            if has_filters:
                header = f"Знайшлось ✅ {total_items} мод."
            else:
                header = f"Каталог ✅ {total_items} мод."
        elif source == "filters":
            if has_filters:
                header = f"Знайшлось ✅ {total_items} мод."
            else:
                header = f"Каталог ✅ {total_items} мод."
        elif source == "favorites":
            header = f"❤️ Обране: {total_items} мод."
        elif source == "sizes":
            header = f"🎯 Мої розміри: {total_items} мод."
        elif source == "cart":
            header = f"🛍 Кошик: {total_items} прод."
            if total_items > 1:
                item_number_text = {
                    0: "Перший товар у кошику.",
                    1: "Другий товар у кошику.",
                    2: "Третій товар у кошику.",
                    3: "Четвертий товар у кошику.",
                    4: "П'ятий товар у кошику.",
                    5: "Шостий товар у кошику.",
                    6: "Сьомий товар у кошику.",
                    7: "Восьмий товар у кошику.",
                    8: "Дев'ятий товар у кошику.",
                    9: "Десятий товар у кошику."
                }
                item_text = item_number_text.get(index)
                if item_text:
                    header += f"\n{item_text}"
        elif source == "product_gallery":
            header = f"Є ✅ {total_items} фото товара"
        elif source == "archive":
            header = f"🗄 Архів: {total_items} мод."
        else:
            # Fallback для неизвестных источников
            if has_filters:
                header = f"Знайшлось ✅ {total_items} мод."
            else:
                header = f"Каталог ✅ {total_items} мод."

        # Добавляем реальные breadcrumbs с стрелкой: откуда пришел → где сейчас
        if breadcrumbs and breadcrumbs != "":
            if breadcrumbs == "filters":
                from_icon = "🔍"
            elif breadcrumbs == "profile":
                from_icon = "👤"
            else:
                from_icon = "✨"
            header = f"<code>{from_icon} {header}</code>"

        logger.debug(f"_get_slider_header: source='{source}', breadcrumbs='{breadcrumbs}', total_items={total_items}, header='{header}'")
        return header

    async def update_photo(
            self,
            index: int,
            paused: bool = False,
            expanded: bool = True,
            user_id: Optional[int] = None
    ) -> None:
        """Обновляет медиа в слайдере (универсально)"""
        data = await self.state.get_data()
        media_list = data.get("media_list", [])
        product_ids = data.get("product_ids", [])
        slider_speed = data.get('speed', DEFAULT_SLIDER_SPEED)
        # Получаем данные о избранном и корзине из FSM
        favorites_data = data.get("favorites_data", {})
        cart_data = data.get("cart_data", {})
        
        # Получаем user_id из состояния, если не передан
        if user_id is None:
            user_id = data.get('user_id')
            # Если user_id все еще None, используем chat_id как fallback для личных чатов
            if user_id is None and self.chat_id > 0:
                user_id = self.chat_id
        
        # Убеждаемся, что user_id является числом
        if user_id is not None:
            try:
                user_id = int(user_id)
            except (ValueError, TypeError):
                logger.warning(f"update_photo: invalid user_id type: {type(user_id)}, value: {user_id}")
                user_id = None
        if not media_list or index >= len(media_list):
            return
        media_info = media_list[index]
        product_id = product_ids[index]
        logger.debug(f"update_photo: index={index}, product_id={product_id}")
        
        # Записываем просмотр товара при смене слайда с длительностью равной скорости слайдера
        if user_id and product_id and product_id > 0:
            data_base.add_product_view(
                user_id=user_id,
                product_id=product_id,
                view_type='slider',
                view_duration=slider_speed
            )
        
        # Получаем источник и breadcrumbs из состояния
        slider_source = data.get("slider_source", "main")
        slider_breadcrumbs = data.get("slider_breadcrumbs", "")
        logger.debug(f"update_photo: DEBUG - slider_source from state='{slider_source}', slider_breadcrumbs='{slider_breadcrumbs}'")
        
        # Получаем фильтры для любого слайдера (main, filters и др.)
        from utils.filter_manager import FilterManager
        active_filters = await FilterManager.get_active_filters(self.state)
        # Показываем корзину только если клавиатура открыта (expanded)
        if expanded:
            cart_items = data_base.get_cart(user_id) if user_id else None
        else:
            cart_items = None
        caption = await self.get_full_slider_caption(product_id, user_id, cart_items=cart_items, show_cart_block=expanded, source=slider_source, breadcrumbs=slider_breadcrumbs, total_items=len(media_list), index=index)
        media_type = media_info.get("media_type", "photo")
        path = media_info["path"]
        # Выбираем нужный InputMedia*
        if media_type == "photo":
            input_media = InputMediaPhoto(media=path, caption=caption)
        elif media_type == "video":
            input_media = InputMediaVideo(media=path, caption=caption)
        elif media_type == "document":
            input_media = InputMediaDocument(media=path, caption=caption)
        elif media_type == "audio":
            input_media = InputMediaAudio(media=path, caption=caption)
        else:
            input_media = InputMediaPhoto(media=path, caption=caption)  # fallback
        
        # Получаем выбранный размер для текущего товара
        selected_size = data.get('selected_size')
        selected_product_id = data.get('selected_product_id')
        size_value = data.get('size')
        # Получаем данные о избранном и корзине из FSM
        is_favorite = data_base.is_product_in_favorites(user_id, product_id) if user_id and product_id and product_id > 0 else False
        is_in_cart = data_base.is_product_in_cart(user_id, product_id, size_value=size_value) if user_id and product_id and product_id > 0 else False
        detailed_sizes = data_base.get_detailed_available_sizes(product_id) if product_id and product_id > 0 else {}
        
        # Сбрасываем состояние выбора размеров при переходе на новый товар, если он не в корзине
        show_sizes_for_product = data.get('show_sizes_for_product')
        if show_sizes_for_product and show_sizes_for_product != product_id:
            # Если показывались размеры для другого товара, сбрасываем состояние
            await self.state.update_data(
                show_sizes_for_product=None,
                selected_size=None,
                selected_product_id=None
            )
            show_sizes_for_product = None
            selected_size = None
            selected_product_id = None
            logger.debug(f"update_photo: reset size selection state for new product {product_id}")
        
        # Если данных нет в FSM, проверяем в базе и обновляем FSM
        # if product_id and product_id > 0 and user_id:
        #     if product_id not in favorites_data:
        #         is_favorite = data_base.is_product_in_favorites(user_id, product_id)
        #         favorites_data[product_id] = is_favorite
        #         await self.state.update_data(favorites_data=favorites_data)
        #         logger.debug(f"update_photo: updated favorites_data for product_id={product_id}, is_favorite={is_favorite}")
        #     if product_id not in cart_data:
        #         is_in_cart = data_base.is_product_in_cart(user_id, product_id)
        #         cart_data[product_id] = is_in_cart
        #         await self.state.update_data(cart_data=cart_data)
        #         logger.debug(f"update_photo: updated cart_data for product_id={product_id}, is_in_cart={is_in_cart}")
        
        logger.debug(f"update_photo: final is_favorite={is_favorite}, is_in_cart={is_in_cart}")
        
        # Логируем параметры для клавиатуры
        logger.debug(f"update_photo: keyboard params - user_id={user_id}, is_favorite={is_favorite}, product_id={product_id}, source={slider_source}")
        
        try:
            await self.mm.edit_media(
                media=input_media,
                reply_markup=get_slider_keyboard(
                    paused, expanded, index, len(media_list), user_id, is_favorite=is_favorite, product_id=product_id, source=slider_source, is_in_cart=is_in_cart,
                    selected_size=selected_size, selected_product_id=selected_product_id, show_sizes_for_product=show_sizes_for_product, breadcrumbs=slider_breadcrumbs,
                    active_filters=active_filters,
                    detailed_sizes=detailed_sizes
                )
            )
        except TelegramBadRequest:
            pass

    async def autoplay_slideshow(self) -> None:
        """Автоматическое проигрывание слайдера"""
        try:
            data = await self.state.get_data()
            slider_speed = data.get('slider_speed', DEFAULT_SLIDER_SPEED)
            await asyncio.sleep(slider_speed)
            while True:
                data = await self.state.get_data()
                if not data.get("playing", False):
                    logger.debug("Autoplay stopped: playing=False")
                    break

                media_list = data.get("media_list", [])
                if not media_list:
                    logger.debug("Autoplay stopped: no media_list")
                    break

                current_index = data["index"]
                cycle_count = data.get("cycle_count", 0)
                user_id = data.get("user_id", None)

                next_index = (current_index + 1) % len(media_list)
                
                logger.debug(f"Autoplay: current_index={current_index}, next_index={next_index}, cycle_count={cycle_count}")

                # Если достигли конца списка (next_index == 0 означает, что мы перешли на первый слайд)
                if next_index == 0:
                    # Достигли конца списка - переходим на первый слайд и ставим на паузу
                    logger.debug("Reached end of slideshow, going to first slide and pausing")
                    await self.state.update_data(
                        index=0,  # Переходим на первый слайд
                        playing=False,
                        cycle_count=0,
                        expanded=True  # Открываем клавиатуру
                    )
                    await self.update_photo(
                        0,  # Первый слайд
                        paused=True,
                        expanded=True,  # Открытая клавиатура
                        user_id=user_id
                    )
                    break
                else:
                    await self.state.update_data(
                        index=next_index,
                        cycle_count=cycle_count + 1
                    )
                    await self.update_photo(
                        next_index,
                        paused=False,
                        expanded=False,  # Закрытая клавиатура во время автопроигрывания
                        user_id=user_id
                    )

                await asyncio.sleep(slider_speed)
        except asyncio.CancelledError:
            logger.debug("Slideshow task was cancelled")
        except Exception as e:
            logger.error(f"Error in slideshow task: {e}")