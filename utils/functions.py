import asyncio
from typing import Optional
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from data_base.models import data_base
from utils import logger
from utils.lexicon import caption_intro
from utils.loader import bot
from utils.filter_manager import FilterManager

from datetime import datetime
import time

import requests
import json

from enums.categories_enum import Categories

# Кэш для курсов валют
_euro_rate_cache = {"rate": None, "timestamp": 0}
_usd_rate_cache = {"rate": None, "timestamp": 0}
_CACHE_DURATION = 300  # 5 минут


async def safe_delete_message(message: Message, delay: int = 0) -> None:
    """Асинхронно удаляет сообщение с логированием ошибок."""
    if delay > 0:
        await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    except TelegramBadRequest as e:
        if "message to delete not found" not in str(e).lower():
            logger.warning(f"Ошибка удаления сообщения: {e}")
    except Exception as e:
        logger.error(f"Неизвестная ошибка при удалении сообщения: {e}")

# Словари для названий месяцев и дней недели
months = {
    1: "січня", 2: "лютого", 3: "березня", 4: "квітня",
    5: "травня", 6: "червня", 7: "липня", 8: "серпня",
    9: "вересня", 10: "жовтня", 11: "листопада", 12: "грудня"
}

days_of_week = {
    0: "понеділок", 1: "вівторок", 2: "середа",
    3: "четвер", 4: "п'ятниця", 5: "субота", 6: "неділя"
}


# Получение текущей даты


def data_time():
    now = datetime.now()
    # Форматирование даты
    day = now.day
    month = months[now.month]
    day_of_week = days_of_week[now.weekday()]

    return f"{day} {month}, {day_of_week}"


def get_euro_exchange_rate():
    current_time = time.time()
    
    # Проверяем кэш
    if (_euro_rate_cache["rate"] is not None and 
        current_time - _euro_rate_cache["timestamp"] < _CACHE_DURATION):
        return _euro_rate_cache["rate"]
    
    try:
        url = "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?valcode=EUR&json"
        response = requests.get(url, timeout=5)  # Добавляем timeout

        if response.status_code != 200:
            # Если API недоступен, возвращаем кэшированное значение или дефолтное
            if _euro_rate_cache["rate"] is not None:
                return _euro_rate_cache["rate"]
            return 40.0  # Дефолтное значение

        data = response.json()

        if not data or 'rate' not in data[0]:
            # Если данные некорректные, возвращаем кэшированное значение или дефолтное
            if _euro_rate_cache["rate"] is not None:
                return _euro_rate_cache["rate"]
            return 40.0  # Дефолтное значение

        rate = data[0]['rate']
        
        # Обновляем кэш
        _euro_rate_cache["rate"] = rate
        _euro_rate_cache["timestamp"] = current_time
        
        return rate
        
    except Exception as e:
        # При любой ошибке возвращаем кэшированное значение или дефолтное
        if _euro_rate_cache["rate"] is not None:
            return _euro_rate_cache["rate"]
        return 40.0  # Дефолтное значение


def get_usd_exchange_rate():
    current_time = time.time()

    # Проверяем кэш
    if (_usd_rate_cache["rate"] is not None and
            current_time - _usd_rate_cache["timestamp"] < _CACHE_DURATION):
        return _usd_rate_cache["rate"]

    try:
        url = "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?valcode=USD&json"
        response = requests.get(url, timeout=5)

        if response.status_code != 200:
            if _usd_rate_cache["rate"] is not None:
                return _usd_rate_cache["rate"]
            return 38.0

        data = response.json()

        if not data or 'rate' not in data[0]:
            if _usd_rate_cache["rate"] is not None:
                return _usd_rate_cache["rate"]
            return 38.0

        rate = data[0]['rate']

        # Обновляем кэш
        _usd_rate_cache["rate"] = rate
        _usd_rate_cache["timestamp"] = current_time

        return rate

    except Exception as e:
        if _usd_rate_cache["rate"] is not None:
            return _usd_rate_cache["rate"]
        return 38.0


