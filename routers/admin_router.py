
"""
Роутер для административных команд.
Обрабатывает:
- Подтверждение пользователей
- Рассылку сообщений
- Другие административные функции
"""

import asyncio
import re
from datetime import datetime

def get_formatted_date() -> str:
    """Возвращает текущую дату в формате 'ДД.ММ.ГГГГ'."""
    return datetime.now().strftime("%d.%m.%Y")
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, MessageEntity
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from data_base.models import data_base
from fsm.states import StateMailing
from utils import admins, safe_delete_message, logger, viewers, vip_users
from utils.loader import bot
from utils.lexicon import LOYALTY_RELAUNCH_ANNOUNCEMENT
from utils.message_manager import MessageManager
from routers.admin_panel_router import show_admin_panel

router = Router(name="admin_router")


async def cleanup_admin_interface(message: Message) -> None:
    """
    Очищает интерфейс администратора после выполнения команды.

    Args:
        message: Сообщение, которое нужно удалить
    """
    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Failed to delete admin message: {e}")


@router.message(F.text.startswith("/approve_"))
async def approve_user(message: Message) -> None:
    """
    Активирует пользователя по команде администратора.

    Параметры:
        message: Сообщение с командой в формате /approve_<user_id>
    """
    if message.from_user.id not in admins:
        return

    try:
        user_id = int(message.text.split("_")[1])

        # Активируем пользователя
        data_base.activate_user(user_id)
        data_base.set_user_level(user_id, 'bronze')
        logger.info(f"Admin {message.from_user.id} approved user {user_id}")

        # Уведомление администратора
        confirmation_msg = await message.answer(f"✅ Користувач {user_id} схвалений.")
        await cleanup_admin_interface(message)
        await safe_delete_message(confirmation_msg, 4)

        # Создаем временную клавиатуру для очистки предыдущего интерфейса
        builder = ReplyKeyboardBuilder()
        builder.add(KeyboardButton(text="blank msg"))
        await message.answer(
            "blank msg",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=builder.export(),
                resize_keyboard=True,
                one_time_keyboard=False
            )
        )

        # Уведомляем пользователя
        welcome_msg = await message.bot.send_message(
            user_id,
            "🎉 Ваш доступ підтверджено!\n✅ Ласкаво просимо!"
        )
        await safe_delete_message(welcome_msg, 50)

    except (IndexError, ValueError) as e:
        error_msg = "Неправильний формат команди. Використовуйте /approve_<user_id>"
        logger.error(f"Approval error: {e}")
        await message.answer(error_msg)
    except Exception as e:
        logger.error(f"User approval failed: {e}")
        await message.answer(f"❌ Помилка: {e}")


@router.callback_query(F.data.startswith("confirm_"))
async def confirm_user(callback: CallbackQuery):
    # Подтверждение пользователей
    pass


@router.callback_query(F.data.startswith("reserve_order:"))
async def handle_reserve_order(callback: CallbackQuery):
    """
    Обрабатывает нажатие кнопки "Резерв" в уведомлении о новом заказе.
    """
    try:
        order_id = int(callback.data.split(":")[1])
        admin_id = callback.from_user.id

        if admin_id not in admins:
            await callback.answer("У вас нет прав для этого действия.", show_alert=True)
            return

        try:
            success = data_base.create_reservation_from_order(order_id, admin_id)
            if success:
                await callback.answer(f"Заказ #{order_id} успешно зарезервирован.", show_alert=True)
                # Обновляем сообщение, добавляя кнопку "Продажа"
                new_text = callback.message.text + "\n\n<b>Статус:</b> ✅ Зарезервовано"
                builder = InlineKeyboardBuilder()
                builder.button(text="Закрыть", callback_data="delete_message")
                await callback.message.edit_text(new_text, reply_markup=builder.as_markup())
            else:
                # Этот блок может и не понадобиться, если метод всегда кидает исключения при ошибке
                await callback.answer("Не удалось зарезервировать заказ.", show_alert=True)

        except ValueError as e:
            # Перехватываем ошибки, если заказ уже обработан или не найден
            logger.warning(f"Admin {admin_id} failed to reserve order {order_id}: {e}")
            await callback.answer(str(e), show_alert=True)
            # Можно также обновить сообщение, чтобы показать актуальный статус
            order_details = data_base.get_order_details(order_id)
            if order_details:
                new_text = callback.message.text + f"\n\n<b>Статус:</b> ❗️ {order_details['status']}"
                await callback.message.edit_text(new_text, reply_markup=None)

    except (IndexError, ValueError) as e:
        logger.error(f"Invalid callback data for order reservation: {callback.data} - {e}")
        await callback.answer("Ошибка в данных команды.", show_alert=True)
    except Exception as e:
        logger.error(f"Unexpected error in handle_reserve_order: {e}")
        await callback.answer("Произошла непредвиденная ошибка.", show_alert=True)


