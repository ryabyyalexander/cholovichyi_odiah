from typing import Any

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from data_base.models import data_base
from filters import IsAdmin
from fsm.states import StateEditProduct
from keyboards.kb import (
    edit_product_keyboard,
    get_selection_keyboard,
    sizes_selection_keyboard,
    qty_selection_keyboard,
    loyalty_tiers_keyboard,
    NavigationCallback,
    get_product_detail_keyboard,
    get_slider_keyboard
)
from utils.message_manager import MessageManager
from utils.loader import bot
from utils import logger, admins
from utils.category_utils import get_subcategory_label, get_subcategory_choices, get_category_label
from routers.edit_media_router import show_media_grid
from enums.categories_enum import Categories
from enums.seasons_enum import Seasons
from enums.brands_enum import Brands
from enums.sizes_enums import JacketSizes, JerseySizes, JeansSizes
from utils.lexicon import btn
from services.notification_service import trigger_discount_notifications

ADMIN_IDS = admins

router = Router()
router.message.filter(IsAdmin(admin_ids=ADMIN_IDS))


async def create_product_card(product_id: int) -> tuple[str, str | None, str | None, object | None]:
    """Создает текстовое описание, ID главного медиа, его тип и клавиатуру для карточки товара."""
    product = data_base.sql_get_product(product_id)
    if not product:
        logger.warning(f"Product with ID {product_id} not found in create_product_card.")
        return "Товар не найден.", None, None, None

    available_sizes = data_base.get_available_sizes(product_id)
    sizes_text = "Доступные размеры:\n"
    if available_sizes:
        valid_sizes = {size: qty for size, qty in available_sizes.items() if qty > 0}
        number_sizes = [f"{size.value}({valid_sizes[size.value]})" for size in JacketSizes if size.value in valid_sizes]
        letter_sizes = [f"{size.value.upper()}({valid_sizes[size.value]})" for size in JerseySizes if size.value in valid_sizes]
        jeans_sizes = [f"{size.value}({valid_sizes[size.value]})" for size in JeansSizes if size.value in valid_sizes]
        sizes_parts = []
        if number_sizes: sizes_parts.append(", ".join(number_sizes))
        if letter_sizes: sizes_parts.append(", ".join(letter_sizes))
        if jeans_sizes: sizes_parts.append(", ".join(jeans_sizes))
        sizes_text += " | ".join(sizes_parts) if sizes_parts else "нет"
    else:
        sizes_text += "нет"

    # Получаем label для категории и подкатегории
    category_label = get_category_label(product['category'])
    subcategory_label = get_subcategory_label(product['category'], product['subcategory'])

    # Определяем иконку сезона
    season_icon = ""
    if product.get('season') == 'осінь-зима':
        season_icon = '❄️ '
    elif product.get('season') == 'весна-літо':
        season_icon = '☀️ '

    discount_price = round(product['sale_price'] - (product['sale_price'] * product['discount'] / 100), 2)

    # Формируем строку для скидок лояльности
    loyalty_text = ""
    loyalty_tiers_json = product.get('loyalty_tiers')
    if loyalty_tiers_json:
        import json
        from data_base.constants import LOYALTY_DISCOUNTS, LOYALTY_ICONS
        try:
            loyalty_tiers = json.loads(loyalty_tiers_json)
            if loyalty_tiers:
                loyalty_parts = []
                for tier in loyalty_tiers:
                    if tier in LOYALTY_DISCOUNTS:
                        icon = LOYALTY_ICONS.get(tier, '')
                        discount = LOYALTY_DISCOUNTS[tier]
                        loyalty_parts.append(f"{icon} -{discount}% для {tier.capitalize()}")
                if loyalty_parts:
                    loyalty_text = "\n".join(loyalty_parts) + "\n"
        except json.JSONDecodeError:
            pass # Оставляем loyalty_text пустым

    text = (
        f"<code>{category_label}/{subcategory_label} {season_icon}{product['season']}\n"
        f"</code><b>{product['brand']}</b><code> • {product['country']}\n"
        f"ID {product_id} - {product['name']}</code>\n\n"
        f"{product['short_description'] or ''}\n\n"
        f"<code>Цена: {product['sale_price']} €\n"
        f"Скидка - {product['discount']}% = {discount_price} €\n\n"
        f"{loyalty_text}"
        f"{sizes_text}</code>")

    # Получаем главное медиа товара
    main_media = None
    media_list = data_base.get_product_media(product_id)
    for media in media_list:
        if media[3]:  # is_main
            main_media = media
            break
    if not main_media and media_list:
        main_media = media_list[0]
    main_file_id = main_media[1] if main_media else None
    main_media_type = main_media[2] if main_media else None
    markup = edit_product_keyboard(product_id)
    return text, main_file_id, main_media_type, markup