async def start_info(state: FSMContext = None, user_id=None):
    from data_base.models import data_base
    from enums.categories_enum import Categories
    from utils.category_utils import get_category_label, get_subcategory_label
    from enums.sizes_enums import JacketSizes, JerseySizes, JeansSizes
    from enums.seasons_enum import Seasons
    from enums.brands_enum import Brands

    # --- БЛОК 2: ФІЛЬТРИ (проверяем сначала) ---
    filters = None
    if state is not None:
        filters = await FilterManager.get_active_filters(state)
    elif user_id:
        filters = data_base.get_user_filters(user_id)

    # --- БЛОК 1: БАЗА (показываем всегда) ---
    analytics = data_base.debug_database_content()
    has_active_products = analytics and analytics.get('total_active_products', 0) > 0

    # Определяем, есть ли активные фильтры
    has_active_filters = filters and any(filters.values())

    # --- Подсчет количества товаров ---
    found_count = 0
    if has_active_filters:
        # Новый, корректный подсчет
        clean_filters = {k: v for k, v in filters.items() if v is not None and k != 'sizes'}
        sizes_dict = filters.get('sizes', {})
        
        # "Выпрямляем" список размеров
        sizes_list = [size for sublist in sizes_dict.values() for size in sublist] if isinstance(sizes_dict, dict) else []
        
        # Если есть размеры, передаем их в `sizes`
        if sizes_list:
            found_count = data_base.get_filtered_product_count(**clean_filters, sizes=sizes_list)
        else: # Иначе, если есть старый ключ `size`
            found_count = data_base.get_filtered_product_count(**clean_filters)
    else:
        # Если фильтров нет, считаем все товары
        total_count = sum(analytics['category_counts'].values()) if analytics.get('category_counts') else 0
        found_count = total_count

    # --- Формирование блоков ---
    if not has_active_filters:
        base_lines = [f"Натисніть кнопку ▶️ {found_count} мод.\nщоб переглянути Каталог"]
        if not analytics.get('category_counts'):
            base_lines.append('Товарів у базі немає.')
        else:
            for cat in Categories:
                count = analytics['category_counts'].get(cat.value, 0)
                base_lines.append(f"• {cat.label}: {count} мод.")
        base_block = "\n".join(base_lines)
    else:
        base_block = f"<code>Натисніть ▶️ {found_count} мод. щоб переглянути товари з урахуванням фільтрів</code>"

    # --- Формирование блока с описанием фильтров ---
    filter_lines = []
    if has_active_filters:
        # Категория и подкатегория
        if cat_val := filters.get("category"):
            filter_lines.append(f"• Категорія:   {get_category_label(cat_val)}")
            if subcat_val := filters.get("subcategory"):
                filter_lines.append(f"• Підкатегорія:   {get_subcategory_label(cat_val, subcat_val)}")
        
        # Размеры (из словаря)
        if sizes_dict := filters.get("sizes"):
            if isinstance(sizes_dict, dict) and any(sizes_dict.values()):
                size_line_parts = []
                if jacket_size := sizes_dict.get('jacket'):
                    size_line_parts.append(f"куртки: {jacket_size}")
                if jersey_size := sizes_dict.get('jersey'):
                    size_line_parts.append(f"трикотаж: {jersey_size}")
                if jeans_size := sizes_dict.get('jeans'):
                    size_line_parts.append(f"джинси: {jeans_size}")
                if size_line_parts:
                    filter_lines.append(f"• Розміри:   {', '.join(size_line_parts)}")

        # Сезон
        if season_val := filters.get("season"):
            try:
                filter_lines.append(f"• Сезон:   {Seasons(season_val).label}")
            except ValueError:
                filter_lines.append(f"• Сезон:   {season_val}")
        
        # Бренд
        if brand_val := filters.get("brand"):
            try:
                filter_lines.append(f"• Бренд:   {Brands(brand_val).label}")
            except ValueError:
                filter_lines.append(f"• Бренд:   {brand_val}")

        filters_block = "🔎 Ваші фільтри\n" + "\n".join(filter_lines)
        filters_block += f"\n\n📊 <i>Знайдено {found_count} мод.</i>"
    else:
        filters_block = "🔎 Фільтри не вибрані" if has_active_products else ""

    # --- БЛОК 3: КОРЗИНА ---
    if user_id:
        cart_block = get_cart_block(user_id)
    else:
        cart_block = """<blockquote>\n🛍  Кошик: порожній\n    </blockquote>"""
    
    # --- Итог ---
    return f'<code>{base_block}</code>', cart_block, f'<code>{filters_block}</code>'

