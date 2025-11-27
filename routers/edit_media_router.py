from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder

from data_base.models import data_base
from filters import IsAdmin
from fsm.states import StateEditMedia, StateEditProduct
from keyboards.kb import (
    media_grid_keyboard,
    media_actions_keyboard,
    confirm_delete_media_keyboard
)
from utils.message_manager import MessageManager
from utils.loader import bot
from utils import logger, admins

router = Router()
router.message.filter(IsAdmin(admin_ids=admins))


async def show_media_grid(chat_id: int, product_id: int, state: FSMContext, message_manager: MessageManager):
    """Показывает сетку медиа товара (универсально для всех типов медиа)"""
    try:
        # Получаем медиа товара
        media_list = data_base.get_product_media(product_id)
        
        if not media_list:
            # Если нет медиа, показываем сообщение с возможностью добавления
            await message_manager.send(
                "📷 У цього товару ще немає фотографій.\n\n"
                "➕ Натисніть 'Додати фото' щоб завантажити перше фото.",
                reply_markup=media_grid_keyboard(product_id, [])
            )
            await state.set_state(StateEditMedia.viewing)
            await state.update_data(product_id=product_id)
            return
        
        # Получаем главное медиа для отображения
        main_media = None
        for media in media_list:
            if media[3]:  # is_main
                main_media = media
                break
        if not main_media:
            main_media = media_list[0]  # Берем первое медиа если нет главного
        main_file_id = main_media[1]
        main_media_type = main_media[2]
        
        # Создаем описание
        caption = f"📷  Управління медіа товару ID {product_id}\n\n"
        caption += f"📊  Всього медіа: {len(media_list)}\n"
        caption += f"⭐️  Головне медіа: {'Встановлено' if any(m[3] for m in media_list) else 'Не встановлено'}\n\n"
        caption += "Інструкція:\n"
        caption += "• Натисніть на медіа для дій з ним\n"
        caption += "• ⭐️ - головне медіа\n"
        caption += "• ⬜️ - звичайне медіа\n"
        caption += "• ➕ - додати нове медіа"

        # Получаем текущий message_id из состояния через MessageManager
        current_msg_id = await message_manager.get_active_msg_id()

        if current_msg_id:
            try:
                # Универсальный выбор InputMedia*
                if main_media_type == "photo":
                    input_media = InputMediaPhoto(media=main_file_id, caption=caption)
                elif main_media_type == "video":
                    input_media = InputMediaVideo(media=main_file_id, caption=caption)
                elif main_media_type == "document":
                    input_media = InputMediaDocument(media=main_file_id, caption=caption)
                elif main_media_type == "audio":
                    input_media = InputMediaAudio(media=main_file_id, caption=caption)
                else:
                    input_media = InputMediaPhoto(media=main_file_id, caption=caption)
                await message_manager.edit_media(
                    media=input_media,
                    reply_markup=media_grid_keyboard(product_id, media_list),
                    message_id=current_msg_id
                )
                logger.info(f"Media grid message {current_msg_id} successfully edited")
            except TelegramBadRequest as e:
                logger.warning(f"Failed to edit media grid message {current_msg_id}: {e}")
                # Если не удалось редактировать, отправляем новое через MessageManager
                await send_new_media_grid_message(message_manager, main_file_id, main_media_type, caption, product_id, media_list, state)
        else:
            # Если нет текущего сообщения, отправляем новое через MessageManager
            await send_new_media_grid_message(message_manager, main_file_id, main_media_type, caption, product_id, media_list, state)

        await state.set_state(StateEditMedia.viewing)
        await state.update_data(product_id=product_id, media_list=media_list)

    except Exception as e:
        logger.error(f"Error showing media grid: {e}")
        await message_manager.send("⚠️ Помилка при відображенні медіа товару")


async def send_new_media_grid_message(message_manager: MessageManager, file_id: str, media_type: str, caption: str, product_id: int, media_list: list, state: FSMContext):
    """Отправляет новое сообщение с сеткой медиа через MessageManager (универсально)"""
    new_msg = await message_manager.send_media_message(
        media_type=media_type,
        file=file_id,
        caption=caption,
        reply_markup=media_grid_keyboard(product_id, media_list)
    )
    # MessageManager автоматически обновит active_msg_id при отправке сообщения
    # Никаких дополнительных обновлений не нужно