async def send_product_card(chat_id: int, product_id: int, state: FSMContext, message_manager: MessageManager) -> None | Message | bool | Any:
    """Отправляет или обновляет карточку товара, используя MessageManager (универсально для всех типов медиа)."""
    logger.info(f"Attempting to send/update product card for product_id: {product_id} in chat: {chat_id}")
    try:
        text, main_file_id, main_media_type, markup = await create_product_card(product_id)
        if text == "Товар не найден.":
            await message_manager.send(text, reply_markup=markup)
            return
        data = await state.get_data()
        current_msg_id = data.get("product_card_message_id")
        old_detail_msg_id = data.get("old_detail_message_id")
        old_slider_msg_id = data.get("old_slider_message_id")
        old_message_has_media = False
        old_message_id = None
        if current_msg_id:
            old_message_id = current_msg_id
            old_message_has_media = True
        elif old_detail_msg_id:
            old_message_id = old_detail_msg_id
            old_message_has_media = True
        elif old_slider_msg_id:
            old_message_id = old_slider_msg_id
            old_message_has_media = True
        if main_file_id and main_media_type:
            logger.debug(f"Sending product card with media for product {product_id}")
            try:
                if old_message_has_media:
                    try:
                        # Универсальный выбор InputMedia*
                        if main_media_type == "photo":
                            input_media = InputMediaPhoto(media=main_file_id, caption=text)
                        elif main_media_type == "video":
                            input_media = InputMediaVideo(media=main_file_id, caption=text)
                        elif main_media_type == "document":
                            input_media = InputMediaDocument(media=main_file_id, caption=text)
                        elif main_media_type == "audio":
                            input_media = InputMediaAudio(media=main_file_id, caption=text)
                        else:
                            input_media = InputMediaPhoto(media=main_file_id, caption=text)
                        edited_msg = await message_manager.bot.edit_message_media(
                            chat_id=chat_id,
                            message_id=old_message_id,
                            media=input_media,
                            reply_markup=markup
                        )
                        logger.info(f"Media message {old_message_id} successfully edited")
                        return edited_msg
                    except TelegramBadRequest as e:
                        logger.warning(f"Failed to edit media message {old_message_id}: {e}")
                        try:
                            await message_manager.bot.delete_message(chat_id, old_message_id)
                        except TelegramBadRequest:
                            pass
                # Если редактирование не удалось или сообщения нет, отправляем новое
                new_msg = await message_manager.send_media_message(
                    media_type=main_media_type,
                    file=main_file_id,
                    caption=text,
                    reply_markup=markup
                )
                if new_msg:
                    await state.update_data(product_card_message_id=new_msg.message_id)
                    await state.update_data(old_detail_message_id=None, old_slider_message_id=None)
                return new_msg
            except Exception as media_error:
                logger.warning(f"Failed to send as media (ID: {main_file_id}), trying as document: {media_error}")
                try:
                    new_msg = await message_manager.send_document_message(
                        document=main_file_id,
                        caption=text,
                        reply_markup=markup
                    )
                    if new_msg:
                        await state.update_data(product_card_message_id=new_msg.message_id)
                        await state.update_data(old_detail_message_id=None, old_slider_message_id=None)
                    return new_msg
                except Exception as doc_error:
                    logger.error(f"Failed to send as document: {doc_error}")
                    if old_message_has_media:
                        try:
                            edited_msg = await message_manager.edit(
                                f"⚠️ Не удалось отобразить медіа товара\n\n{text}",
                                reply_markup=markup
                            )
                            return edited_msg
                        except TelegramBadRequest:
                            pass
                    new_msg = await message_manager.send(
                        f"⚠️ Не удалось отобразить медіа товара\n\n{text}",
                        reply_markup=markup
                    )
                    if new_msg:
                        await state.update_data(product_card_message_id=new_msg.message_id)
                        await state.update_data(old_detail_message_id=None, old_slider_message_id=None)
                    return new_msg
        else:
            logger.debug(f"No media for product {product_id}, sending as text")
            if old_message_has_media:
                try:
                    edited_msg = await message_manager.edit(
                        f"⚠️ Медіа відсутнє\n\n{text}",
                        reply_markup=markup
                    )
                    return edited_msg
                except TelegramBadRequest as e:
                    logger.warning(f"Failed to edit text message {old_message_id}: {e}")
                    try:
                        await message_manager.bot.delete_message(chat_id, old_message_id)
                    except TelegramBadRequest:
                        pass
            new_msg = await message_manager.send(
                f"⚠️ Медіа відсутнє\n\n{text}",
                reply_markup=markup
            )
            if new_msg:
                await state.update_data(product_card_message_id=new_msg.message_id)
                await state.update_data(old_detail_message_id=None, old_slider_message_id=None)
            return new_msg
    except Exception as e:
        logger.error(f"CRITICAL ERROR in send_product_card: {e}", exc_info=True)
        await message_manager.send(
            f"⚠️ Произошла критическая ошибка при отображении товара ID {product_id}")

