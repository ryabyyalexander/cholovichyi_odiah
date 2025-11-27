import asyncio
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio
from aiogram.exceptions import TelegramBadRequest

from data_base.models import data_base
from enums import RegisteredMainMenu
from fsm.states import StateEditProduct, DetailViewState
from keyboards.kb import create_keyboard, get_product_detail_keyboard, get_slider_keyboard, NavigationCallback
from routers.edit_product_router import send_product_card
from utils.functions import get_caption
from utils.message_manager import MessageManager
from utils import safe_delete_message, admins
from utils.slider_manager import SliderManager
from utils.loader import bot
from utils import logger
from enums.sizes_enums import JacketSizes, JerseySizes, JeansSizes
from utils.view_tracker import view_tracker
from routers.navigation_router import process_main_menu
from services.loyalty_service import LoyaltyService

router = Router()



@router.callback_query(F.data.in_(["prev", "next", "pause", "play"]))
async def slideshow_controls(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    data = await state.get_data()

    # Проверяем наличие необходимых данных в состоянии
    if not data or "index" not in data or "media_list" not in data:
        try:
            if callback.message:
                first_name = callback.from_user.first_name
                caption = await get_caption(state)
                await manager.edit(caption,
                                   reply_markup=create_keyboard(RegisteredMainMenu, "", "main", add_back=False))

        except TelegramBadRequest:
            await callback.answer("Повідомлення вже видалено або не знайдено.")
        await state.clear()
        return

    # Проверяем наличие медиа
    media_list = data.get("media_list", [])
    product_ids = data.get("product_ids", [])
    if not media_list:
        msg = await callback.message.answer("❌ Немає доступних медіа.")
        await safe_delete_message(msg, 2)
        return

    # Получаем текущие параметры слайдера
    index = data["index"]
    msg_id = data["msg_id"]
    playing = data.get("playing", False)
    user_id = callback.from_user.id
    
    # Получаем product_id для текущего индекса
    product_id = product_ids[index] if index < len(product_ids) else None

    # Создаем менеджеры
    message_manager = MessageManager(callback.bot, state, callback.message.chat.id)
    slider_manager = SliderManager(message_manager, state)

    # Обрабатываем действия пользователя
    if callback.data == "prev":
        index = (index - 1) % len(media_list)
        await state.update_data(index=index, cycle_count=0)
        await slider_manager.update_photo(
            index,
            paused=not playing,
            expanded=data.get("expanded", True),
            user_id=user_id
        )
    elif callback.data == "next":
        index = (index + 1) % len(media_list)
        await state.update_data(index=index, cycle_count=0)
        await slider_manager.update_photo(
            index,
            paused=not playing,
            expanded=data.get("expanded", True),
            user_id=user_id
        )
    elif callback.data == "pause":
        # Кнопка pause нажата когда клавиатура закрыта - останавливаем автопроигрывание и открываем клавиатуру
        await callback.answer()
        await state.update_data(playing=False, expanded=True)
        await slider_manager.update_photo(
            index,
            paused=True,  # Слайдер на паузе
            expanded=True,
            user_id=user_id
        )
        return
    elif callback.data == "play":
        # Кнопка play нажата когда клавиатура открыта - закрываем клавиатуру и запускаем автопроигрывание
        await callback.answer()
        await state.update_data(playing=True, expanded=False)
        
        # Сразу переходим на следующий слайд
        current_index = data["index"]
        next_index = (current_index + 1) % len(media_list)
        logger.debug(f"Play pressed: current_index={current_index}, next_index={next_index}, total_slides={len(media_list)}")
        await state.update_data(index=next_index, cycle_count=1)
        await slider_manager.update_photo(
            next_index,
            paused=False,
            expanded=False,
            user_id=user_id
        )
        await asyncio.create_task(slider_manager.autoplay_slideshow())
        return

    await callback.answer()


@router.callback_query(F.data == "edit_product")
async def edit_product_from_slider(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    product_id = data.get("product_ids")[data.get("index")] if data.get("product_ids") else None

    if not product_id:
        await callback.answer("Не удалось определить товар для редактирования")
        return

    chat_id = callback.message.chat.id
    message_manager = MessageManager(callback.bot, state, chat_id)

    # Сохраняем ID старого сообщения для правильной очистки
    old_message_id = callback.message.message_id
    await state.update_data(old_slider_message_id=old_message_id)

    # Открываем карточку товара
    await state.set_state(StateEditProduct.editing)
    await state.update_data(product_id=product_id)
    
    # send_product_card сама определит, нужно ли edit или send
    await send_product_card(chat_id, product_id, state, message_manager)

    await callback.answer()


@router.callback_query(F.data.startswith("detail_view:"))
async def handle_detail_view(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Детальніше' в слайдере (универсально для всех типов медиа)"""
    try:
        product_id = int(callback.data.split(":")[1])
        chat_id = callback.message.chat.id
        message_manager = MessageManager(bot, state, chat_id)

        # Сохраняем контекст основного слайдера, чтобы вернуться к нему
        slider_data = await state.get_data()
        original_media_list = slider_data.get("media_list", [])
        original_product_ids = slider_data.get("product_ids", [])
        
        # Получаем все медиа товара
        media_list = data_base.get_product_media(product_id)
        
        if not media_list:
            await callback.answer("⚠️ У цього товару немає медіа")
            return
        
        # Получаем информацию о товаре
        product = data_base.sql_get_product(product_id)
        if not product:
            await callback.answer("⚠️ Товар не знайдено")
            return
        
        # Записываем просмотр товара типа 'single'
        user_id = callback.from_user.id
        view_tracker.quick_view(
            user_id=user_id,
            product_id=product_id,
            view_type='single'
        )
        
        # Создаем детальное описание для первого медиа
        detail_caption = await create_detail_caption(product, product_id, 0)
        
        # Получаем file_id и тип первого медиа
        first_media = media_list[0]
        file_id = first_media[1]
        media_type = first_media[2]
        
        # Универсальный выбор InputMedia*
        if media_type == "photo":
            input_media = InputMediaPhoto(media=file_id, caption=detail_caption)
        elif media_type == "video":
            input_media = InputMediaVideo(media=file_id, caption=detail_caption)
        elif media_type == "document":
            input_media = InputMediaDocument(media=file_id, caption=detail_caption)
        elif media_type == "audio":
            input_media = InputMediaAudio(media=file_id, caption=detail_caption)
        else:
            input_media = InputMediaPhoto(media=file_id, caption=detail_caption)
        
        try:
            await callback.message.edit_media(
                media=input_media,
                reply_markup=get_product_detail_keyboard(product_id, 0, len(media_list), callback.from_user.id)
            )
        except TelegramBadRequest as e:
            logger.warning(f"Failed to edit message: {e}")
            # Если не удалось отредактировать, используем универсальный метод MessageManager
            await message_manager.send_media_message(
                media_type=media_type,
                file=file_id,
                caption=detail_caption,
                reply_markup=get_product_detail_keyboard(product_id, 0, len(media_list), callback.from_user.id)
            )
        
        # Сохраняем состояние детального просмотра
        await state.set_state(DetailViewState.viewing)
        await state.update_data(
            detail_product_id=product_id,
            detail_media_list=media_list,
            detail_current_index=0,
            detail_product=product,
            # Сохраняем данные основного слайдера
            slider_media_list=original_media_list,
            slider_product_ids=original_product_ids
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error in handle_detail_view: {e}")
        await callback.answer("⚠️ Помилка при відкритті деталей")


@router.callback_query(F.data.startswith("detail_prev:"), StateFilter(DetailViewState.viewing))
async def handle_detail_prev(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Предыдущее медиа' в детальном просмотре (универсально)"""
    try:
        parts = callback.data.split(":")
        product_id = int(parts[1])
        current_index = int(parts[2])
        data = await state.get_data()
        media_list = data.get("detail_media_list", [])
        product = data.get("detail_product")
        if not media_list or current_index <= 0:
            await callback.answer("Це перше медіа", show_alert=False)
            return
        new_index = current_index - 1
        file_id = media_list[new_index][1]
        media_type = media_list[new_index][2]
        detail_caption = await create_detail_caption(product, product_id, new_index)
        chat_id = callback.message.chat.id
        message_manager = MessageManager(bot, state, chat_id)
        try:
            if media_type == "photo":
                input_media = InputMediaPhoto(media=file_id, caption=detail_caption)
            elif media_type == "video":
                input_media = InputMediaVideo(media=file_id, caption=detail_caption)
            elif media_type == "document":
                input_media = InputMediaDocument(media=file_id, caption=detail_caption)
            elif media_type == "audio":
                input_media = InputMediaAudio(media=file_id, caption=detail_caption)
            else:
                input_media = InputMediaPhoto(media=file_id, caption=detail_caption)
            await message_manager.edit_media(
                media=input_media,
                reply_markup=get_product_detail_keyboard(product_id, new_index, len(media_list), callback.from_user.id)
            )
        except TelegramBadRequest as e:
            logger.warning(f"Failed to edit message: {e}")
            await message_manager.send_media_message(
                media_type=media_type,
                file=file_id,
                caption=detail_caption,
                reply_markup=get_product_detail_keyboard(product_id, new_index, len(media_list), callback.from_user.id)
            )
        await state.update_data(detail_current_index=new_index)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in handle_detail_prev: {e}")
        await callback.answer("⚠️ Помилка при навігації")


@router.callback_query(F.data.startswith("detail_next:"), StateFilter(DetailViewState.viewing))
async def handle_detail_next(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Следующее медиа' в детальном просмотре (универсально)"""
    try:
        parts = callback.data.split(":")
        product_id = int(parts[1])
        current_index = int(parts[2])
        data = await state.get_data()
        media_list = data.get("detail_media_list", [])
        product = data.get("detail_product")
        if not media_list or current_index >= len(media_list) - 1:
            await callback.answer("Це останнє медіа", show_alert=False)
            return
        new_index = current_index + 1
        file_id = media_list[new_index][1]
        media_type = media_list[new_index][2]
        detail_caption = await create_detail_caption(product, product_id, new_index)
        chat_id = callback.message.chat.id
        message_manager = MessageManager(bot, state, chat_id)
        try:
            if media_type == "photo":
                input_media = InputMediaPhoto(media=file_id, caption=detail_caption)
            elif media_type == "video":
                input_media = InputMediaVideo(media=file_id, caption=detail_caption)
            elif media_type == "document":
                input_media = InputMediaDocument(media=file_id, caption=detail_caption)
            elif media_type == "audio":
                input_media = InputMediaAudio(media=file_id, caption=detail_caption)
            else:
                input_media = InputMediaPhoto(media=file_id, caption=detail_caption)
            await message_manager.edit_media(
                media=input_media,
                reply_markup=get_product_detail_keyboard(product_id, new_index, len(media_list), callback.from_user.id)
            )
        except TelegramBadRequest as e:
            logger.warning(f"Failed to edit message: {e}")
            await message_manager.send_media_message(
                media_type=media_type,
                file=file_id,
                caption=detail_caption,
                reply_markup=get_product_detail_keyboard(product_id, new_index, len(media_list), callback.from_user.id)
            )
        await state.update_data(detail_current_index=new_index)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in handle_detail_next: {e}")
        await callback.answer("⚠️ Помилка при навігації")


@router.callback_query(F.data.startswith("detail_back_to_slider:"), StateFilter(DetailViewState.viewing))
async def handle_detail_back_to_slider(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Вернуться к слайдеру' (универсально для всех типов медиа)"""
    try:
        product_id = int(callback.data.split(":")[1])
        chat_id = callback.message.chat.id
        message_manager = MessageManager(bot, state, chat_id)
        # Получаем исходные данные слайдера
        slider_data = await state.get_data()
        media_list = slider_data.get("slider_media_list", [])
        product_ids = slider_data.get("slider_product_ids", [])
        if not media_list:
            await callback.answer("⚠️ Слайдер не знайдено")
            return
        # Находим индекс товара в слайдере
        try:
            slider_index = product_ids.index(product_id)
        except ValueError:
            slider_index = 0
        await state.update_data(index=slider_index)
        # Синхронизируем корзину в FSM при возврате к слайдеру
        user_id = callback.from_user.id
        cart_items = data_base.get_cart(user_id)
        await state.update_data(cart_items=cart_items)
        media_info = media_list[slider_index]
        file_id = media_info.get("path") or media_info.get("file_id")
        media_type = media_info.get("media_type", "photo")
        # Получаем expanded и другие данные из состояния
        expanded = slider_data.get("expanded", True)
        slider_source = slider_data.get("slider_source", "main")
        slider_breadcrumbs = slider_data.get('slider_breadcrumbs', '')
        
        # Создаем экземпляр SliderManager для получения caption
        slider_manager = SliderManager(message_manager, state)
        caption = await slider_manager.get_full_slider_caption(
            product_id,
            user_id,
            cart_items=cart_items,
            show_cart_block=expanded,
            source=slider_source,
            breadcrumbs=slider_breadcrumbs,
            total_items=len(media_list),
            index=slider_index
        )
        # Универсальный выбор InputMedia*
        if media_type == "photo":
            input_media = InputMediaPhoto(media=file_id, caption=caption)
        elif media_type == "video":
            input_media = InputMediaVideo(media=file_id, caption=caption)
        elif media_type == "document":
            input_media = InputMediaDocument(media=file_id, caption=caption)
        elif media_type == "audio":
            input_media = InputMediaAudio(media=file_id, caption=caption)
        else:
            input_media = InputMediaPhoto(media=file_id, caption=caption)
        # Проверяем, находится ли товар в избранном
        is_favorite = False
        if user_id and product_id and product_id > 0:
            is_favorite = data_base.is_product_in_favorites(user_id, product_id)
        
        show_sizes_for_product = slider_data.get('show_sizes_for_product')

        try:
            await callback.message.edit_media(
                media=input_media,
                reply_markup=get_slider_keyboard(
                    expanded=True,
                    index=slider_index,
                    total=len(media_list),
                    user_id=user_id,
                    is_favorite=is_favorite,
                    product_id=product_id,
                    source=slider_source,  # <--- ДОБАВЛЕНО ЗДЕСЬ
                    selected_size=None,
                    selected_product_id=None,
                    show_sizes_for_product=show_sizes_for_product,
                    breadcrumbs=slider_breadcrumbs
                )
            )
        except TelegramBadRequest as e:
            logger.warning(f"Failed to edit message: {e}")
            await message_manager.send_media_message(
                media_type=media_type,
                file=file_id,
                caption=caption,
                reply_markup=get_slider_keyboard(
                    expanded=True,
                    index=slider_index,
                    total=len(media_list),
                    user_id=user_id,
                    is_favorite=is_favorite,
                    product_id=product_id,
                    source=slider_source,  # <--- И ЗДЕСЬ ТОЖЕ
                    selected_size=None,
                    selected_product_id=None,
                    show_sizes_for_product=show_sizes_for_product,
                    breadcrumbs=slider_breadcrumbs
                )
            )
        # Восстанавливаем основной список медиа в состояние
        await state.update_data(
            media_list=media_list,
            product_ids=product_ids
        )
        await state.set_state("slider_viewing")
        await callback.answer("← Повернувся до слайдера")
    except Exception as e:
        logger.error(f"Error in handle_detail_back_to_slider: {e}")
        await callback.answer("⚠️ Помилка при поверненні")





async def create_detail_caption(product: dict, product_id: int, photo_index: int) -> str:
    """Создает детальное описание товара для конкретного фото"""
    try:
        from utils.functions import get_euro_exchange_rate

        # Получаем Доступні розміри
        available_sizes = data_base.get_available_sizes(product_id)
        
        # Формируем строку с размерами
        sizes_text = "Доступні розміри:\n"
        if available_sizes:
            valid_sizes = {size: qty for size, qty in available_sizes.items() if qty > 0}
            jacket_sizes = [
                f"{size}" if valid_sizes[size] == 1 else f"{size}({valid_sizes[size]})"
                for size in [j.value for j in JacketSizes] if size in valid_sizes
            ]
            jersey_sizes = [
                f"{size.upper()}" if valid_sizes[size] == 1 else f"{size.upper()}({valid_sizes[size]})"
                for size in [j.value for j in JerseySizes] if size in valid_sizes
            ]
            jeans_sizes = [
                f"{size}" if valid_sizes[size] == 1 else f"{size}({valid_sizes[size]})"
                for size in [j.value for j in JeansSizes] if size in valid_sizes
            ]
            sizes_parts = []
            if jacket_sizes: sizes_parts.append(", ".join(jacket_sizes))
            if jersey_sizes: sizes_parts.append(", ".join(jersey_sizes))
            if jeans_sizes: sizes_parts.append(", ".join(jeans_sizes))
            sizes_text += " | ".join(sizes_parts) if sizes_parts else "нет"
        else:
            sizes_text += "нет"

        # Рассчитываем цену со скидкой
        discount_price = round(product['sale_price'] - (product['sale_price'] * product['discount'] / 100), 2)
        
        # Создаем упрощенное описание
        detail_caption = ""
        
        # Получаем caption из базы данных для конкретного фото
        media_list = data_base.get_product_media(product_id)
        if media_list and photo_index < len(media_list):
            photo_caption = media_list[photo_index][4]  # caption из [id, file_id, type, is_main, caption]
            if photo_caption and photo_caption.strip():  # Проверяем что caption не None и не пустая строка
                detail_caption += f"""<blockquote>{photo_caption}</blockquote>"""
        
        # Добавляем цену
        detail_caption += f"\n\n<code>Ціна: {product['sale_price']} €"
        
        if product['discount'] != 0:
            detail_caption += f"""
Знижка: {product['discount']}%
Ціна зі знижкою: {discount_price} € * {get_euro_exchange_rate()} = {round(discount_price * get_euro_exchange_rate())} грн.</code>"""
        else:
            detail_caption += f""" * {get_euro_exchange_rate()} = {round(product['sale_price'] * get_euro_exchange_rate())} грн.</code>"""
        
        # Добавляем размеры
        detail_caption += f"\n\n<code>{sizes_text}</code>"
        
        return detail_caption
        
    except Exception as e:
        logger.error(f"Error creating detail caption: {e}")
        return f"⚠️ Помилка при створенні опису"


@router.callback_query(F.data == "no_action")
async def handle_no_action(callback: CallbackQuery):
    """Обработчик для кнопок без действия (заглушки)"""
    await callback.answer()

@router.callback_query(NavigationCallback.filter(F.action == "main"), StateFilter("slider_viewing"))
async def handle_close_slider_from_cart(callback: CallbackQuery, state: FSMContext):
    """Обработчик возврата из слайдера корзины на главную (breadcrumbs=cart, source=cart)."""
    data = await state.get_data()
    breadcrumbs = data.get("slider_breadcrumbs", "")
    source = data.get("slider_source", "")
    chat_id = callback.message.chat.id
    message_manager = MessageManager(bot, state, chat_id)
    if breadcrumbs == "cart" and source == "cart":
        # Полный сброс состояния, чтобы не было ни одного breadcrumbs/filters
        await state.clear()
        callback_data = NavigationCallback(action="main", current_level="main", breadcrumbs="")
        await process_main_menu(callback, callback_data, state, message_manager)
        await callback.answer("← Повернувся до головного меню")
        return
    await callback.answer()


@router.callback_query(F.data.startswith("add_to_cart:"))
async def handle_add_to_cart(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    """
    Обработчик кнопки 'Добавить в корзину'.
    Добавляет товар в корзину пользователя через data_base.add_to_cart.
    """
    try:
        user_id = callback.from_user.id
        parts = callback.data.split(":")
        product_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        if not product_id:
            await callback.answer("Ошибка: не удалось определить товар", show_alert=True)
            return
        data = await state.get_data()
        size_value = data.get("selected_size") or data.get("size")
        data_base.add_to_cart(user_id=user_id, product_id=product_id, size_value=size_value, quantity=1)
        
        # === ОБНОВЛЯЕМ ДАННЫЕ О КОРЗИНЕ В FSM ===
        try:
            cart_data = data.get("cart_data", {})
            # Обновляем статус корзины для данного товара
            cart_data[product_id] = True  # Товар теперь в корзине
            await state.update_data(cart_data=cart_data)
            logger.debug(f"handle_add_to_cart: updated cart_data for product_id={product_id}, new_status=True")
        except Exception as e:
            logger.error(f"Error updating cart_data in FSM: {e}")
        
        # Синхронизируем корзину в FSM
        await state.update_data(cart_items=data_base.get_cart(user_id))
        # Проверяем, есть ли товар в корзине (должен быть после добавления)
        cart_items = data_base.get_cart(user_id)
        is_in_cart = any(item["product_id"] == product_id for item in cart_items)
        from keyboards.kb import get_slider_keyboard
        # Получаем параметры для клавиатуры из состояния
        index = data.get("index", 0)
        total = len(data.get("media_list", []))
        is_favorite = False
        if hasattr(data_base, 'is_product_in_favorites'):
            is_favorite = data_base.is_product_in_favorites(user_id, product_id)
        
        # Обновляем слайдер корзины с новым списком
        try:
            data = await state.get_data()
            slider_source = data.get("slider_source", "main")
            # Обновляем текущий слайд с новой клавиатурой
            try:
                data = await state.get_data()
                media_list = data.get("media_list", [])
                product_ids = data.get("product_ids", [])
                current_index = data.get("index", 0)
                expanded = data.get("expanded", True)
                if media_list and product_ids and current_index < len(product_ids):
                    slider_manager = SliderManager(manager, state)
                    await slider_manager.update_photo(
                        current_index,
                        paused=not data.get("playing", False),
                        expanded=expanded,
                        user_id=user_id
                    )
            except Exception as e:
                logger.error(f"Error updating slider after cart change: {e}")
                pass
        except Exception as e:
            logger.error(f"Error updating slider after cart change: {e}")
            pass
        
        await callback.answer()
    except Exception as e:
        print(f"[ADD TO CART ERROR] {e}")
        await callback.answer("Ошибка при добавлении в корзину", show_alert=True)

@router.callback_query(F.data.startswith("remove_from_cart:"))
async def handle_remove_from_cart(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    """
    Обработчик кнопки 'Удалить из корзины'.
    Удаляет весь товар из корзины (все размеры) и возвращает кнопку ➕.
    """
    try:
        user_id = callback.from_user.id
        parts = callback.data.split(":")
        product_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        if not product_id:
            await callback.answer("Ошибка: не удалось определить товар", show_alert=True)
            return
        
        # Удаляем весь товар из корзины (все размеры)
        data_base.remove_from_cart(user_id=user_id, product_id=product_id, size_value=None, quantity=1000)
        
        # === ОБНОВЛЯЕМ ДАННЫЕ О КОРЗИНЕ В FSM ===
        try:
            data = await state.get_data()
            cart_data = data.get("cart_data", {})
            # Обновляем статус корзины для данного товара
            cart_data[product_id] = False  # Товар больше не в корзине
            await state.update_data(cart_data=cart_data)
            logger.debug(f"handle_remove_from_cart: updated cart_data for product_id={product_id}, new_status=False")
        except Exception as e:
            logger.error(f"Error updating cart_data in FSM: {e}")
        
        # Синхронизируем корзину в FSM
        await state.update_data(cart_items=data_base.get_cart(user_id))
        
        # Обновляем текущий слайд с новой клавиатурой
        try:
            data = await state.get_data()
            media_list = data.get("media_list", [])
            product_ids = data.get("product_ids", [])
            current_index = data.get("index", 0)
            expanded = data.get("expanded", True)
            if media_list and product_ids and current_index < len(product_ids):
                slider_manager = SliderManager(manager, state)
                await slider_manager.update_photo(
                    current_index,
                    paused=not data.get("playing", False),
                    expanded=expanded,
                    user_id=user_id
                )
        except Exception as e:
            logger.error(f"Error updating slider after cart change: {e}")
            pass
        
        await callback.answer("Товар удален из корзины")
    except Exception as e:
        print(f"[REMOVE FROM CART ERROR] {e}")
        await callback.answer("Ошибка при удалении из корзини", show_alert=True)

@router.callback_query(F.data.startswith("show_sizes:"))
async def handle_show_sizes(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    """
    Обработчик кнопки ➕ - показывает размеры товара.
    При повторном нажатии закрывает выбор размеров.
    """
    try:
        user_id = callback.from_user.id
        parts = callback.data.split(":")
        product_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        
        if not product_id:
            await callback.answer("Ошибка: не удалось определить товар", show_alert=True)
            return
        
        # Получаем текущее состояние
        data = await state.get_data()
        current_show_sizes = data.get("show_sizes_for_product")
        
        # Если размеры уже показаны для этого товара - закрываем их
        if current_show_sizes == product_id:
            await state.update_data(
                show_sizes_for_product=None,
                selected_size=None,
                selected_product_id=None
            )
            await callback.answer("Выбор размеров закрыт")
        else:
            # Показываем размеры для нового товара
            await state.update_data(
                show_sizes_for_product=product_id,
                selected_size=None,
                selected_product_id=None
            )
            await callback.answer("Выберите размер")
        
        # Обновляем слайдер
        index = data.get("index", 0)
        
        # Создаем менеджеры
        message_manager = MessageManager(callback.bot, state, callback.message.chat.id)
        slider_manager = SliderManager(message_manager, state)
        
        # Обновляем слайд
        await slider_manager.update_photo(
            index=index,
            paused=False,
            expanded=True,
            user_id=user_id
        )
        
    except Exception as e:
        logger.error(f"Error in handle_show_sizes: {e}")
        await callback.answer("Ошибка при показе размеров", show_alert=True)


@router.callback_query(F.data.startswith("select_size:"))
async def handle_select_size(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    """
    Обработчик выбора размера.
    """
    try:
        user_id = callback.from_user.id
        parts = callback.data.split(":")
        product_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        size_value = parts[2] if len(parts) > 2 else None
        
        if not product_id:
            await callback.answer("Ошибка: не удалось определить товар", show_alert=True)
            return
        
        # Проверяем доступное количество для размера
        available_sizes = data_base.get_available_sizes(product_id)
        available_qty = available_sizes.get(size_value, 0) if size_value != "no_size" else 1
        
        if available_qty == 0 and size_value != "no_size":
            await callback.answer("Этот размер недоступен", show_alert=True)
            return
        
        # Если размеров больше 1, показываем выбор количества
        if available_qty > 1 and size_value != "no_size":
            await state.update_data(
                selected_size=size_value,
                selected_product_id=product_id
            )
            
            # Обновляем слайдер с показом количества
            data = await state.get_data()
            index = data.get("index", 0)
            
            message_manager = MessageManager(callback.bot, state, callback.message.chat.id)
            slider_manager = SliderManager(message_manager, state)
            
            await slider_manager.update_photo(
                index=index,
                paused=False,
                expanded=True,
                user_id=user_id
            )
            
            await callback.answer(f"Выберите количество для размера {size_value}")
            return
        
        # Если размеров 1 или "без размера", добавляем сразу в корзину
        quantity = 1
        if size_value == "no_size":
            size_value = None
        
        # Добавляем в корзину
        data_base.add_to_cart(user_id=user_id, product_id=product_id, size_value=size_value, quantity=quantity)
        
        # Обновляем FSM
        data = await state.get_data()
        cart_data = data.get("cart_data", {})
        cart_data[product_id] = True
        await state.update_data(
            cart_data=cart_data, 
            cart_items=data_base.get_cart(user_id),
            show_sizes_for_product=None  # Скрываем размеры после добавления
        )
        
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
            else:
                # Обычное поведение для других слайдеров
                media_list = data.get("media_list", [])
                product_ids = data.get("product_ids", [])
                current_index = data.get("index", 0)
                expanded = data.get("expanded", True)
                if media_list and product_ids and current_index < len(product_ids):
                    slider_manager = SliderManager(manager, state)
                    await slider_manager.update_photo(
                        current_index,
                        paused=not data.get("playing", False),
                        expanded=expanded,
                        user_id=user_id
                    )
        except Exception as e:
            logger.error(f"Error updating slider after cart change: {e}")
            pass
        
        size_text = size_value if size_value else "без размера"
        await callback.answer(f"Добавлено в корзину: {size_text}")
        
    except Exception as e:
        logger.error(f"Error in handle_select_size: {e}")
        await callback.answer("Ошибка при выборе размера", show_alert=True)


@router.callback_query(F.data.startswith("select_quantity:"))
async def handle_select_quantity(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    """
    Обработчик выбора количества.
    """
    try:
        user_id = callback.from_user.id
        parts = callback.data.split(":")
        product_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        size_value = parts[2] if len(parts) > 2 else None
        quantity = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1
        
        if not product_id or not size_value:
            await callback.answer("Ошибка: не удалось определить параметры", show_alert=True)
            return
        
        # Проверяем доступное количество
        available_sizes = data_base.get_available_sizes(product_id)
        available_qty = available_sizes.get(size_value, 0)
        
        if quantity > available_qty:
            await callback.answer(f"Доступно только {available_qty} шт.", show_alert=True)
            return
        
        # Добавляем в корзину
        data_base.add_to_cart(user_id=user_id, product_id=product_id, size_value=size_value, quantity=quantity)

        # Обновляем FSM
        data = await state.get_data()
        cart_data = data.get("cart_data", {})
        cart_data[product_id] = True
        await state.update_data(cart_data=cart_data, cart_items=data_base.get_cart(user_id))

        # Очищаем состояние выбора размера и количества, чтобы закрыть панель
        await state.update_data(
            selected_size=None,
            selected_product_id=None,
            show_sizes_for_product=None  # <-- Вот это исправление
        )
        
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
            else:
                # Обычное поведение для других слайдеров
                media_list = data.get("media_list", [])
                product_ids = data.get("product_ids", [])
                current_index = data.get("index", 0)
                expanded = data.get("expanded", True)
                if media_list and product_ids and current_index < len(product_ids):
                    slider_manager = SliderManager(manager, state)
                    await slider_manager.update_photo(
                        current_index,
                        paused=not data.get("playing", False),
                        expanded=expanded,
                        user_id=user_id
                    )
        except Exception as e:
            logger.error(f"Error updating slider after cart change: {e}")
            pass
        
        await callback.answer(f"Добавлено в корзину: {size_value} - {quantity} шт.")
        
    except Exception as e:
        logger.error(f"Error in handle_select_quantity: {e}")
        await callback.answer("Ошибка при выборе количества", show_alert=True)


@router.callback_query(F.data.startswith("join_waitlist:"))
async def handle_join_waitlist(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик кнопки 'Встать в очередь' для недоступного товара.
    """
    try:
        user_id = callback.from_user.id
        parts = callback.data.split(":")
        product_id = int(parts[1])
        size_value = parts[2]

        was_added = data_base.add_to_waiting_list(user_id, product_id, size_value)

        if was_added:
            await callback.answer("✅ Чудово! Ми повідомимо вас, як тільки товар з'явиться.", show_alert=True)
        else:
            await callback.answer("☑️ Ви вже у списку очікування на цей товар.", show_alert=True)

    except (IndexError, ValueError) as e:
        logger.error(f"Error in handle_join_waitlist: Invalid callback data: {callback.data} - {e}")
        await callback.answer("Помилка. Не вдалося додати вас до списку очікування.", show_alert=True)
    except Exception as e:
        logger.error(f"Error in handle_join_waitlist: {e}")
        await callback.answer("Невідома помилка. Спробуйте пізніше.", show_alert=True)


from utils.functions import get_cart_block


@router.callback_query(F.data == "order_cart")
async def handle_order_cart(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    """
    Обработчик кнопки 'Оформить заказ' в слайдере корзины. Запрашивает подтверждение.
    """
    from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
    user_id = callback.from_user.id
    if not data_base.get_cart(user_id):
        await callback.answer("Ваш кошик порожній!", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Так", callback_data="order:confirm")
    builder.button(text="❌ Скасувати", callback_data="order:cancel")
    builder.adjust(2)

    cart_caption = get_cart_block(user_id)
    confirmation_text = "Ви впевнені, що хочете відправити замовлення?"
    full_caption = f"{cart_caption}\n\n{confirmation_text}"

    await manager.edit(
        full_caption,
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "order:confirm")
async def handle_confirm_order(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    """
    Обработчик подтверждения заказа.
    """
    user_id = callback.from_user.id
    cart_items = data_base.get_cart(user_id)

    if not cart_items:
        await callback.answer("Ваш кошик порожній!", show_alert=True)
        return

    try:
        # Рассчитываем скидку пользователя
        from utils.functions import calculate_cashback
        total_amount = sum(item['sale_price'] * item['quantity'] for item in cart_items)
        discount_info = calculate_cashback(user_id, total_amount)
        discount_amount = discount_info['discount']

        # Создаем заказ
        order_id = data_base.create_sale(user_id, cart_items, discount_amount)

        final_amount = total_amount - discount_amount


        # Получаем информацию о пользователе
        user_data = data_base.sql_get_user(user_id, 'first_name', 'last_name', 'user_name')

        if not user_data:
            # Случай 1: Пользователь не найден в БД (исправление критической ошибки)
            user_name = f"User {user_id}"
        else:
            # Распаковываем для читаемости
            first_name, last_name, username = user_data

            # Собираем имя из существующих частей
            name_parts = []
            if first_name:
                name_parts.append(first_name)
            if last_name:
                name_parts.append(last_name)

            if name_parts:
                # Случай 2: Есть имя и/или фамилия
                user_name = " ".join(name_parts)
            elif username:
                # Случай 3: Имени нет, но есть username
                user_name = username
            else:
                # Случай 4: Вообще ничего нет, используем ID
                user_name = f"User {user_id}"


        # Отправляем уведомления админам
        from services.notification_service import NotificationService
        from utils.loader import bot
        notification_service = NotificationService(bot)

        await notification_service.notify_new_order(
            order_id=order_id,
            user_id=user_id,
            total_amount=total_amount,
            items_count=len(cart_items),
            user_name=user_name,
            cart_items=cart_items
        )

        # Показываем подтверждение пользователю
        confirmation_text = (
            f"<blockquote>\n"
            f"✅ <b>Заказ #{order_id} оформлен!</b>\n\n"
            f"📦 Товары: {len(cart_items)} шт.\n"
            f"💰 Сумма: {total_amount:.2f} €\n"
            f"🎁 Скидка: {discount_amount:.2f} €\n"
            f"💳 К оплате: {final_amount:.2f} €\n\n"
            f"⏰ Ожидайте звонка для подтверждения заказа.\n"
            f"</blockquote>"
        )

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        close_button = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Закрыть", callback_data="delete_message")]
        ])
        await manager.edit(confirmation_text, reply_markup=close_button)
        await callback.answer("✅ Заказ успешно оформлен!")

    except Exception as e:
        logger.error(f"Ошибка оформления заказа: {e}")
        await callback.answer("❌ Ошибка оформления заказа", show_alert=True)


@router.callback_query(F.data == "order:cancel")
async def handle_cancel_order(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    """
    Обработчик отмены заказа. Возвращает пользователя в слайдер корзины.
    """
    try:
        user_id = callback.from_user.id
        data = await state.get_data()
        
        media_list = data.get("slider_media_list", [])
        product_ids = data.get("slider_product_ids", [])
        index = data.get("index", 0)

        if not media_list or not product_ids:
            await callback.answer("Не вдалося повернутися до кошика.", show_alert=True)
            await process_main_menu(callback, NavigationCallback(action="main", current_level="main", breadcrumbs=""), state, manager)
            return

        slider_manager = SliderManager(manager, state)
        await slider_manager.update_photo(
            index,
            paused=True,
            expanded=True,
            user_id=user_id
        )
        await callback.answer("Оформлення скасовано.")

    except Exception as e:
        logger.error(f"Error cancelling order: {e}")
        await callback.answer("Помилка при скасуванні.", show_alert=True)