@router.callback_query(F.data.startswith("media_action:"), StateFilter(StateEditMedia.viewing))
async def handle_media_action(callback: CallbackQuery, state: FSMContext):
    """Обработчик действий с медиа"""
    await callback.answer()
    try:
        parts = callback.data.split(":")
        product_id = int(parts[1])
        media_id = int(parts[2])
        action = parts[3]

        chat_id = callback.message.chat.id
        message_manager = MessageManager(bot, state, chat_id)

        if action == "view":
            # Показать действия для конкретного медиа
            await show_media_actions(callback, product_id, media_id, state, message_manager)

        elif action == "add":
            # Начать добавление фото
            await start_add_media(callback, product_id, state, message_manager)

        elif action == "back":
            # Вернуться к редактированию товара
            await back_to_product_edit(callback, product_id, state, message_manager)

        elif action == "grid":
            # Вернуться к сетке
            await show_media_grid(chat_id, product_id, state, message_manager)

        elif action == "set_main":
            # Сделать фото главным
            await set_main_photo(callback, product_id, media_id, state, message_manager)

        elif action == "delete":
            # Показать подтверждение удаления
            await show_delete_confirmation(callback, product_id, media_id, state, message_manager)

        elif action == "edit_caption":
            # Начать редактирование caption
            await start_edit_caption(callback, product_id, media_id, state, message_manager)

        elif action == "confirm_delete":
            # Подтвердить удаление
            await confirm_delete_media(callback, product_id, media_id, state, message_manager)

        elif action == "cancel_delete":
            # Отменить удаление
            await show_media_grid(chat_id, product_id, state, message_manager)

    except Exception as e:
        logger.error(f"Error in handle_media_action: {e}")
        await callback.answer("⚠️ Помилка при обробці дії", show_alert=True)


@router.callback_query(F.data.startswith("media_action:"), StateFilter(StateEditMedia.confirming_delete))
async def handle_media_action_confirming(callback: CallbackQuery, state: FSMContext):
    """Обработчик действий с медиа в состоянии подтверждения удаления"""
    await callback.answer()
    try:
        parts = callback.data.split(":")
        product_id = int(parts[1])
        media_id = int(parts[2])
        action = parts[3]

        chat_id = callback.message.chat.id
        message_manager = MessageManager(bot, state, chat_id)

        if action == "confirm_delete":
            # Подтвердить удаление
            await confirm_delete_media(callback, product_id, media_id, state, message_manager)

        elif action == "cancel_delete":
            # Отменить удаление
            await show_media_grid(chat_id, product_id, state, message_manager)

    except Exception as e:
        logger.error(f"Error in handle_media_action_confirming: {e}")
        await callback.answer("⚠️ Помилка при обробці дії", show_alert=True)


@router.callback_query(F.data.startswith("media_action:"), StateFilter(StateEditMedia.editing_caption))
async def handle_media_action_editing_caption(callback: CallbackQuery, state: FSMContext):
    """Обработчик действий с медиа в состоянии редактирования caption"""
    await callback.answer()
    try:
        parts = callback.data.split(":")
        product_id = int(parts[1])
        media_id = int(parts[2])
        action = parts[3]

        chat_id = callback.message.chat.id
        message_manager = MessageManager(bot, state, chat_id)

        if action == "grid":
            # Вернуться к сетке
            await show_media_grid(chat_id, product_id, state, message_manager)

    except Exception as e:
        logger.error(f"Error in handle_media_action_editing_caption: {e}")
        await callback.answer("⚠️ Помилка при обробці дії", show_alert=True)