@router.message(
    F.text.regexp(r'^\d+a$'),
    ~StateFilter(StateEditProduct.editing_price),
    ~StateFilter(StateEditProduct.editing_purchase_price),
    ~StateFilter(StateEditProduct.editing_discount),
    ~StateFilter(StateEditProduct.editing_name),
    ~StateFilter(StateEditProduct.editing_description)
)
async def select_product_to_edit(message: Message, state: FSMContext) -> None:
    """Обработчик выбора товара для редактирования по ID (формат: 15a)."""
    current_state = await state.get_state()
    print(f"[DEBUG] FSM state on ID input: {current_state}")
    try:
        # Убираем 'a' в конце и преобразуем в число
        product_id = int(message.text[:-1])
    except ValueError:
        await message.reply("Пожалуйста, введите корректный ID товара в формате '15a'.")
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    
    # Проверяем, является ли пользователь админом
    if user_id not in admins:
        await message.reply("У вас нет прав для редактирования товаров.")
        return
    
    logger.info(f"Admin {chat_id} selected product ID {product_id} for editing.")

    message_manager = MessageManager(bot, state, chat_id)
    product = data_base.sql_get_product(product_id)
    data = await state.get_data()

    # Cancel any running animation
    if "animation_task" in data and not data["animation_task"].done():
        data["animation_task"].cancel()
        logger.debug("Анимация остановлена")


    if not product:
        logger.warning(f"Product with ID {product_id} not found for editing by admin {chat_id}.")
        await message_manager.send(f"Товар с ID {product_id} не найден.")
        try:
            await message.delete()
            logger.debug(f"User message {message.message_id} with product ID deleted.")
        except TelegramBadRequest as e:
            logger.warning(f"Could not delete user message {message.message_id}: {e}")
        return

    await state.set_state(StateEditProduct.editing)
    await state.update_data(product_id=product_id)
    logger.info(f"State set to StateEditProduct.editing for product_id: {product_id}")

    await send_product_card(chat_id, product_id, state, message_manager)
    try:
        await message.delete()
        logger.debug(f"User message {message.message_id} with product ID deleted.")
    except TelegramBadRequest as e:
        logger.warning(f"Could not delete user message {message.message_id}: {e}")