async def get_caption(state: FSMContext, k=0):
    data = await state.get_data()
    user_id = data.get('user_id')
    base_block, filters_block, cart_block = await start_info(state, user_id)
    formatted_date = data_time()
    euro_rate = get_euro_exchange_rate()
    captions = caption_intro.split('\n')[1:]
    if not captions:
        current_caption = ""
    else:
        if k < 0 or k >= len(captions):
            k = 0
        current_caption = captions[k]

    # --- Новый блок: статистика по размерам ---
    size_stats_block = ""
    if user_id:  # Только если есть user_id
        user = data_base.sql_get_user(user_id, 'size')
        size_json = user[0] if user and user[0] else None
        jacket_size = jersey_size = jeans_size = None
        if size_json:
            try:
                size_obj = json.loads(size_json)
                jacket_size = size_obj.get('jacket')
                jersey_size = size_obj.get('jersey')
                jeans_size = size_obj.get('jeans')
            except Exception:
                pass
        size_lines = []
        count_jackets = count_jersey = count_jeans = 0
        if jacket_size:
            count_jackets = data_base.get_filtered_product_count(category=Categories.JACKETS.value, size=jacket_size)
            size_lines.append(f"Куртки — {jacket_size} | {count_jackets} мод.")
        if jersey_size:
            count_jersey = data_base.get_filtered_product_count(category=Categories.JERSEY.value, size=jersey_size)
            size_lines.append(f"Трикотаж — {jersey_size} | {count_jersey} мод.")
        if jeans_size:
            count_jeans = data_base.get_filtered_product_count(category=Categories.JEANS.value, size=jeans_size)
            size_lines.append(f"Джинсы — {jeans_size} | {count_jeans} мод.")
        if size_lines:
            total_count = count_jackets + count_jersey + count_jeans
            size_stats_block = f"<code>🎯 {total_count} мод. Ваші розміри</code>\n<code>" + "\n".join(size_lines) + "</code>"
        else:
            size_stats_block = ""
    
    # Формируем результат динамически, без лишних переводов строки
    blocks = [formatted_date]
    if base_block.strip():
        blocks.append(base_block)
    if size_stats_block.strip():
        blocks.append(size_stats_block)
    if filters_block.strip():
        blocks.append(filters_block)
    if cart_block.strip():
        blocks.append(cart_block)
    if current_caption.strip():
        blocks.append(current_caption)
    blocks.append(f"<code>1 euro - {round(euro_rate/get_usd_exchange_rate(), 2)} USD - {round(euro_rate, 2)} грн.</code>")
    result = "\n\n".join(blocks)
    return result

def calculate_final_item_price(product: dict, user_id: Optional[int]) -> float:
    """Рассчитывает финальную цену товара с учетом всех скидок (базовая + лояльность)."""
    if not product:
        return 0.0

    # 1. Применяем обычную скидку товара
    base_price = product.get('sale_price', 0)
    discount_percentage = product.get('discount', 0)
    price_after_discount = round(base_price - (base_price * discount_percentage / 100), 2)

    # 2. Применяем скидку лояльности
    final_price = price_after_discount
    if user_id:
        user_level_data = data_base.sql_get_user(user_id, 'level')
        user_level = user_level_data[0].upper() if user_level_data and user_level_data[0] else None
        if user_level:
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
                        final_price = round(price_after_discount - (price_after_discount * loyalty_discount_percentage / 100), 2)
                except (json.JSONDecodeError, ValueError):
                    pass # Ошибка в JSON, скидка не применяется
    
    return final_price


