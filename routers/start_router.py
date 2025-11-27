import asyncio
import time

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from data_base.models import data_base
from enums import MainMenu
from keyboards.kb import create_keyboard, create_main_menu_keyboard
from middlewares.message_manager_middlewares import MessageManager
from utils import admins, logger, bot
from utils.caption_animate import animate_caption
from utils.functions import safe_delete_message, get_caption
from utils.filter_manager import FilterManager
from services.loyalty_service import LoyaltyService
from utils.slider_manager import SliderManager

router = Router()

LAST_START_TIME = {}


class StartLock:
    _locks = {}

    @classmethod
    def get_lock(cls, user_id):
        if user_id not in cls._locks:
            cls._locks[user_id] = asyncio.Lock()
        return cls._locks[user_id]


@router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext, manager: MessageManager):
    user_id = message.from_user.id
    data_base.update_user_blocked(user_id, 0)
    now = time.time()

    # Защита от частых запросов
    if user_id in LAST_START_TIME and (now - LAST_START_TIME[user_id]) < 1:
        return
    LAST_START_TIME[user_id] = now

    async with StartLock.get_lock(user_id):
        # Отмена предыдущей анимации
        data = await state.get_data()
        if "animation_task" in data and not data["animation_task"].done():
            data["animation_task"].cancel()
            try:
                await data["animation_task"]
            except asyncio.CancelledError:
                pass

        # Остановка слайдера если он работает
        slider_data = await state.get_data()
        if slider_data.get("playing") or slider_data.get("msg_id"):
            slider_manager = SliderManager(manager, state)
            await slider_manager._stop_previous_slideshow()
            # Очищаем данные слайдера из состояния
            await state.update_data(
                index=None, playing=None, photo_list=None, msg_id=None, speed=None,
                cycle_count=None, cycle_length=None, expanded=None, first_photo_shown=None,
                media_list=None, product_ids=None, slider_media_list=None, slider_product_ids=None
            )

        # Очистка предыдущих сообщений
        if register_msg_id := data_base.get_and_clear_register_msg_id(user_id):
            try:
                await bot.delete_message(chat_id=user_id, message_id=register_msg_id)
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение о регистрации: {e}")

        if active_msg_id := data_base.get_active_msg_id(user_id):
            try:
                await manager.bot.delete_message(chat_id=user_id, message_id=active_msg_id)
            except TelegramBadRequest:
                pass

        # Сохраняем user_id в FSM state
        await state.update_data(user_id=user_id)

        # Подгружаем фильтры из базы в FSM
        await FilterManager.load_filters_from_db(state)

        # --- Новый блок: обработка реферала ---
        user = data_base.sql_get_user(user_id)
        referrer_id = None
        # Получаем аргумент /start (user_id реферера)
        args = message.text.split()
        is_self_ref = False
        if len(args) > 1:
            try:
                referrer_id = int(args[1])
                if referrer_id == user_id:
                    referrer_id = None  # нельзя быть реферером самому себе
                    is_self_ref = True
            except Exception:
                referrer_id = None
        loyalty = LoyaltyService(data_base)
        is_new_user = False
        if not user:
            # Новый пользователь, регистрируем с referrer_id если есть
            is_new_user = data_base.register_user_with_referrer(
                user_id,
                message.from_user.first_name,
                message.from_user.last_name,
                message.from_user.username,
                user_id in admins,
                referrer_id=referrer_id
            )
            active_filters = await FilterManager.get_active_filters(state)
            start_kb = create_main_menu_keyboard(user_id, "", "main", active_filters)
            # Передаем user_id в состояние перед вызовом get_caption
            await state.update_data(user_id=user_id)
            caption = await get_caption(state)
            msg = await manager.send(caption, reply_markup=start_kb)
        else:
            # Получаем активные фильтры для определения текста кнопки
            active_filters = await FilterManager.get_active_filters(state)
            start_kb = create_main_menu_keyboard(user_id, "", "main", active_filters)
            # Передаем user_id в состояние перед вызовом get_caption
            await state.update_data(user_id=user_id)
            caption = await get_caption(state)
            msg = await manager.send(caption, reply_markup=start_kb)

        await safe_delete_message(message)

        # --- Новый блок: уведомление админу о регистрации по реферальной ссылке ---
        if is_new_user:
            if referrer_id:
                from_user = message.from_user
                text = (f"👤 Новый пользователь по реферальной ссылке!\n"
                        f"ID: <code>{user_id}</code>\n"
                        f"Имя: {from_user.first_name or ''} {from_user.last_name or ''}\n"
                        f"Username: @{from_user.username or '-'}\n"
                        f"Реферер: <code>{referrer_id}</code>")
                close_kb = InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="╳", callback_data="close_admin_referral_notify")]]
                )
                for admin_id in admins:
                    try:
                        await manager.bot.send_message(admin_id, text, reply_markup=close_kb)
                    except Exception as e:
                        logger.warning(f"Не удалось отправить уведомление админу {admin_id}: {e}")
            elif is_self_ref:
                log_msg = f"Пользователь {user_id} (@{message.from_user.username}) попытался зарегистрироваться по собственной реферальной ссылке. (is_admin={user_id in admins})"
                logger.info(log_msg)
                # print(log_msg)

        # --- Новый блок: начисление бонуса рефереру за первый старт ---
        if is_new_user and referrer_id:
            # Проверяем, что у пользователя есть referrer_id и это первый старт
            # (is_new_user True только при первой регистрации)
            loyalty.add_referral_bonus(referrer_id, user_id)

        # Запуск анимации
        animation_task = asyncio.create_task(animate_caption(manager, start_kb, msg.message_id, state))
        await state.update_data({
            "animation_task": animation_task,
            "animation_message_id": msg.message_id
        })


@router.callback_query(F.data.startswith("confirm_"))
async def confirm_user(callback: CallbackQuery):
    user_id = None
    if callback.from_user.id not in admins:
        await callback.answer("❌ Доступ заборонено")
        return

    try:
        user_id = int(callback.data.split("_")[1])
        logger.info(f"Admin {callback.from_user.id} confirms user {user_id}")

        data_base.activate_user(user_id)
        data_base.set_user_level(user_id, 'bronze')
        logger.info(f"User activated: {user_id}")

        await callback.message.delete()
        await callback.answer("✅ Користувача активовано")

        # Отправляем сообщение пользователю
        try:
            msg = await bot.send_message(
                chat_id=user_id,
                text="✅ Ваш профіль активовано.\nЛаскаво просимо  →    /start\n\n"
            )
            data_base.set_register_msg_id(user_id, msg.message_id)
        except Exception as e:
            logger.error(f"Failed to send confirmation to user {user_id}: {e}")

    except Exception as e:
        logger.error(f"Confirmation error: {e}")
        await callback.answer(f"❌ Помилка: {e}")

    if active_msg_id := data_base.get_active_msg_id(user_id):
        try:
            await bot.delete_message(chat_id=user_id, message_id=active_msg_id)
            logger.info(f"Deleted waiting message (ID: {active_msg_id})")
        except Exception as e:
            logger.warning(f"Failed to delete waiting message: {e}")


# --- Новый callback handler для закрытия уведомления админу о реферале ---
@router.callback_query(F.data == "close_admin_referral_notify")
async def close_admin_referral_notify(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение по кнопке 'Закрыть': {e}")
    await callback.answer()