@router.callback_query(F.data.startswith("sell_from_order:"))
async def handle_sell_from_order(callback: CallbackQuery):
    """
    Обрабатывает нажатие кнопки "Продажа" в уведомлении о зарезервированном заказе.
    """
    try:
        order_id = int(callback.data.split(":")[1])
        admin_id = callback.from_user.id

        if admin_id not in admins:
            await callback.answer("У вас нет прав для этого действия.", show_alert=True)
            return

        try:
            # Получаем детали заказа до его завершения
            order_details = data_base.get_order_details(order_id)
            if not order_details:
                await callback.answer("Не удалось найти детали заказа.", show_alert=True)
                return

            # Отправляем уведомление о подтверждении заказа и начисляем баллы
            from services.notification_service import notification_service
            admin_user = data_base.sql_get_user(admin_id, 'first_name', 'last_name')
            admin_name = f"{admin_user[0]} {admin_user[1]}" if admin_user and admin_user[0] and admin_user[1] else f"Admin {admin_id}"
            await notification_service.notify_order_confirmed(order_id, order_details['user_id'], admin_name)

            # Завершаем продажу (списываем товар и меняем статусы)
            data_base.complete_sale_from_reservation(order_id, admin_id)
            await callback.answer(f"Заказ #{order_id} успешно продан.", show_alert=True)

            # Обновляем сообщение у админа
            new_text = callback.message.text.replace("✅ Зарезервовано", "💰 Продано")
            await callback.message.edit_text(new_text, reply_markup=None)

            # Оповещаем пользователей из листа ожидания
            for item in order_details['items']:
                product_id = item['product_id']
                size_id = item['size_id']
                waiting_list_users = data_base.clear_waiting_list_and_get_users(product_id, size_id)
                for user_id in waiting_list_users:
                    try:
                        await callback.bot.send_message(user_id, f"Товар '{item['name']}' (размер: {item['size_value']}), который вы ожидали, к сожалению, продан. Мы сообщим, если он снова появится в наличии.")
                    except Exception as e:
                        logger.error(f"Не удалось уведомить пользователя {user_id} из листа ожидания: {e}")

        except ValueError as e:
            logger.warning(f"Admin {admin_id} failed to sell order {order_id}: {e}")
            await callback.answer(str(e), show_alert=True)
            # Обновляем сообщение, чтобы отразить актуальный статус
            order_details = data_base.get_order_details(order_id)
            if order_details:
                new_text = callback.message.text.replace("✅ Зарезервовано", f"❗️ {order_details['status']}")
                close_button = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Закрыть", callback_data="delete_message")]
                ])
                await callback.message.edit_text(new_text, reply_markup=close_button)

    except (IndexError, ValueError) as e:
        logger.error(f"Invalid callback data for order selling: {callback.data} - {e}")
        await callback.answer("Ошибка в данных команды.", show_alert=True)
    except Exception as e:
        logger.error(f"Unexpected error in handle_sell_from_order: {e}")
        await callback.answer("Произошла непредвиденная ошибка.", show_alert=True)


# --- Новая логика рассылки ---

