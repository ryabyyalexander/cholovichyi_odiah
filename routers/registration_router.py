from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, \
    InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from enums import MainMenu
from keyboards.kb import NavigationCallback
from middlewares.message_manager_middlewares import MessageManager
from data_base.models import data_base
from utils import logger, safe_delete_message, admins
from services.loyalty_service import LoyaltyService

router = Router()


@router.callback_query(
    NavigationCallback.filter(F.action == "main"),
    NavigationCallback.filter(F.current_level == MainMenu.PHONE),
)
async def handle_add_phone(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    data = await state.get_data()
    if "animation_task" in data and not data["animation_task"].done():
        data["animation_task"].cancel()
        logger.debug("Анимация остановлена")

    get_phone_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📞 Надіслати номер", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await manager.send(
        f"👋 Ласкаво просимо, {callback.from_user.first_name or 'Користувач'}!\nНадішліть свій номер для реєстрації.",
        reply_markup=get_phone_kb
    )
    await callback.answer()


@router.message(F.contact)
async def handle_contact(message: Message, manager: MessageManager):
    contact = message.contact
    user_id = message.from_user.id

    if data_base.is_user_active(user_id):
        await manager.send("✅ Ви вже активовані.")
        return

    data_base.execute_query(
        "UPDATE users SET phone = ? WHERE user_id = ?",
        (contact.phone_number, user_id)
    )

    # --- Проверка и применение акции "Золотой старт" ---
    promotion = data_base.get_active_promotion("GIVE_GOLD_ON_FIRST_LOGIN")
    if promotion:
        loyalty_service = LoyaltyService(data_base)
        loyalty_service.add_points_for_purchase(user_id, 5000)
        await manager.send(
            f"🎉 <b>Вітаємо з реєстрацією!</b>\n\n" 
            f"Ви отримуєте бонус в рамках акції <b>\"{promotion['name']}\"</b>.\n"
            f"Вам нараховано 5000 балів та присвоєно рівень <b>GOLD</b>!\n"
            f"Насолоджуйтесь ексклюзивними знижками."
        )

    await manager.send(
        f"✅  Зараз доступні майже всі функції.\nЛаскаво просимо  →    /start\n\n⏳  Як тільки адміністратор підтвердить ваш доступ, " 
        "Ви зможете користуватися всіма можливостями бота!",
        reply_markup=ReplyKeyboardRemove()
    )
    await notify_admins_about_new_user(message, user_id, contact.phone_number)
    await safe_delete_message(message)


async def notify_admins_about_new_user(message: Message, user_id: int, phone: str):
    confirm_button = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Підтвердити", callback_data=f"confirm_{user_id}")]
        ]
    )

    user_info = (
        f"📲 Новий запит на підписку:\n"
        f"👤 {message.from_user.full_name} (@{message.from_user.username})\n"
        f"🆔 ID: {user_id}\nНомер: {phone}"
    )

    for admin_id in admins:
        try:
            await message.bot.send_message(
                admin_id,
                user_info,
                reply_markup=confirm_button
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")




@router.callback_query(F.data == "profile_add_phone")
async def handle_profile_add_phone(callback: CallbackQuery, manager: MessageManager):
    get_phone_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📞 Надіслати номер", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await manager.send(
        f"👋 {callback.from_user.first_name or 'Користувач'}, надішліть свій номер для реєстрації.",
        reply_markup=get_phone_kb
    )
    await callback.answer()