async def show_media_actions(callback: CallbackQuery, product_id: int, media_id: int, state: FSMContext, message_manager: MessageManager):
    """Показывает действия для конкретного медиа"""
    try:
        # Получаем информацию о медиа
        media_list = data_base.get_product_media(product_id)
        target_media = None

        for media in media_list:
            if media[0] == media_id:  # ID медиа
                target_media = media
                break

        if not target_media:
            await callback.answer("⚠️ Медіа не знайдено", show_alert=True)
            return

        # Получаем file_id и тип медиа
        file_id = target_media[1]
        media_type = target_media[2]
        is_main = target_media[3]

        # Создаем описание
        caption = f"📷 Фото {media_id}\n\n"
        caption += f"Статус: {'⭐️ Головне фото' if is_main else '⬜️ Звичайне фото'}\n"
        caption += f"Тип: {media_type}\n"
        if target_media[4]:  # caption
            caption += f"Підпис: {target_media[4]}\n"

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

        # Используем MessageManager для редактирования
        try:
            await message_manager.edit_media(
                media=input_media,
                reply_markup=media_actions_keyboard(product_id, media_id, is_main)
            )
            logger.info(f"Media actions message successfully edited")
        except TelegramBadRequest as e:
            logger.warning(f"Failed to edit media actions message: {e}")
            # Если не удалось редактировать, используем прямое редактирование
            await callback.message.edit_media(
                media=input_media,
                reply_markup=media_actions_keyboard(product_id, media_id, is_main)
            )

        await callback.answer()

    except Exception as e:
        logger.error(f"Error showing media actions: {e}")
        await callback.answer("⚠️ Помилка при відображенні дій", show_alert=True)


async def start_add_media(callback: CallbackQuery, product_id: int, state: FSMContext, message_manager: MessageManager):
    """Начинает процесс добавления медиа"""
    try:
        add_media_text = f"📷 Додавання фото до товару ID {product_id}\n\n"
        add_media_text += "📤 Завантажте фото або відео\n"
        add_media_text += "💡 Можна завантажити кілька файлів одразу\n\n"
        add_media_text += "❌ Для скасування натисніть 'Назад'"

        # Используем MessageManager для редактирования
        try:
            await message_manager.edit_photo_caption(
                caption=add_media_text,
                reply_markup=InlineKeyboardBuilder().button(
                    text="← Назад",
                    callback_data=f"media_action:{product_id}:0:grid"
                ).as_markup()
            )
            logger.info(f"Add media message successfully edited")
        except TelegramBadRequest as e:
            logger.warning(f"Failed to edit add media message: {e}")
            # Если не удалось редактировать, используем прямое редактирование
            await callback.message.edit_caption(
                caption=add_media_text,
                reply_markup=InlineKeyboardBuilder().button(
                    text="← Назад",
                    callback_data=f"media_action:{product_id}:0:grid"
                ).as_markup()
            )

        await state.set_state(StateEditMedia.adding_photos)
        await state.update_data(product_id=product_id, new_media=[])

        await callback.answer()

    except Exception as e:
        logger.error(f"Error starting add media: {e}")
        await callback.answer("⚠️ Помилка при додаванні медіа", show_alert=True)


@router.message(StateFilter(StateEditMedia.adding_photos))
async def handle_new_media(message: Message, state: FSMContext):
    """Обрабатывает загруженные медиа"""
    try:
        data = await state.get_data()
        product_id = data.get('product_id')

        if not product_id:
            await message.reply("⚠️ Помилка: ID товару не знайдено")
            return

        message_manager = MessageManager(bot, state, message.chat.id)
        new_media = data.get('new_media', [])

        # Обрабатываем фото
        if message.photo:
            file_id = message.photo[-1].file_id
            media_type = 'photo'
            caption = message.caption or ''

            # Добавляем в базу
            media_id = data_base.add_media_to_product(product_id, file_id, media_type, caption)
            new_media.append({
                'id': media_id,
                'file_id': file_id,
                'type': media_type,
                'caption': caption
            })

            # Отправляем временное сообщение (3 секунды)
            temp_msg = await message.reply(f"✅ Фото додано! ID: {media_id}")
            import asyncio
            await asyncio.sleep(3)
            try:
                await temp_msg.delete()
            except TelegramBadRequest:
                pass

        # Обрабатываем видео
        elif message.video:
            file_id = message.video.file_id
            media_type = 'video'
            caption = message.caption or ''

            # Добавляем в базу
            media_id = data_base.add_media_to_product(product_id, file_id, media_type, caption)
            new_media.append({
                'id': media_id,
                'file_id': file_id,
                'type': media_type,
                'caption': caption
            })

            # Отправляем временное сообщение (3 секунды)
            temp_msg = await message.reply(f"✅ Відео додано! ID: {media_id}")
            import asyncio
            await asyncio.sleep(3)
            try:
                await temp_msg.delete()
            except TelegramBadRequest:
                pass

        else:
            await message.reply("⚠️ Будь ласка, завантажте фото або відео")
            return

        # Обновляем состояние
        await state.update_data(new_media=new_media)

        # Удаляем сообщение пользователя
        try:
            await message.delete()
        except TelegramBadRequest:
            pass

        # Автоматически обновляем сетку через 1 секунду
        import asyncio
        await asyncio.sleep(1)
        await show_media_grid(message.chat.id, product_id, state, message_manager)

    except Exception as e:
        logger.error(f"Error handling new media: {e}")
        await message.reply("⚠️ Помилка при обробці медіа")