def get_recipient_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора аудитории рассылки."""
    builder = InlineKeyboardBuilder()
    builder.button(text=f"Админы ({len(viewers)})", callback_data="mailing_group:viewers")
    builder.button(text=f"VIP ({len(vip_users)})", callback_data="mailing_group:vip")
    builder.button(text=f"Всем", callback_data="mailing_group:all")
    builder.button(text="Бронза", callback_data="mailing_group:bronze")
    builder.button(text="Серебро", callback_data="mailing_group:silver")
    builder.button(text="Бриллиант", callback_data="mailing_group:diamond")
    builder.button(text="Отмена", callback_data="mailing:cancel")
    builder.adjust(2, 1, 3, 1)
    return builder.as_markup()

@router.callback_query(F.data == "start_mailing")
async def start_mailing(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in admins:
        await callback.answer("У вас нет прав для этого действия.", show_alert=True)
        return
    
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="mailing:cancel")]
    ])
    prompt_msg = await callback.message.edit_text(
        "Перешлите или отправьте сообщение, которое нужно разослать всем пользователям.", 
        reply_markup=cancel_kb
    )
    await state.update_data(prompt_message_id=prompt_msg.message_id)
    await state.set_state(StateMailing.waiting_for_message)
    await callback.answer()

@router.message(StateFilter(StateMailing.waiting_for_message))
async def message_to_mail_received(message: Message, state: FSMContext):
    data = await state.get_data()
    prompt_message_id = data.get('prompt_message_id')

    # We need to copy the message to show a preview FIRST
    preview_message = await bot.copy_message(chat_id=message.chat.id, from_chat_id=message.chat.id, message_id=message.message_id)

    # Then, delete the initial prompt and the user's message
    await message.delete()
    if prompt_message_id:
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=prompt_message_id)
        except Exception:
            pass

    current_date_str = get_formatted_date()
    
    message_data = {
        'content_type': message.content_type,
        'text': message.text,
        'entities': [e.dict() for e in message.entities] if message.entities else [],
        'caption': message.caption,
        'caption_entities': [e.dict() for e in message.caption_entities] if message.caption_entities else [],
    }

    date_prefix = "\n\n"
    date_text = f"{current_date_str}"
    # The length of the entity is the number of UTF-16 code units
    date_entity = {'type': 'code', 'length': len(date_text.encode('utf-16-le')) // 2}

    if message.photo or message.video:
        message_data['file_id'] = message.photo[-1].file_id if message.photo else message.video.file_id
        
        original_caption = message_data.get('caption') or ""
        
        # The text that comes before the date. Add prefix only if there is a caption.
        prefix = original_caption + date_prefix if original_caption else ""
        
        # Calculate offset in UTF-16 code units
        offset = len(prefix.encode('utf-16-le')) // 2
        date_entity['offset'] = offset

        message_data['caption'] = prefix + date_text
        message_data['caption_entities'].append(date_entity)

    elif message.text: # For text messages
        original_text = message_data.get('text') or ""

        # The text that comes before the date. Add prefix only if there is text.
        prefix = original_text + date_prefix if original_text else ""

        # Calculate offset in UTF-16 code units
        offset = len(prefix.encode('utf-16-le')) // 2
        date_entity['offset'] = offset

        message_data['text'] = prefix + date_text
        message_data['entities'].append(date_entity)

    archive_content = message.html_text or message.caption
    match = re.search(r'<b>(.*?)</b>', archive_content) if archive_content else None
    if match:
        archive_name = match.group(1)
    else:
        archive_name = (message.text or message.caption or "Медиа-сообщение")[:30]
        if len(archive_name) == 30:
            archive_name += "..."

    await state.update_data(
        message_to_send=message_data,
        archive_name=archive_name,
        archive_content=archive_content,
        preview_message_id=preview_message.message_id # Save preview message id to delete later
    )

    # Check if recipients are already selected (from subscription flow)
    if data.get('users_to_send'):
        group_name = data.get('group_name', 'Подписчики')
        user_count = len(data.get('users_to_send'))
        
        confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да, отправить", callback_data="mailing:confirm")],
            [InlineKeyboardButton(text="Отмена", callback_data="mailing:cancel")]
        ])
        # We need to delete the "send message" prompt here
        prompt_message_id = data.get('prompt_message_id')
        if prompt_message_id:
            try:
                await bot.delete_message(message.chat.id, prompt_message_id)
            except Exception:
                pass

        confirm_prompt = await message.answer(
            f"Вы уверены, что хотите отправить это сообщение группе "
            f"<b>'{group_name}'</b> ({user_count} чел.)?",
            reply_markup=confirm_kb,
            parse_mode="HTML"
        )
        await state.update_data(messages_to_delete=[preview_message.message_id, confirm_prompt.message_id])
        await state.set_state(StateMailing.waiting_for_confirmation)
    else:
        # --- Go to standard group selection ---
        markup = get_recipient_keyboard()
        prompt_msg = await message.answer(
            "Сообщение готово. Выберите аудиторию для рассылки:",
            reply_markup=markup
        )
        await state.update_data(prompt_message_id=prompt_msg.message_id)
        await state.set_state(StateMailing.waiting_for_recipient_group)


@router.callback_query(F.data.startswith("mailing_group:"), StateFilter(StateMailing.waiting_for_recipient_group))
async def select_recipient_group(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    group_code = callback.data.split(":")[1]
    
    group_map = {
        "viewers": ("Админы", viewers),
        "vip": ("VIP", vip_users),
        "all": ("Все пользователи", data_base.get_unblocked_users()),
        "bronze": ("Бронзовые", data_base.get_users_by_level('bronze')),
        "silver": ("Серебряные", data_base.get_users_by_level('silver')),
        "diamond": ("Бриллиантовые", data_base.get_users_by_level('diamond')),
    }

    if group_code not in group_map:
        await callback.message.edit_text("Неизвестная группа.")
        await state.clear()
        return

    group_name, user_list = group_map[group_code]
    user_count = len(user_list)

    await state.update_data(users_to_send=user_list, group_name=group_name)

    data = await state.get_data()
    prompt_message_id = data.get('prompt_message_id')
    preview_message_id = data.get('preview_message_id')

    # Delete previous messages
    if prompt_message_id:
        try:
            await bot.delete_message(callback.message.chat.id, prompt_message_id)
        except Exception:
            pass
    
    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да, отправить", callback_data="mailing:confirm")],
        [InlineKeyboardButton(text="Отмена", callback_data="mailing:cancel")]
    ])

    confirm_prompt = await callback.message.answer(
        f"Вы уверены, что хотите отправить это сообщение группе "
        f"<b>'{group_name}'</b> ({user_count} чел.)?",
        reply_markup=confirm_kb,
        parse_mode="HTML"
    )

    # Update messages to delete to include the new prompt and the preview
    await state.update_data(messages_to_delete=[preview_message_id, confirm_prompt.message_id])
    await state.set_state(StateMailing.waiting_for_confirmation)

@router.callback_query(F.data == "mailing:from_template")
async def mailing_from_template_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in admins:
        await callback.answer("У вас нет прав для этого действия.", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="🔥 Перезавантаження Програми Лояльності!", callback_data="mailing:template:loyalty_relaunch")
    builder.button(text="Отмена", callback_data="mailing:cancel")
    builder.adjust(1)

    await callback.message.edit_text("Выберите шаблон для рассылки:", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("mailing:template:"))
async def mailing_from_template_select(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    template_key = callback.data.split(":")[2]

    current_date_str = get_formatted_date()

    if template_key == "loyalty_relaunch":
        content = LOYALTY_RELAUNCH_ANNOUNCEMENT
        match = re.search(r'<b>(.*?)</b>', content)
        name = match.group(1) if match else "🔥 Перезавантаження Програми Лояльності!"
    else:
        return

    # Append date to content, wrapped in <code> tags
    content_with_date = f"{content}\n\n<code>{current_date_str}</code>"

    message_data = {
        'content_type': 'text',
        'text': content_with_date,
        'entities': None,
        'parse_mode': 'HTML'
    }

    # Send a preview of the template message
    preview_message = await callback.message.answer(
        text=content_with_date,
        parse_mode='HTML',
        disable_web_page_preview=True
    )

    await state.update_data(
        message_to_send=message_data,
        archive_name=name,
        archive_content=content,
        preview_message_id=preview_message.message_id
    )

    # Show recipient selection
    markup = get_recipient_keyboard()
    prompt_msg = await callback.message.edit_text(
        "Сообщение из шаблона готово. Выберите аудиторию для рассылки:",
        reply_markup=markup
    )
    await state.update_data(prompt_message_id=prompt_msg.message_id)
    await state.set_state(StateMailing.waiting_for_recipient_group)


@router.callback_query(F.data == "start_subscription_mailing")
async def start_subscription_mailing(callback: CallbackQuery, state: FSMContext):
    """
    Starts the process of mailing to subscribers by showing a list of topics.
    """
    if callback.from_user.id not in admins:
        await callback.answer("У вас нет прав для этого действия.", show_alert=True)
        return

    topics = data_base.get_subscription_topics()
    if not topics:
        await callback.answer("Нет доступных тем для подписки.", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for topic in topics:
        subscribers_count = len(data_base.get_subscribers(topic['topic_key']))
        builder.button(
            text=f"{topic['description']} ({subscribers_count})",
            callback_data=f"select_subscription_topic:{topic['topic_key']}"
        )
    
    builder.button(text="Отмена", callback_data="mailing:cancel")
    builder.adjust(1)

    await callback.message.edit_text(
        "Выберите тему для рассылки:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("select_subscription_topic:"))
async def select_subscription_topic(callback: CallbackQuery, state: FSMContext):
    """
    Handles the selection of a subscription topic. 
    For simple topics, it gets subscribers and asks for the message.
    For complex topics (like brand_news), it proceeds to the next selection step.
    """
    await callback.answer()
    topic_key = callback.data.split(":")[1]
    await state.update_data(topic_key=topic_key)

    if topic_key == 'brand_news':
        # Get brands that have at least one subscriber
        all_brands = data_base.get_all_brands()
        brands_with_subscribers = []
        for brand in all_brands:
            if data_base.get_subscribers_for_brand(brand):
                brands_with_subscribers.append(brand)

        if not brands_with_subscribers:
            await callback.answer("Никто не подписан на новости по конкретным брендам.", show_alert=True)
            return

        builder = InlineKeyboardBuilder()
        for brand in brands_with_subscribers:
            builder.button(text=brand, callback_data=f"select_brand_for_mailing:{brand}")
        builder.adjust(2)
        builder.row(InlineKeyboardButton(text="Отмена", callback_data="mailing:cancel"))
        
        await callback.message.edit_text(
            "Выберите бренд для рассылки новостей:",
            reply_markup=builder.as_markup()
        )
        await state.set_state(StateMailing.waiting_for_brand_for_subscription_mailing)

    else: # For simple topics like 'new_arrivals', 'sales_and_discounts'
        subscribers = [sub['user_id'] for sub in data_base.get_subscribers(topic_key)]
        if not subscribers:
            await callback.answer("На эту тему никто не подписан.", show_alert=True)
            return

        topic_info = next((topic for topic in data_base.get_subscription_topics() if topic['topic_key'] == topic_key), None)
        group_name = topic_info['description'] if topic_info else topic_key

        await state.update_data(users_to_send=subscribers, group_name=group_name)

        cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Отмена", callback_data="mailing:cancel")]
        ])
        prompt_msg = await callback.message.edit_text(
            f"Выбрана тема: <b>{group_name}</b> ({len(subscribers)} подписчиков).\n\n"
            "Теперь перешлите или отправьте сообщение, которое нужно разослать.", 
            reply_markup=cancel_kb,
            parse_mode="HTML"
        )
        await state.update_data(prompt_message_id=prompt_msg.message_id)
        await state.set_state(StateMailing.waiting_for_message)

@router.callback_query(F.data.startswith("select_brand_for_mailing:"), StateFilter(StateMailing.waiting_for_brand_for_subscription_mailing))
async def brand_for_subscription_mailing_selected(callback: CallbackQuery, state: FSMContext):
    """
    Handles the selection of a brand for brand-news mailing.
    """
    await callback.answer()
    brand_name = callback.data.split(":")[1]

    subscribers = data_base.get_subscribers_for_brand(brand_name)
    if not subscribers:
        await callback.answer(f"На новости бренда {brand_name} никто не подписан.", show_alert=True)
        return

    group_name = f"Подписчики на новости бренда {brand_name}"
    await state.update_data(users_to_send=subscribers, group_name=group_name)

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="mailing:cancel")]
    ])
    prompt_msg = await callback.message.edit_text(
        f"Выбран бренд: <b>{brand_name}</b> ({len(subscribers)} подписчиков).\n\n"
        "Теперь перешлите или отправьте сообщение, которое нужно разослать.",
        reply_markup=cancel_kb,
        parse_mode="HTML"
    )
    await state.update_data(prompt_message_id=prompt_msg.message_id)
    await state.set_state(StateMailing.waiting_for_message)



async def send_message_with_close_button(user_id: int, message_data: dict):
    close_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Закрыть", callback_data="delete_message")]
    ])
    
    content_type = message_data.get('content_type')
    text = message_data.get('text')
    entities_data = message_data.get('entities')
    caption = message_data.get('caption')
    caption_entities_data = message_data.get('caption_entities')
    file_id = message_data.get('file_id')
    parse_mode = message_data.get('parse_mode')

    entities = [MessageEntity(**e) for e in entities_data] if entities_data else None
    caption_entities = [MessageEntity(**e) for e in caption_entities_data] if caption_entities_data else None

    if content_type == 'text':
        await bot.send_message(user_id, text, entities=entities, reply_markup=close_kb, parse_mode=parse_mode, disable_web_page_preview=True)
    elif content_type == 'photo':
        await bot.send_photo(user_id, file_id, caption=caption, caption_entities=caption_entities, reply_markup=close_kb, parse_mode=parse_mode)
    elif content_type == 'video':
        await bot.send_video(user_id, file_id, caption=caption, caption_entities=caption_entities, reply_markup=close_kb, parse_mode=parse_mode)

@router.callback_query(StateMailing.waiting_for_confirmation, F.data == 'mailing:confirm')
async def confirm_mailing_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    messages_to_delete = data.get('messages_to_delete', [])
    
    if messages_to_delete:
        start_message = await bot.send_message(callback.from_user.id, "Начинаю рассылку...")
        for msg_id in messages_to_delete:
            try: 
                await bot.delete_message(callback.from_user.id, msg_id)
            except Exception: pass
    else:
        start_message = await callback.message.edit_text("Начинаю рассылку...")
    
    await callback.answer()

    message_data = data.get('message_to_send')
    archive_name = data.get('archive_name')
    archive_content = data.get('archive_content')
    group_name = data.get('group_name', 'неизвестной группе')
    users_to_send = data.get('users_to_send', [])

    if not message_data:
        await start_message.edit_text("Произошла ошибка, сообщение для рассылки не найдено.")
        await state.clear()
        return

    # Append date to archive_content
    current_date_str = get_formatted_date()
    if archive_content:
        archive_content += f"\n\n<code>{current_date_str}</code>"
    else:
        archive_content = f"<code>{current_date_str}</code>"

    try:
        if archive_content:
            archive_id = data_base.add_message_to_archive(name=archive_name, content=archive_content)
            if users_to_send:
                data_base.add_archive_recipients(archive_id=archive_id, user_ids=users_to_send)
            logger.info(f"Сообщение для рассылки заархивировано для {len(users_to_send)} получателей.")
    except Exception as e:
        logger.error(f"Ошибка автоматической архивации: {e}")
        await bot.send_message(callback.from_user.id, f"⚠️ Не удалось сохранить сообщение в архив, но рассылка будет выполнена. Ошибка: {e}")

    success_count = 0
    blocked_count = 0

    for user_id in users_to_send:
        try:
            await send_message_with_close_button(user_id, message_data)
            success_count += 1
        except TelegramForbiddenError:
            logger.warning(f"Пользователь {user_id} заблокировал бота. Обновляю статус.")
            data_base.update_user_blocked(user_id, 1)
            blocked_count += 1
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
        await asyncio.sleep(0.1)

    report_text = (
        f"✅ Рассылка для группы '{group_name}' завершена!\n\n"
        f"- Успешно отправлено: {success_count}\n"
        f"- Заблокировали бота: {blocked_count}"
    )
    
    close_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Закрыть", callback_data="delete_message")]
    ])
    await start_message.edit_text(report_text, reply_markup=close_kb)
    await state.clear()

@router.callback_query(F.data == 'mailing:cancel')
async def cancel_mailing_handler(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    await callback.answer("Рассылка отменена.") # Answer first to dismiss loading state

    current_state = await state.get_state()
    if current_state is None: # If no active state, just go back to admin panel
        try:
            await callback.message.edit_text("Отменено.") # Edit the template selection message
        except TelegramBadRequest:
            await bot.send_message(callback.from_user.id, "Отменено.")
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения об отмене (без состояния): {e}")
            await bot.send_message(callback.from_user.id, "Отменено (произошла ошибка при обновлении сообщения).")
        await show_admin_panel(callback, state, manager)
        return

    data = await state.get_data()
    messages_to_delete = data.get('messages_to_delete', [])
    
    try:
        # Attempt to edit the message to show cancellation status
        await callback.message.edit_text("Рассылка отменена.")
    except TelegramBadRequest:
        # If message was already deleted or not found, send a new message
        await bot.send_message(callback.from_user.id, "Рассылка отменена.")
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения об отмене рассылки: {e}")
        await bot.send_message(callback.from_user.id, "Рассылка отменена (произошла ошибка при обновлении сообщения).")

    for msg_id in messages_to_delete:
        # Ensure we don't try to delete the message we just edited/sent
        if msg_id != callback.message.message_id:
            try:
                await bot.delete_message(callback.from_user.id, msg_id)
            except Exception:
                pass
            
    await state.clear()
    # Navigate back to admin panel
    await show_admin_panel(callback, state, manager)