@router.callback_query(F.data.startswith("edit_"), StateFilter(StateEditProduct.editing))
async def edit_product_field(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    product_id = data.get('product_id')
    if not product_id:
        logger.error("product_id not found in state for edit_product_field.")
        await callback.answer("Ошибка: ID товара не найден. Попробуйте снова.", show_alert=True)
        return

    chat_id = callback.message.chat.id
    action = callback.data.split(":")[0]

    message_manager = MessageManager(bot, state, chat_id)
    text_prompt = ""
    new_state = None
    reply_kb = None

    if action == "edit_name":
        text_prompt = "Введите новое название товара:"
        new_state = StateEditProduct.editing_name
    elif action == "edit_desc":
        text_prompt = "Введите новое описание товара:"
        new_state = StateEditProduct.editing_description
    elif action == "edit_price":
        text_prompt = "Введите новую цену товара (число):"
        new_state = StateEditProduct.editing_price
    elif action == "edit_purchase_price":
        text_prompt = "Введите закупочную цену товара (число):"
        new_state = StateEditProduct.editing_purchase_price
    elif action == "edit_discount":
        text_prompt = "Введите новую скидку (число 0-100):"
        new_state = StateEditProduct.editing_discount
    elif action == "edit_category":
        text_prompt = "Выберите категорию:"
        reply_kb = get_selection_keyboard(
            [cat.value for cat in Categories],
            "set_category", product_id
        )
    elif action == "edit_season":
        text_prompt = "Выберите сезон:"
        reply_kb = get_selection_keyboard(
            [season.value for season in Seasons],
            "set_season", product_id
        )
    elif action == "edit_brand":
        text_prompt = "Выберите бренд:"
        reply_kb = get_selection_keyboard(
            [brand.value for brand in Brands],
            "set_brand", product_id
        )
    elif action == "edit_loyalty_tiers":
        import json
        product = data_base.sql_get_product(product_id)
        current_tiers_json = product.get("loyalty_tiers")
        current_tiers = []
        if current_tiers_json:
            try:
                current_tiers = json.loads(current_tiers_json)
            except json.JSONDecodeError:
                current_tiers = []
        
        text_prompt = "Выберите уровни лояльности для скидки:"
        reply_kb = loyalty_tiers_keyboard(product_id, current_tiers)
        new_state = StateEditProduct.editing_loyalty_tiers
    elif action == "edit_sizes":
        current_sizes_dict = data_base.get_available_sizes(product_id)
        text_prompt = "Укажите наличие и количество размеров:"
        reply_kb = sizes_selection_keyboard(product_id, current_sizes_dict)
    elif action == "edit_photos":
        await callback.answer()
        # Импортируем функцию из нового роутера
        await show_media_grid(chat_id, product_id, state, message_manager)
        return
    elif action == "edit_subcategory":
        # Получаем текущую категорию товара
        product = data_base.sql_get_product(product_id)
        category = product.get("category") if product else None
        subcategories = get_subcategory_choices(category)
        text_prompt = "Виберіть підкатегорію:"
        reply_kb = get_selection_keyboard(
            [value for label, value in subcategories],
            "set_subcategory", product_id
        )

    if text_prompt:
        await message_manager.edit_photo_caption(caption=text_prompt, reply_markup=reply_kb)

    if new_state:
        await state.set_state(new_state)

    await callback.answer()


@router.callback_query(F.data.startswith("set_"), StateFilter(StateEditProduct.editing))
async def set_product_field(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    product_id = data.get('product_id')
    if not product_id:
        logger.error("product_id not found in state for set_product_field.")
        await callback.answer("Ошибка: ID товара не найден. Попробуйте снова.", show_alert=True)
        return

    chat_id = callback.message.chat.id
    parts = callback.data.split(":")
    action_type = parts[0]
    value = parts[2]

    field_to_update = None
    if action_type == "set_category":
        field_to_update = "category"
    elif action_type == "set_subcategory":
        field_to_update = "subcategory"
        # Сохраняем value (ключ enum), а не label
        # value уже является правильным ключом enum (например, "sweatshirts")
        # Не нужно преобразовывать в label
    elif action_type == "set_season":
        field_to_update = "season"
    elif action_type == "set_brand":
        field_to_update = "brand"

    message_manager = MessageManager(bot, state, chat_id)

    if field_to_update:
        try:
            data_base.update_product_field(product_id, field_to_update, value)
            logger.info(f"Product ID {product_id} field '{field_to_update}' updated to '{value}'.")

            # Автозаполнение country в зависимости от бренда
            if field_to_update == "brand":
                italy_brands = ['Impulso', 'Montechiaro', 'Lorenzoni', 'Marina Militare']
                germany_brands = ['Alberto', 'Milestone', 'Casa Moda', 'Red Point']
                nederland_brands = ['R2 Amsterdam']

                country_value = None
                if value in italy_brands:
                    country_value = "Italy"
                elif value in germany_brands:
                    country_value = "Germany"
                elif value in nederland_brands:
                    country_value = "Niderland"

                if country_value:
                    data_base.update_product_field(product_id, "country", country_value)
                    logger.info(f"Country auto-set to {country_value} for brand '{value}' in product {product_id}")

            await send_product_card(chat_id, product_id, state, message_manager)
            await state.set_state(StateEditProduct.editing)
        except Exception as e:
            logger.error(f"Error updating product field '{field_to_update}' for product_id {product_id}: {e}",
                         exc_info=True)
            await callback.answer("⚠️ Ошибка при обновлении данных товара.", show_alert=True)
            await send_product_card(chat_id, product_id, state, message_manager)
    else:
        logger.warning(f"Unknown action_type '{action_type}' in set_product_field for product_id {product_id}.")
        await callback.answer("Неизвестное действие.", show_alert=True)

    await callback.answer()


@router.callback_query(F.data.startswith("toggle_loyalty_tier:"), StateFilter(StateEditProduct.editing_loyalty_tiers))
async def toggle_loyalty_tier_handler(callback: CallbackQuery, state: FSMContext) -> None:
    import json
    _, product_id_str, tier_name = callback.data.split(":")
    product_id = int(product_id_str)

    product = data_base.sql_get_product(product_id)
    current_tiers_json = product.get("loyalty_tiers")
    current_tiers = []
    if current_tiers_json:
        try:
            current_tiers = json.loads(current_tiers_json)
        except json.JSONDecodeError:
            current_tiers = []

    if tier_name in current_tiers:
        current_tiers.remove(tier_name)
    else:
        current_tiers.append(tier_name)

    updated_tiers_json = json.dumps(current_tiers)
    data_base.update_product_field(product_id, "loyalty_tiers", updated_tiers_json)

    await callback.message.edit_reply_markup(
        reply_markup=loyalty_tiers_keyboard(product_id, current_tiers)
    )
    await callback.answer()


async def process_text_input(message: Message, state: FSMContext, field_name: str):
    data = await state.get_data()
    product_id = data.get('product_id')
    if not product_id:
        logger.error(f"product_id not found in state for process_text_input (field: {field_name}).")
        return

    chat_id = message.chat.id
    message_manager = MessageManager(bot, state, chat_id)
    new_value_str = message.text

    # Get old product data for comparison
    old_product = data_base.sql_get_product(product_id)
    old_discount = old_product.get('discount', 0) if old_product else 0

    # Валидация и преобразование типов
    new_value: any = new_value_str
    if field_name == "sale_price":
        try:
            clean_value = new_value_str.replace(' ', '').replace(',', '.')
            new_value = round(float(clean_value), 2)
            if new_value < 0:
                raise ValueError("Price cannot be negative.")
        except ValueError:
            await message.reply("Цена должна быть положительным числом (например, 123.45). Попробуйте снова.")
            return
    elif field_name == "discount":
        try:
            clean_value = new_value_str.replace(' ', '').replace(',', '.')
            new_value = int(float(clean_value))
            if not (0 <= new_value <= 100):
                raise ValueError("Discount must be between 0 and 100.")
        except ValueError:
            await message.reply("Скидка должна быть целым числом от 0 до 100. Попробуйте снова.")
            return

    try:
        await message.delete()
        data_base.update_product_field(product_id, field_name, new_value)
        logger.info(f"Product ID {product_id} field '{field_name}' updated to '{new_value}'.")

        # --- Trigger for discount notifications ---
        if field_name == "discount" and new_value > old_discount:
            logger.info(f"Discount for product {product_id} increased from {old_discount} to {new_value}. Triggering notifications.")
            await trigger_discount_notifications(product_id, new_value)
            
        await send_product_card(chat_id, product_id, state, message_manager)
        await state.set_state(StateEditProduct.editing)
        await state.update_data(product_id=product_id)
    except Exception as e:
        logger.error(
            f"Error updating product field '{field_name}' for product_id {product_id} with value '{new_value}': {e}",
            exc_info=True)
        await message_manager.send(f"⚠️ Ошибка при обновлении поля '{field_name}'.")
        await send_product_card(chat_id, product_id, state, message_manager)
        await state.set_state(StateEditProduct.editing)


@router.message(StateFilter(StateEditProduct.editing_name))
async def process_edit_name(message: Message, state: FSMContext): await process_text_input(message, state, "name")


@router.message(StateFilter(StateEditProduct.editing_description))
async def process_edit_description(message: Message, state: FSMContext): await process_text_input(message, state,
                                                                                                  "short_description")


@router.message(StateFilter(StateEditProduct.editing_price))
async def handle_price_input(message: Message, state: FSMContext):
    await process_text_input(message, state, "sale_price")


@router.message(StateFilter(StateEditProduct.editing_purchase_price))
async def handle_purchase_price_input(message: Message, state: FSMContext):
    await process_text_input(message, state, "purchase_price")


@router.message(StateFilter(StateEditProduct.editing_discount))
async def process_edit_discount(message: Message, state: FSMContext): await process_text_input(message, state,
                                                                                               "discount")


@router.callback_query(F.data.startswith("add_size:"), StateFilter(StateEditProduct.editing))
async def add_size_handler(callback: CallbackQuery, state: FSMContext) -> None:
    _, product_id_str, size_val = callback.data.split(":")
    product_id = int(product_id_str)
    chat_id = callback.message.chat.id
    message_manager = MessageManager(bot, state, chat_id)
    data = await state.get_data()
    if data.get('product_id') != product_id:
        logger.warning(
            f"Product ID mismatch in add_size_handler: state ({data.get('product_id')}) vs callback ({product_id})")
        await callback.answer("Ошибка ID товара. Попробуйте снова.", show_alert=True)
        return
    try:
        data_base.add_product_size(product_id, size_val, 1)
        logger.info(f"Added size {size_val} with qty 1 for product {product_id}")
        current_sizes = data_base.get_available_sizes(product_id)
        await message_manager.edit_photo_caption(
            caption="Выберите размеры или их количество:",
            reply_markup=sizes_selection_keyboard(product_id, current_sizes)
        )
        await callback.answer(f"✅ Размер {size_val} (1 шт) добавлен. Нажмите на него, чтобы изменить количество.")
    except Exception as e:
        logger.error(f"Error in add_size_handler for product {product_id}, size {size_val}: {e}", exc_info=True)
        await callback.answer("⚠️ Ошибка при добавлении размера.", show_alert=True)


@router.callback_query(F.data.startswith("select_qty:"), StateFilter(StateEditProduct.editing))
async def select_qty_handler(callback: CallbackQuery, state: FSMContext) -> None:
    _, product_id_str, size_val = callback.data.split(":")
    product_id = int(product_id_str)
    chat_id = callback.message.chat.id
    message_manager = MessageManager(bot, state, chat_id)
    data = await state.get_data()
    if data.get('product_id') != product_id:
        logger.warning(
            f"Product ID mismatch in select_qty_handler: state ({data.get('product_id')}) vs callback ({product_id})")
        await callback.answer("Ошибка ID товара. Попробуйте снова.", show_alert=True)
        return
    await message_manager.edit_photo_caption(
        caption=f"Выберите новое количество для размера {size_val}:",
        reply_markup=qty_selection_keyboard(product_id, size_val)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("update_qty:"), StateFilter(StateEditProduct.editing))
async def update_qty_handler(callback: CallbackQuery, state: FSMContext) -> None:
    _, product_id_str, size_val_from_cb, qty_str = callback.data.split(":")
    product_id = int(product_id_str)
    new_qty = int(qty_str)
    chat_id = callback.message.chat.id
    message_manager = MessageManager(bot, state, chat_id)
    data = await state.get_data()
    if data.get('product_id') != product_id:
        logger.warning(f"Product ID mismatch in update_qty_handler.")
        await callback.answer("Ошибка ID товара.", show_alert=True)
        return
    size_val = size_val_from_cb
    try:
        if new_qty == 0:
            data_base.remove_product_size(product_id, size_val)
            logger.info(f"Removed size {size_val} for product {product_id}")
        else:
            data_base.add_product_size(product_id, size_val, new_qty)
            logger.info(f"Updated quantity for size {size_val} to {new_qty} for product {product_id}")
        current_sizes = data_base.get_available_sizes(product_id)
        await message_manager.edit_photo_caption(
            caption="Выберите размеры или их количество:",
            reply_markup=sizes_selection_keyboard(product_id, current_sizes)
        )
        await callback.answer(f"Количество для {size_val} обновлено: {new_qty if new_qty > 0 else 'удален'}")
    except Exception as e:
        logger.error(f"Error in update_qty_handler for product {product_id}, size {size_val}: {e}", exc_info=True)
        await callback.answer("⚠️ Ошибка при обновлении количества.", show_alert=True)


@router.callback_query(F.data.startswith("menu:"), StateFilter(StateEditProduct.editing, StateEditProduct.editing_loyalty_tiers))
async def back_to_product_menu_from_sizes(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    product_id = data.get('product_id')
    if not product_id:
        logger.error("product_id not found in state for back_to_product_menu_from_sizes.")
        await callback.answer("Ошибка: ID товара не найден. Попробуйте снова.", show_alert=True)
        return
    chat_id = callback.message.chat.id
    message_manager = MessageManager(bot, state, chat_id)
    await send_product_card(chat_id, product_id, state, message_manager)
    await state.set_state(StateEditProduct.editing)
    await callback.answer("Возврат в меню редактирования товара.")


@router.callback_query(F.data == "close_slider", StateFilter("slider_viewing"))
async def handle_close_slider(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    product_id_for_return = data.get("product_id")
    chat_id = callback.message.chat.id
    message_manager = MessageManager(bot, state, chat_id)
    slider_own_msg_id = data.get("msg_id")
    if slider_own_msg_id:
        try:
            await bot.delete_message(chat_id, slider_own_msg_id)
            logger.info(f"Slider message {slider_own_msg_id} deleted.")
        except TelegramBadRequest as e:
            logger.warning(f"Failed to delete slider message {slider_own_msg_id}: {e}")
    else:
        logger.warning("No 'msg_id' (slider's own message ID) found in state when closing slider.")

    await state.update_data(
        index=None, playing=None, photo_list=None, msg_id=None, speed=None,
        cycle_count=None, cycle_length=None, expanded=None, first_photo_shown=None
    )
    logger.debug("Slider specific data cleared from FSM.")

    if not product_id_for_return:
        logger.warning("product_id_for_return not found in state when closing slider. Cannot return to product card.")
        await state.clear()
        await callback.answer("Слайдер закрыт.")
        return

    await state.set_state(StateEditProduct.editing)
    logger.info(f"State set back to StateEditProduct.editing for product_id: {product_id_for_return}")
    await send_product_card(chat_id, product_id_for_return, state, message_manager)
    await callback.answer("Просмотр фото завершен.")


@router.callback_query(F.data == btn['x'], StateFilter(StateEditProduct.editing))
async def close_product_editing_card(callback: CallbackQuery, state: FSMContext):
    chat_id = callback.message.chat.id
    message_manager = MessageManager(bot, state, chat_id)
    logger.info(f"User {chat_id} pressed close on product editing card.")
    active_msg_id = await message_manager.get_active_msg_id()
    if active_msg_id:
        try:
            await bot.delete_message(chat_id, active_msg_id)
            logger.debug(f"Deleted product editing card message {active_msg_id}.")
        except TelegramBadRequest as e:
            logger.warning(f"Failed to delete product editing card message {active_msg_id}: {e}")
    await state.clear()
    await callback.answer("Редактирование товара завершено.")


@router.callback_query(F.data.startswith("product_delete:"), StateFilter(StateEditProduct.editing))
async def delete_product_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик удаления товара с подтверждением."""
    _, product_id_str = callback.data.split(":")
    product_id = int(product_id_str)
    chat_id = callback.message.chat.id
    message_manager = MessageManager(bot, state, chat_id)
    
    # Проверяем, что товар существует
    product = data_base.sql_get_product(product_id)
    if not product:
        await callback.answer("⚠️ Товар не найден!", show_alert=True)
        return
    
    # Создаем клавиатуру подтверждения
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Так, видалити",
        callback_data=f"product_confirm_delete:{product_id}"
    )
    builder.button(
        text="❌ Скасувати",
        callback_data=f"product_cancel_delete:{product_id}"
    )
    builder.adjust(2)
    
    # Показываем подтверждение
    await callback.message.edit_caption(
        caption=f"⚠️ **Підтвердження видалення**\n\n"
                f"Ви дійсно хочете видалити товар?\n\n"
                f"**ID:** {product_id}\n"
                f"**Назва:** {product['name']}\n"
                f"**Бренд:** {product['brand']}\n\n"
                f"❗️ Ця дія незворотна!",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("product_confirm_delete:"), StateFilter(StateEditProduct.editing))
async def confirm_delete_product(callback: CallbackQuery, state: FSMContext):
    """Подтверждение удаления товара."""
    _, product_id_str = callback.data.split(":")
    product_id = int(product_id_str)
    chat_id = callback.message.chat.id
    message_manager = MessageManager(bot, state, chat_id)
    
    try:
        # Получаем информацию о товаре перед удалением
        product = data_base.sql_get_product(product_id)
        if not product:
            await callback.answer("⚠️ Товар не знайдено!", show_alert=True)
            return
        
        # Удаляем товар из базы данных
        data_base.delete_product(product_id)
        logger.info(f"Product {product_id} ({product['name']}) deleted by admin {chat_id}")
        
        # Показываем сообщение об успешном удалении
        await callback.message.edit_caption(
            caption=f"✅ **Товар успішно видалено!**\n\n"
                    f"**ID:** {product_id}\n"
                    f"**Назва:** {product['name']}\n"
                    f"**Бренд:** {product['brand']}\n\n"
                    f"Товар та всі його розміри були видалені з бази даних.",
            reply_markup=InlineKeyboardBuilder().button(
                text="← Повернутися до фільтрів",
                callback_data=NavigationCallback(action="filters", current_level="filters", breadcrumbs="").pack()
            ).as_markup()
        )
        
        # Очищаем состояние
        await state.clear()
        await callback.answer("Товар видалено!")
        
    except Exception as e:
        logger.error(f"Error deleting product {product_id}: {e}", exc_info=True)
        await callback.answer("⚠️ Помилка при видаленні товару!", show_alert=True)
        
        # Возвращаемся к редактированию товара
        await send_product_card(chat_id, product_id, state, message_manager)


@router.callback_query(F.data.startswith("product_cancel_delete:"), StateFilter(StateEditProduct.editing))
async def cancel_delete_product(callback: CallbackQuery, state: FSMContext):
    """Отмена удаления товара."""
    _, product_id_str = callback.data.split(":")
    product_id = int(product_id_str)
    chat_id = callback.message.chat.id
    message_manager = MessageManager(bot, state, chat_id)
    
    # Возвращаемся к редактированию товара
    await send_product_card(chat_id, product_id, state, message_manager)
    await callback.answer("Видалення скасовано!")


@router.callback_query(F.data.startswith("return_to_product:"), StateFilter(StateEditProduct.editing))
async def return_to_product_from_edit(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Вернуться к товару' - возвращает к тому же товару"""
    await callback.answer()
    try:
        product_id = int(callback.data.split(":")[1])
        data = await state.get_data()
        
        # Проверяем, что product_id в состоянии совпадает с тем, что в callback_data
        state_product_id = data.get('product_id')
        if state_product_id != product_id:
            await callback.answer("⚠️ ID товару не співпадає", show_alert=True)
            return
        
        chat_id = callback.message.chat.id
        message_manager = MessageManager(bot, state, chat_id)
        
        # Проверяем, откуда пользователь пришел в редактирование
        old_slider_msg_id = data.get("old_slider_message_id")
        
        if old_slider_msg_id:
            # Пользователь пришел из слайдера
            logger.info(f"Returning to slider for product {product_id}")
            from utils.slider_manager import SliderManager

            # Получаем данные слайдера из состояния
            slider_data = await state.get_data()
            media_list = slider_data.get("media_list", [])
            product_ids = slider_data.get("product_ids", [])

            if not media_list or not product_ids:
                await callback.answer("⚠️ Дані слайдера не знайдено", show_alert=True)
                return

            # Находим индекс товара в слайдере
            try:
                slider_index = product_ids.index(product_id)
            except ValueError:
                slider_index = 0 # Если не нашли, возвращаемся к первому слайду

            # Обновляем состояние слайдера
            await state.update_data(index=slider_index)

            # Получаем информацию о медиа
            media_info = media_list[slider_index]
            file_id = media_info.get("path") or media_info.get("file_id")
            media_type = media_info.get("media_type", "photo")
            
            # Создаем caption
            slider_manager = SliderManager(message_manager, state)
            caption = await slider_manager.get_full_slider_caption(
                product_id,
                callback.from_user.id,
                cart_items=data.get("cart_items", []),
                show_cart_block=True, # expanded=True
                source=slider_data.get("slider_source", "main"),
                breadcrumbs=slider_data.get("slider_breadcrumbs", ""),
                total_items=len(media_list),
                index=slider_index
            )

            # Создаем InputMedia
            if media_type == "video":
                input_media = InputMediaVideo(media=file_id, caption=caption)
            elif media_type == "document":
                input_media = InputMediaDocument(media=file_id, caption=caption)
            elif media_type == "audio":
                input_media = InputMediaAudio(media=file_id, caption=caption)
            else: # По умолчанию photo
                input_media = InputMediaPhoto(media=file_id, caption=caption)

            # Проверяем, находится ли товар в избранном
            user_id = callback.from_user.id
            is_favorite = data_base.is_product_in_favorites(user_id, product_id) if user_id and product_id else False

            # Создаем клавиатуру
            keyboard = get_slider_keyboard(
                expanded=True,
                index=slider_index,
                total=len(media_list),
                user_id=user_id,
                is_favorite=is_favorite,
                product_id=product_id,
                source=slider_data.get("slider_source", "main"),
                breadcrumbs=slider_data.get("slider_breadcrumbs", ""),
                active_filters=slider_data.get("active_filters", {})
            )

            try:
                await callback.message.edit_media(
                    media=input_media,
                    reply_markup=keyboard
                )
            except TelegramBadRequest as e:
                logger.warning(f"Failed to edit message: {e}. Sending new one.")
                await message_manager.send_media_message(
                    media_type=media_type,
                    file=file_id,
                    caption=caption,
                    reply_markup=keyboard
                )

            # Возвращаемся к состоянию слайдера
            await state.set_state("slider_viewing")
            await callback.answer("← Повернувся до слайдера")
            
        else:
            # Пользователь пришел напрямую (например, ввел ID товара)
            # Возвращаем к главному меню
            logger.info(f"No return path found for product {product_id}, going to main menu")
            
            # Очищаем состояние редактирования
            await state.clear()
            
            # Отправляем главное меню
            from routers.navigation_router import process_main_menu
            # Создаем фиктивный callback_data для главного меню
            from keyboards.kb import NavigationCallback
            fake_callback_data = NavigationCallback(action="main", current_level="main", breadcrumbs="")
            await process_main_menu(callback, fake_callback_data, state, message_manager)
            
            await callback.answer("← Повернувся до головного меню")
        
    except Exception as e:
        logger.error(f"Error in return_to_product_from_edit: {e}")
        await callback.answer("⚠️ Помилка при поверненні до товару", show_alert=True)


@router.callback_query(F.data.startswith("activate_product:"), StateFilter(StateEditProduct.editing))
async def handle_activate_product_callback(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split(":")[1])
    admin_id = callback.from_user.id
    try:
        data_base.activate_product(product_id, admin_id, "Активировано через меню редактирования")
        await callback.answer("Товар активовано!", show_alert=True)
    except ValueError as e:
        # Если ошибка связана с отсутствием закупочной цены
        if "purchase_price" in str(e):
            await callback.answer("Для активації товару необхідно ввести закупівельну ціну.", show_alert=True)
        else:
            await callback.answer(f"Помилка активації: {e}", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка активации товара: {e}")
        await callback.answer("Виникла помилка при активації товару.", show_alert=True)
    # Обновляем клавиатуру
    try:
        await callback.message.edit_reply_markup(reply_markup=edit_product_keyboard(product_id))
    except Exception:
        pass

@router.callback_query(F.data.startswith("deactivate_product:"), StateFilter(StateEditProduct.editing))
async def handle_deactivate_product_callback(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split(":")[1])
    admin_id = callback.from_user.id
    try:
        data_base.deactivate_product(product_id, admin_id, "Деактивировано через меню редактирования")
        await callback.answer("Товар деактивирован!", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка деактивации товара: {e}")
        await callback.answer(f"Ошибка деактивации: {e}", show_alert=True)
    # Обновляем клавиатуру
    await callback.message.edit_reply_markup(reply_markup=edit_product_keyboard(product_id))