async def set_main_photo(callback: CallbackQuery, product_id: int, media_id: int, state: FSMContext, message_manager: MessageManager):
    """Устанавливает фото как главное"""
    try:
        data_base.set_main_photo(product_id, media_id)

        await callback.answer("✅ Фото встановлено як головне!")

        # Показываем обновленную сетку
        await show_media_grid(callback.message.chat.id, product_id, state, message_manager)

    except Exception as e:
        logger.error(f"Error setting main photo: {e}")
        await callback.answer("⚠️ Помилка при встановленні головного фото", show_alert=True)


async def show_delete_confirmation(callback: CallbackQuery, product_id: int, media_id: int, state: FSMContext, message_manager: MessageManager):
    """Показывает подтверждение удаления"""
    try:
        # Получаем информацию о медиа
        media_list = data_base.get_product_media(product_id)
        target_media = None

        for media in media_list:
            if media[0] == media_id:
                target_media = media
                break

        if not target_media:
            await callback.answer("⚠️ Медіа не знайдено", show_alert=True)
            return

        # Получаем file_id и тип медиа
        file_id = target_media[1]
        media_type = target_media[2]
        is_main = target_media[3]

        caption = f"⚠️ Підтвердження видалення\n\n"
        caption += f"Ви дійсно хочете видалити це медіа?\n\n"
        caption += f"ID: {media_id}\n"
        caption += f"Статус: {'⭐️ Головне фото' if is_main else '⬜️ Звичайне фото'}\n"
        caption += f"Тип: {media_type}\n\n"
        caption += "❗️ Ця дія незворотна!"

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

        # Используем MessageManager для редактирования
        try:
            await message_manager.edit_media(
                media=input_media,
                reply_markup=confirm_delete_media_keyboard(product_id, media_id)
            )
            logger.info(f"Delete confirmation message successfully edited")
        except TelegramBadRequest as e:
            logger.warning(f"Failed to edit delete confirmation message: {e}")
            # Если не удалось редактировать, используем прямое редактирование
            await callback.message.edit_media(
                media=input_media,
                reply_markup=confirm_delete_media_keyboard(product_id, media_id)
            )

        await state.set_state(StateEditMedia.confirming_delete)
        await callback.answer()

    except Exception as e:
        logger.error(f"Error showing delete confirmation: {e}")
        await callback.answer("⚠️ Помилка при підтвердженні видалення", show_alert=True)


async def confirm_delete_media(callback: CallbackQuery, product_id: int, media_id: int, state: FSMContext, message_manager: MessageManager):
    """Подтверждает удаление медиа"""
    try:
        # Удаляем медиа
        deleted = data_base.delete_product_media(media_id)

        if deleted:
            await callback.answer("✅ Фото видалено!")
        else:
            await callback.answer("⚠️ Фото не знайдено", show_alert=True)
            return

        # Показываем обновленную сетку
        await show_media_grid(callback.message.chat.id, product_id, state, message_manager)

    except Exception as e:
        logger.error(f"Error confirming delete media: {e}")
        await callback.answer("⚠️ Помилка при видаленні фото", show_alert=True)