def get_cart_block(user_id: int) -> str:
    """
    Возвращает текстовый блок с содержимым корзины пользователя (подробный формат для главной).
    """
    from data_base.models import data_base
    cart_items = data_base.get_cart(user_id)
    if not cart_items:
        # Рассчитываем скидку для пустой корзины (сумма = 0)
        discount_info = calculate_cashback(user_id, 0)
        return f"""<blockquote>
<code>🛍  Кошик: порожній
Накопичувальна знижка</code>  <b>{discount_info['total_percentage']}%</b>

</blockquote>"""
    
    # Подсчитываем общее количество товаров и сумму
    total_count = sum(item.get("quantity", 1) for item in cart_items)
    total = 0
    for item in cart_items:
        # Получаем полный объект продукта, чтобы передать в функцию расчета
        product = data_base.sql_get_product(item['product_id'])
        qty = item.get("quantity", 1)
        final_price = calculate_final_item_price(product, user_id)
        total += final_price * qty
    
    total_rounded = round(total, 2)
    euro_rate = get_euro_exchange_rate()
    total_uah = total_rounded * euro_rate
    
    # Рассчитываем скидку пользователя (если есть)
    discount_info = calculate_cashback(user_id, total_rounded)
    discount_uah = discount_info['discount'] * euro_rate
    final_to_pay_eur = round(total_rounded - discount_info['discount'], 2)
    final_to_pay_uah = round(final_to_pay_eur * euro_rate, 0)
    
    # Формируем заголовок с количеством товаров
    text = f"<code>🛍  {total_count} тов. Ваш кошик:\n\n"
    
    # Добавляем детали товаров
    for i, item in enumerate(cart_items, 1):
        product = data_base.sql_get_product(item['product_id'])
        if not product:
            continue

        name = product.get("name") or f"Товар {item.get('product_id')}"
        category = product.get("category", "")
        subcategory = product.get("subcategory", "")
        product_id = product.get("id")
        qty = item.get("quantity")
        size_value = item.get("size_value")

        # Цена с учетом всех скидок
        final_price_per_item = calculate_final_item_price(product, user_id)
        price_str = f"{final_price_per_item} €"
        # Формируем строку с категорией и подкатегорией
        category_info = ""
        if category and subcategory:
            category_info = f"{category}/{subcategory}"
        elif category:
            category_info = category
        elif subcategory:
            category_info = subcategory
        
        # Формируем строку товара с размером
        item_line = f"{i} </code>/ID_{product_id}<code> {category_info}"
        if size_value:
            item_line += f"\n{size_value} розм. {qty} шт. x {price_str}"
        else:
            item_line += f" {qty} шт. x {price_str}"
        text += item_line + "\n\n"
    
    text += f"\nСума: {total_rounded} € ({round(total_uah, 0)} грн) "
    text += f"\nНакопичувальна знижка </code><b>{discount_info['total_percentage']}%</b><code> - {round(discount_uah, 0)} грн"
    text += f"\n\nДо оплати: {final_to_pay_eur} € ({final_to_pay_uah} грн - <b>{round(final_to_pay_uah/get_usd_exchange_rate(), 0)}$</b>)</code>"
    return f"""<blockquote> 
{text}

</blockquote>"""


def get_cart_block_profile(user_id: int) -> str:
    """
    Возвращает текстовый блок с содержимым корзины пользователя (компактный формат для профиля).
    """
    from data_base.models import data_base
    cart_items = data_base.get_cart(user_id)
    if not cart_items:
        # Рассчитываем скидку для пустой корзины (сумма = 0)
        discount_info = calculate_cashback(user_id, 0)
        return f"""<blockquote>\n<code>🛍  Кошик: порожній\nНакопичувальна знижка</code>  <b>{discount_info['total_percentage']}%</b>\n\n</blockquote>"""
    
    # Подсчитываем общее количество товаров и сумму
    total_count = sum(item.get("quantity", 1) for item in cart_items)
    total = 0
    for item in cart_items:
        # Получаем полный объект продукта, чтобы передать в функцию расчета
        product = data_base.sql_get_product(item['product_id'])
        qty = item.get("quantity", 1)
        final_price = calculate_final_item_price(product, user_id)
        total += final_price * qty
    
    total_rounded = round(total, 2)
    euro_rate = get_euro_exchange_rate()
    total_uah = total_rounded * euro_rate
    
    # Рассчитываем скидку пользователя (если есть)
    discount_info = calculate_cashback(user_id, total_rounded)
    discount_uah = discount_info['discount'] * euro_rate
    final_to_pay_eur = round(total_rounded - discount_info['discount'], 2)
    final_to_pay_uah = round(final_to_pay_eur * euro_rate, 0)
    
    # Формируем компактный заголовок с количеством товаров
    text = f"<code>🛍  Ваш кошик:\n"
    text += f"{total_count} прод. | Сума: {total_rounded} € ({round(total_uah, 0)} грн)\n"
    text += f"Накопичувальна знижка </code><b>{discount_info['total_percentage']}%</b><code> - {round(discount_uah, 0)} грн\n"
    text += f"До оплати: {final_to_pay_eur} € ({final_to_pay_uah} грн)</code>"
    return f"""<blockquote> \n{text}\n\n</blockquote>"""

