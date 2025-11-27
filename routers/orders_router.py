from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from data_base.models import data_base
from keyboards.kb import NavigationCallback
from enums.profile_enum import Profile
from utils.message_manager import MessageManager
from aiogram.utils.keyboard import InlineKeyboardBuilder
from enums.main_menu_enum import RegisteredMainMenu

router = Router()


@router.callback_query(NavigationCallback.filter(F.current_level == Profile.ORDERS))
async def handle_orders(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    user_id = callback.from_user.id
    orders = data_base.get_user_orders(user_id)

    if not orders:
        text = "У вас ще немає замовлень."
        builder = InlineKeyboardBuilder()
        builder.button(
            text="⬅️  До профілю",
            callback_data=NavigationCallback(action="main", current_level="profile", breadcrumbs="").pack()
        )
        await manager.edit(text, reply_markup=builder.as_markup())
        await callback.answer()
        return

    text = "<b>Ваші замовлення:</b>\n\n"
    builder = InlineKeyboardBuilder()
    for order in orders:
        text += f"<b>Замовлення №{order['id']}</b> від {order['created_at']}\n"
        text += f"Статус: {order['status']}\n"
        text += f"Сума: {order['final_amount']:.2f} грн\n\n"
        builder.button(
            text=f"Замовлення №{order['id']} - {order['final_amount']:.2f} грн. - від {order['created_at'][:10]}",
            callback_data=f"order_details:{order['id']}"
        )

    builder.button(
        text="⬅️  До профілю",
        callback_data=NavigationCallback(action="main", current_level=RegisteredMainMenu.PROFILE, breadcrumbs="").pack()
    )
    builder.adjust(1)

    await manager.edit(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("order_details:"))
async def handle_order_details(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    order_id = int(callback.data.split(":")[1])
    order_details = data_base.get_order_details(order_id)

    if not order_details:
        await callback.answer("Замовлення не знайдено.")
        return

    text = f"<b>Деталі замовлення №{order_details['id']}</b>\n\n"
    text += f"<b>Дата:</b> {order_details['created_at']}\n"
    text += f"<b>Статус:</b> {order_details['status']}\n\n"
    text += "<b>Товари:</b>\n"

    for item in order_details['items']:
        text += f"- {item['name']} ({item['size_value']}) - {item['quantity']} шт. x {item['unit_price']:.2f} грн = {item['total_price']:.2f} грн\n"

    text += f"\n<b>Загальна сума:</b> {order_details['final_amount']:.2f} грн"

    builder = InlineKeyboardBuilder()
    builder.button(
        text="⬅️  До списку замовлень",
        callback_data=NavigationCallback(action="main", current_level=Profile.ORDERS, breadcrumbs="").pack()
    )

    await manager.edit(text, reply_markup=builder.as_markup())
    await callback.answer()
