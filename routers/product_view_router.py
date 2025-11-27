from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest

from data_base.models import data_base
from utils import logger
from utils.message_manager import MessageManager
from utils.slider_manager import SliderManager
from utils.loader import bot

router = Router()
# Убираем фильтр - теперь все пользователи (включая админов) могут смотреть слайдеры


@router.message(F.text.regexp(r'^\d+$'))
async def show_product_slider(message: Message, state: FSMContext) -> None:
    """Обработчик цифровых сообщений для показа слайдера товара обычным пользователям."""
    try:
        product_id = int(message.text)
    except ValueError:
        return  # Не должно произойти, но на всякий случай

    chat_id = message.chat.id
    user_id = message.from_user.id
    
    logger.info(f"User {chat_id} requested product slider for ID {product_id}")

    message_manager = MessageManager(bot, state, chat_id)
    
    # Проверяем, существует ли товар
    product = data_base.sql_get_product(product_id)
    if not product:
        await message_manager.send(f"Товар з ID {product_id} не знайдено.")
        try:
            await message.delete()
        except TelegramBadRequest:
            pass
        return

    # Получаем медиа товара
    media_list = data_base.get_product_media(product_id)
    if not media_list:
        await message_manager.send(f"У товару з ID {product_id} немає фото.")
        try:
            await message.delete()
        except TelegramBadRequest:
            pass
        return

    # Форматируем медиа для слайдера
    formatted_media = []
    for media in media_list:
        formatted_media.append({
            "path": media[1],  # file_id
            "caption": media[4] if len(media) > 4 else "",  # caption
            "media_type": media[2]  # media_type
        })

    # Создаем список product_ids (все одинаковые, так как это один товар)
    product_ids = [product_id] * len(formatted_media)

    # Запускаем слайдер
    slider_manager = SliderManager(message_manager, state)
    await slider_manager.start_slider(formatted_media, product_ids, source="product_gallery", user_id=user_id, breadcrumbs="main")

    # Удаляем сообщение пользователя
    try:
        await message.delete()
        logger.debug(f"User message {message.message_id} with product ID deleted.")
    except TelegramBadRequest as e:
        logger.warning(f"Could not delete user message {message.message_id}: {e}") 


@router.message(F.text.regexp(r"^/ID_(\d+)$"))
async def show_product_slider_by_command(message: Message, state: FSMContext) -> None:
    """Обработчик команд вида /ID_XX для показа слайдера товара по ID из корзины (большие буквы)."""
    import re
    match = re.match(r"^/ID_(\d+)$", message.text)
    if not match:
        return
    product_id = int(match.group(1))
    chat_id = message.chat.id
    user_id = message.from_user.id
    logger.info(f"User {chat_id} requested product slider for ID {product_id} via /ID_ command (from cart)")
    message_manager = MessageManager(bot, state, chat_id)
    product = data_base.sql_get_product(product_id)
    if not product:
        await message_manager.send(f"Товар з ID {product_id} не знайдено.")
        try:
            await message.delete()
        except TelegramBadRequest:
            pass
        return
    media_list = data_base.get_product_media(product_id)
    if not media_list:
        await message_manager.send(f"У товару з ID {product_id} немає фото.")
        try:
            await message.delete()
        except TelegramBadRequest:
            pass
        return
    formatted_media = []
    for media in media_list:
        formatted_media.append({
            "path": media[1],
            "caption": media[4] if len(media) > 4 else "",
            "media_type": media[2]
        })
    product_ids = [product_id] * len(formatted_media)
    slider_manager = SliderManager(message_manager, state)
    # Сбросить breadcrumbs и current_level, чтобы возврат работал как для обычного слайдера
    await state.update_data(slider_breadcrumbs="main", current_level="main")
    await slider_manager.start_slider(formatted_media, product_ids, source="product_gallery", user_id=user_id, breadcrumbs="main")
    try:
        await message.delete()
        logger.debug(f"User message {message.message_id} with /ID_ command deleted.")
    except TelegramBadRequest as e:
        logger.warning(f"Could not delete user message {message.message_id}: {e}")