def get_cart_block_short(user_id: Optional[int], product_id: Optional[int] = None, current_size: Optional[str] = None, current_qty: Optional[int] = None) -> str:
    """
    Возвращает компактный блок корзины для слайдера.
    Показывает цену за конкретный товар (с учетом его скидки), который сейчас просматривается.
    """
    from data_base.models import data_base
    if user_id is None:
        return ""
    cart_items = data_base.get_cart(user_id)
    if not cart_items:
        return ""

    # Если product_id не передан, нет смысла что-то показывать в этом блоке
    if product_id is None:
        return ""

    # Находим конкретный товар в корзине по ID и размеру
    item_in_cart = None
    for item in cart_items:
        # У товара может не быть размера, поэтому проверяем и этот случай
        item_size = item.get("size_value")
        if item.get("product_id") == product_id and (item_size == current_size or (item_size is None and current_size is None)):
            item_in_cart = item
            break
    
    # Если товар с таким размером не найден в корзине, ничего не показываем
    if not item_in_cart:
        return ""

    # Рассчитываем цену для этого конкретного товара с учетом всех скидок
    product = data_base.sql_get_product(product_id)
    final_price_per_item = calculate_final_item_price(product, user_id)
    quantity = item_in_cart.get("quantity", 1)
    
    total_item_price_eur = round(final_price_per_item * quantity, 2)

    euro_rate = get_euro_exchange_rate()
    total_item_price_uah = int(round(total_item_price_eur * euro_rate, 0))

    # Формируем строку с информацией о текущем товаре
    size_from_cart = item_in_cart.get("size_value")
    qty_from_cart = item_in_cart.get("quantity")

    current_item_info = ""
    if size_from_cart and qty_from_cart:
        current_item_info = f"Товар в кошику: розм. {size_from_cart}, {qty_from_cart} шт.\n"
    elif qty_from_cart:
        current_item_info = f"Товар в кошику: {qty_from_cart} шт.\n"
    else:
        # Fallback, если в корзине нет инфо о кол-ве
        current_item_info = "Товар в кошику\n"

    return "<blockquote>\n<code>{current_item_info}Ціна за товар: {total_item_price_eur} € ({total_item_price_uah} грн)</code>\n</blockquote>".format(
        current_item_info=current_item_info,
        total_item_price_eur=total_item_price_eur,
        total_item_price_uah=total_item_price_uah
    )


def calculate_cashback(user_id: int, purchase_amount: float) -> dict:
    """
    Рассчитывает скидку на основе баллов пользователя.
    
    Args:
        user_id: ID пользователя
        purchase_amount: Сумма покупки в евро
        
    Returns:
        dict с информацией о скидке
    """
    from data_base.models import data_base
    from utils.lexicon import DISCOUNT_SETTINGS
    
    # Получаем только нужные поля
    user = data_base.sql_get_user(user_id, 'restart_count', 'total_spent')
    if not user:
        return {"discount": 0, "total_percentage": 0, "final_price": purchase_amount}
    
    # Безопасно приводим к int
    activity_points = int(user[0] or 0)
    total_spent = int(user[1] or 0)
    
    # Получаем реферальные баллы из истории
    referral_points = data_base.get_user_referral_points(user_id)
    
    # Расчет скидки с использованием констант из lexicon
    purchase_percentage = min((total_spent / DISCOUNT_SETTINGS['PURCHASE_BASE_AMOUNT']) * DISCOUNT_SETTINGS['PURCHASE_PERCENTAGE'], 30)
    referral_percentage = min((referral_points / DISCOUNT_SETTINGS['REFERRAL_BASE_AMOUNT']), 10)
    activity_percentage = min((activity_points / DISCOUNT_SETTINGS['ACTIVITY_BASE_AMOUNT']) * DISCOUNT_SETTINGS['ACTIVITY_PERCENTAGE'], 10)
    
    total_percentage = purchase_percentage + referral_percentage + activity_percentage
    
    # Рассчитываем скидку
    discount_amount = (purchase_amount * total_percentage) / 100
    final_price = purchase_amount - discount_amount
    
    return {
        "discount": round(discount_amount, 2),
        "total_percentage": round(total_percentage, 2),
        "final_price": round(final_price, 2),
        "purchase_percentage": round(purchase_percentage, 2),
        "referral_percentage": round(referral_percentage, 2),
        "activity_percentage": round(activity_percentage, 2)
    }