async def back_to_product_edit(callback: CallbackQuery, product_id: int, state: FSMContext, message_manager: MessageManager):
    """Возвращается к редактированию товара"""
    try:
        # Сохраняем слайдер-данные, если они есть
        slider_keys = ["photo_list", "product_ids", "media_list", "index", "old_slider_msg_id"]
        data = await state.get_data()
        slider_data = {k: v for k, v in data.items() if k in slider_keys}

        from routers.edit_product_router import send_product_card

        await state.set_state(StateEditProduct.editing)
        await state.update_data(product_id=product_id, **slider_data)

        await send_product_card(callback.message.chat.id, product_id, state, message_manager)
        await callback.answer("← Повернувся до редагування товару")
    except Exception as e:
        logger.error(f"Error back to product edit: {e}")
        await callback.answer("⚠️ Помилка при поверненні", show_alert=True)


async def start_edit_caption(callback: CallbackQuery, product_id: int, media_id: int, state: FSMContext, message_manager: MessageManager):
    """Начинает процесс редактирования caption"""
    try:
        # Получаем информацию о медиа
        media_list = data_base.get_product_media(product_id)
        target_media = None

        for media in media_list:
            if media[0] == media_id:
                target_media = media
                break

        if not target_media:
            await callback.answer("⚠️ Медіа не знайдено", show_alert=True)
            return

        # Получаем текущий caption
        current_caption = target_media[4]

        # Создаем сообщение для редактирования
        edit_caption_text = f"📷 Редагування підпису фото ID {media_id}\n\n"
        edit_caption_text += f"Поточний підпис: {current_caption}\n"
        edit_caption_text += "📝 Введіть новий підпис:"
        
        # Используем MessageManager для редактирования
        try:
            await message_manager.edit_photo_caption(
                caption=edit_caption_text,
                reply_markup=InlineKeyboardBuilder().button(
                    text="← Назад",
                    callback_data=f"media_action:{product_id}:{media_id}:grid"
                ).as_markup()
            )
            logger.info(f"Edit caption message successfully edited")
        except TelegramBadRequest as e:
            logger.warning(f"Failed to edit edit caption message: {e}")
            # Если не удалось редактировать, используем прямое редактирование
            await callback.message.edit_caption(
                caption=edit_caption_text,
                reply_markup=InlineKeyboardBuilder().button(
                    text="← Назад",
                    callback_data=f"media_action:{product_id}:{media_id}:grid"
                ).as_markup()
            )
        
        await state.set_state(StateEditMedia.editing_caption)
        await state.update_data(product_id=product_id, media_id=media_id, current_caption=current_caption)
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error starting edit caption: {e}")
        await callback.answer("⚠️ Помилка при редагуванні підпису", show_alert=True)


@router.message(StateFilter(StateEditMedia.editing_caption))
async def handle_edited_caption(message: Message, state: FSMContext):
    """Обрабатывает введенный пользователем новый caption"""
    try:
        data = await state.get_data()
        product_id = data.get('product_id')
        media_id = data.get('media_id')
        current_caption = data.get('current_caption')
        
        if not product_id or not media_id:
            await message.reply("⚠️ Помилка: ID товару або медіа не знайдено")
            return
        
        message_manager = MessageManager(bot, state, message.chat.id)
        new_caption = message.text.strip()
        
        if not new_caption:
            await message.reply("⚠️ Помилка: Новий підпис не може бути порожнім")
            return
        
        # Обновляем данные в базе
        updated = data_base.update_media_caption(media_id, new_caption)
        
        if not updated:
            await message.reply("⚠️ Помилка: Не вдалося оновити підпис")
            return
        
        # Удаляем сообщение пользователя
        try:
            await message.delete()
        except TelegramBadRequest:
            pass
        
        # Отправляем временное сообщение об успехе (3 секунды)
        temp_msg = await message.answer("✅ Підпис фото успішно оновлено!")
        import asyncio
        await asyncio.sleep(3)
        try:
            await temp_msg.delete()
        except TelegramBadRequest:
            pass
        
        # Показываем обновленную сетку
        await show_media_grid(message.chat.id, product_id, state, message_manager)
        
    except Exception as e:
        logger.error(f"Error handling edited caption: {e}")
        await message.reply("⚠️ Помилка при редагуванні підпису") 