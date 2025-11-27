from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from data_base.models import data_base
from filters import IsAdmin
from services import loyalty_service
from utils.message_manager import MessageManager
from utils import logger, admins, viewers
from utils.slider_manager import SliderManager, format_media

# В блоке импортов из стандартной библиотеки или сторонних пакетов
import csv
import io
import math
from datetime import datetime, timedelta

# В блоке импортов aiogram
from aiogram.types import CallbackQuery, BufferedInputFile, InlineKeyboardButton

router = Router(name="admin_panel_router")

# Применяем фильтр админа ко всем хендлерам
router.message.filter(IsAdmin(admin_ids=viewers))
router.callback_query.filter(IsAdmin(admin_ids=viewers))


@router.callback_query(F.data == "admin_panel")
async def show_admin_panel(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    """Показывает админскую панель"""
    builder = InlineKeyboardBuilder()
    # Кнопка "Добавить товар" только для админов
    if callback.from_user.id in admins:
        builder.button(text="+  Додати товар", callback_data="admin_add_product")
        builder.button(text="+  Нова розсилка", callback_data="start_mailing")
        builder.button(text="+  Розсилка з шаблону", callback_data="mailing:from_template")
        builder.button(text="+  Розсилка для підписників", callback_data="start_subscription_mailing")
        pending_orders_count = data_base.get_pending_orders_count()
        if pending_orders_count > 0:
            builder.button(text=f"📋 Очікуючі замовлення ({pending_orders_count})", callback_data="admin_pending_orders")
        
        active_reservations_count = len(data_base.get_active_reservations())
        if active_reservations_count > 0:
            builder.button(text=f"📦 Резерви ({active_reservations_count})", callback_data="manage_reservations")

        builder.button(text="💎 Акції", callback_data="admin_promotions")
        builder.button(text="👤 Управління користувачами", callback_data="admin_user_management")

    builder.button(text="✅  Архів товарів", callback_data="admin_archive")
    
    builder.button(text="❇️  Статистика продажів", callback_data="admin_sales_stats")
    builder.button(text="✳️  Звіти по товарах", callback_data="admin_inventory_reports_menu")
    builder.button(text="← Назад до профілю", callback_data="admin_back_to_profile")
    builder.adjust(1)
    
    text = "<b>🔧 Адміністративна панель керування</b>\n\nОберіть дію:"
    await manager.edit(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "admin_promotions")
async def show_promotions_panel(callback: CallbackQuery, manager: MessageManager):
    """Показывает панель управления акциями"""
    if callback.from_user.id not in admins:
        await callback.answer("У вас нет прав для этого действия.", show_alert=True)
        return
    promotions = data_base.get_all_promotions()
    
    text = "<b>💎 Управление акциями</b>\n\n"
    if not promotions:
        text += "Активных или запланированных акций нет."
    
    builder = InlineKeyboardBuilder()
    
    for promo in promotions:
        status_icon = "✅" if promo['is_active'] else "❌"
        text += f"\n{status_icon} <b>{promo['name']}</b>\n"
        text += f"    <i>{promo['description']}</i>\n"
        text += f"    <b>Даты:</b> {promo['start_date']} - {promo['end_date']}\n"
        
        if promo['is_active']:
            builder.button(text=f'Остановить "{promo["name"]}"', callback_data=f"promo_deactivate:{promo['id']}")
        else:
            builder.button(text=f'Запустить "{promo["name"]}"', callback_data=f"promo_activate:{promo['id']}")

    builder.button(text="💰 Псевдо-покупка для новых", callback_data="give_pseudo_purchase")
    builder.button(text="← Назад", callback_data="admin_panel")
    builder.adjust(1)
    
    await manager.edit(text, reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data == "give_pseudo_purchase")
async def give_pseudo_purchase_to_new_users(callback: CallbackQuery, manager: MessageManager):
    if callback.from_user.id not in admins:
        await callback.answer("У вас нет прав для этого действия.", show_alert=True)
        return

    await callback.answer("⏳ Начинаю начисление псевдо-покупок...", show_alert=True)
    
    try:
        users_to_update = data_base.get_users_with_no_purchase_history()
        if not users_to_update:
            await manager.send("✅ Не найдено пользователей без истории покупок.")
            return

        ls = loyalty_service.LoyaltyService(data_base)
        count = 0
        for user_id in users_to_update:
            try:
                ls.log_pseudo_purchase_only(user_id, 5000)
                count += 1
            except Exception as e:
                logger.error(f"Ошибка начисления псевдо-покупки пользователю {user_id}: {e}")
        
        await manager.send(f"✅ Начисление завершено!\nОбработано пользователей: {count}")

    except Exception as e:
        logger.error(f"Ошибка массового начисления псевдо-покупок: {e}")
        await manager.send("❌ Произошла ошибка во время начисления.")


@router.callback_query(F.data.startswith("promo_activate:"))
async def activate_promotion(callback: CallbackQuery, manager: MessageManager):
    if callback.from_user.id not in admins:
        await callback.answer("У вас нет прав для этого действия.", show_alert=True)
        return
    promo_id = int(callback.data.split(":")[1])
    data_base.execute_query("UPDATE promotions SET is_active = 1 WHERE id = ?", (promo_id,))
    await callback.answer("✅ Акция запущена!")
    await show_promotions_panel(callback, manager)

@router.callback_query(F.data.startswith("promo_deactivate:"))
async def deactivate_promotion(callback: CallbackQuery, manager: MessageManager):
    if callback.from_user.id not in admins:
        await callback.answer("У вас нет прав для этого действия.", show_alert=True)
        return
    promo_id = int(callback.data.split(":")[1])
    data_base.execute_query("UPDATE promotions SET is_active = 0 WHERE id = ?", (promo_id,))
    await callback.answer("❌ Акция остановлена!")
    await show_promotions_panel(callback, manager)



@router.callback_query(F.data == "admin_archive")
async def show_archive(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    """Показывает архив товаров (активные и неактивные)"""
    products = data_base.get_all_products()
    if not products:
        await callback.answer("Товарів не знайдено.", show_alert=True)
        return

    user_id = callback.from_user.id
    slider_manager = SliderManager(manager, state)
    media_list, product_ids = format_media(products)
    await slider_manager.start_slider(media_list=media_list, product_ids=product_ids, source="archive", user_id=user_id)
    await callback.answer()


@router.callback_query(F.data == "admin_build_cart")
async def handle_build_cart(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    """Собрать корзину - заглушка"""
    await callback.answer("🛒 Зібрати кошик - функція в розробці", show_alert=True)


@router.callback_query(F.data == "admin_sales_stats")
async def handle_sales_stats(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    """Статистика продаж"""
    try:
        # Получаем отчет за последние 30 дней
        from datetime import datetime, timedelta
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        report = data_base.get_sales_report(start_date, end_date)
        
        text = f"<b>📊 Статистика продажів (30 днів)</b>\n\n"
        text += f"📋 Всього замовлень: {report['total_orders']}\n"
        text += f"✅ Підтверджених: {report['confirmed_orders']}\n"
        text += f"❌ Скасованих: {report['cancelled_orders']}\n"
        text += f"💰 Загальна виручка: {report['total_revenue']:.2f} €\n"
        text += f"🎁 Загальні знижки: {report['total_discounts']:.2f} €\n"
        text += f"📈 Середній чек: {report['avg_order_value']:.2f} €\n\n"
        
        if report['top_products']:
            text += "<b>🏆 Топ товарів:</b>\n"
            for i, product in enumerate(report['top_products'][:5], 1):
                brand_info = f" ({product['brand']})" if product['brand'] else ""
                text += f"{i}. {product['name']}{brand_info}\n"
                text += f"   Продано: {product['total_sold']} шт.\n"
                text += f"   Виручка: {product['total_revenue']:.2f} €\n"
                text += f"   Прибуток: {product['total_profit']:.2f} €\n\n"
        
        builder = InlineKeyboardBuilder()
        builder.button(text="📊 Детальний звіт", callback_data="admin_detailed_report")
        builder.button(text="📅 Змінити період", callback_data="admin_change_period")
        builder.button(text="← Назад", callback_data="admin_panel")
        builder.adjust(1)
        
        await manager.edit(text, reply_markup=builder.as_markup())
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        await callback.answer("❌ Помилка отримання статистики", show_alert=True)


@router.callback_query(F.data == "admin_back_to_profile")
async def admin_back_to_profile(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    """Возврат в профиль из админ панели"""
    from routers.profile_router import handle_profile
    await handle_profile(callback, state, manager)
    await callback.answer()


# НОВЫЕ ОБРАБОТЧИКИ ДЛЯ УПРАВЛЕНИЯ ЗАКАЗАМИ И ТОВАРАМИ

@router.callback_query(F.data == "admin_pending_orders")
async def handle_pending_orders(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    """Показывает список ожидающих заказов"""
    pending_orders = data_base.get_pending_orders()
    
    if not pending_orders:
        text = "<b>📋 Очікуючі замовлення</b>\n\nНемає замовлень, що очікують підтвердження."
        builder = InlineKeyboardBuilder()
        builder.button(text="← Назад", callback_data="admin_panel")
        await manager.edit(text, reply_markup=builder.as_markup())
        await callback.answer()
        return
    
    # Показываем первый заказ
    await state.update_data(pending_orders=pending_orders, current_order_index=0)
    await show_order_details(callback, state, manager, 0)


@router.callback_query(F.data.startswith("admin_order_"))
async def handle_order_action(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    """Обрабатывает действия с заказами"""
    action = callback.data.split("_")[2]  # confirm, cancel, next, prev
    data = await state.get_data()
    pending_orders = data.get('pending_orders', [])
    current_index = data.get('current_order_index', 0)
    if not pending_orders:
        await callback.answer("Немає замовлень для обробки", show_alert=True)
        return

    current_order = pending_orders[current_index]
    order_id = current_order['id']
    
    try:
        if action == "confirm":
            # Подтверждаем заказ
            admin_id = callback.from_user.id
            admin_user = data_base.sql_get_user(admin_id, 'first_name', 'last_name')
            admin_name = f"{admin_user[0]} {admin_user[1]}" if admin_user and admin_user[0] and admin_user[1] else f"Admin {admin_id}"
            
            data_base.complete_sale(order_id, admin_id, "Замовлення підтверджено")
            
            # Отправляем уведомление пользователю
            from services.notification_service import NotificationService
            from utils.loader import bot
            notification_service = NotificationService(bot)
            await notification_service.notify_order_confirmed(
                order_id, current_order['user_id'], admin_name
            )
            
            await callback.answer("✅ Замовлення підтверджено!")
            
        elif action == "cancel":
            # Отменяем заказ
            admin_id = callback.from_user.id
            reason = "Замовлення скасовано адміністратором"
            data_base.cancel_sale(order_id, admin_id, reason)
            
            # Отправляем уведомление пользователю
            from services.notification_service import NotificationService
            from utils.loader import bot
            notification_service = NotificationService(bot)
            await notification_service.notify_order_cancelled(
                order_id, current_order['user_id'], reason
            )
            
            await callback.answer("❌ Замовлення скасовано!")
            
        elif action == "next":
            # Следующий заказ
            if current_index < len(pending_orders) - 1:
                await state.update_data(current_order_index=current_index + 1)
                await show_order_details(callback, state, manager, current_index + 1)
            else:
                await callback.answer("Це останнє замовлення")
            return
            
        elif action == "prev":
            # Предыдущий заказ
            if current_index > 0:
                await state.update_data(current_order_index=current_index - 1)
                await show_order_details(callback, state, manager, current_index - 1)
            else:
                await callback.answer("Це перше замовлення")
            return
        
        # Обновляем список заказов после действия
        pending_orders = data_base.get_pending_orders()
        await state.update_data(pending_orders=pending_orders)
        
        if pending_orders:
            await show_order_details(callback, state, manager, 0)
        else:
            await handle_pending_orders(callback, state, manager)
        
    except Exception as e:
        logger.error(f"Ошибка обработки заказа {order_id}: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


async def show_order_details(callback: CallbackQuery, state: FSMContext, manager: MessageManager, order_index: int):
    """Показывает детали заказа"""
    data = await state.get_data()
    pending_orders = data.get('pending_orders', [])
    
    if order_index >= len(pending_orders):
        await callback.answer("Замовлення не знайдено", show_alert=True)
        return
    
    order = pending_orders[order_index]
    order_details = data_base.get_order_details(order['id'])
    
    if not order_details:
        await callback.answer("Деталі замовлення не знайдені", show_alert=True)
        return
    
    # Формируем текст с деталями заказа
    text = f"<b>📋 Замовлення #{order_details['id']}</b>\n\n"
    text += f"👤 <b>Клієнт:</b> {order_details['user_name']}\n"
    text += f"📞 <b>Телефон:</b> {order_details['user_phone'] or 'Не вказано'}\n"
    text += f"💰 <b>Сума:</b> {order_details['total_amount']:.2f} €\n"
    text += f"🎁 <b>Знижка:</b> {order_details['discount_amount']:.2f} €\n"
    text += f"💳 <b>До сплати:</b> {order_details['final_amount']:.2f} €\n"
    text += f"📅 <b>Дата:</b> {order_details['created_at'][:19]}\n"
    text += f"📦 <b>Товарів:</b> {len(order_details['items'])} шт.\n\n"
    
    text += "<b>📦 Товари:</b>\n"
    for i, item in enumerate(order_details['items'], 1):
        size_info = f" ({item['size_value']})" if item['size_value'] else ""
        text += f"{i}. {item['name']}{size_info} - {item['quantity']} шт. x {item['unit_price']:.2f} €\n"
    
    # Клавиатура
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Підтвердити", callback_data=f"admin_order_confirm")
    builder.button(text="❌ Скасувати", callback_data=f"admin_order_cancel")
    builder.button(text="◀️ Попередній", callback_data=f"admin_order_prev")
    builder.button(text="Наступний ▶️", callback_data=f"admin_order_next")
    builder.button(text="← Назад", callback_data="admin_panel")
    builder.adjust(2, 2, 1)
    
    await manager.edit(text, reply_markup=builder.as_markup())


# --- НОВЫЕ ОБРАБОТЧИКИ ДЛЯ ОТЧЕТОВ ПО ТОВАРАМ ---


@router.callback_query(F.data == "manage_reservations")
async def handle_manage_reservations(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    """Показывает список активных резервов"""
    active_reservations = data_base.get_active_reservations()
    
    if not active_reservations:
        text = "<b>📦 Активные резервы</b>\n\nНет активных резервов."
        builder = InlineKeyboardBuilder()
        builder.button(text="← Назад", callback_data="admin_panel")
        await manager.edit(text, reply_markup=builder.as_markup())
        await callback.answer()
        return
    
    await state.update_data(reservations=active_reservations, current_reservation_index=0)
    await show_reservation_details(callback, state, manager, 0)


async def show_reservation_details(callback: CallbackQuery, state: FSMContext, manager: MessageManager, reservation_index: int):
    """Показывает детали резерва"""
    data = await state.get_data()
    reservations = data.get('reservations', [])
    
    if reservation_index >= len(reservations):
        await callback.answer("Резерв не найден", show_alert=True)
        return
    
    reservation = reservations[reservation_index]
    reservation_details = data_base.get_reservation_details(reservation['reservation_id'])
    
    if not reservation_details:
        await callback.answer("Детали резерва не найдены", show_alert=True)
        return
    
    # Формируем текст с деталями резерва
    text = f"<b>📦 Резерв #{reservation_details['reservation_id']}</b>\n\n"
    text += f"👤 <b>Клиент:</b> {reservation_details['customer_name']}\n"
    text += f"📞 <b>Телефон:</b> {reservation_details['customer_phone'] or 'Не указано'}\n"
    text += f"📦 <b>Товар:</b> {reservation_details['product_name']}\n"
    text += f"📏 <b>Размер:</b> {reservation_details['size_value']}\n"
    text += f"📅 <b>Дата:</b> {reservation_details['created_at'][:19]}\n"
    if reservation_details['expires_at']:
        text += f"⏳ <b>Истекает:</b> {reservation_details['expires_at'][:19]}\n"
    
    # Клавиатура
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Продажа", callback_data=f"admin_reservation_confirm")
    builder.button(text="❌ Отменить", callback_data=f"admin_reservation_cancel")
    builder.button(text="◀️ Предыдущий", callback_data=f"admin_reservation_prev")
    builder.button(text="Следующий ▶️", callback_data=f"admin_reservation_next")
    builder.button(text="← Назад", callback_data="admin_panel")
    builder.adjust(2, 2, 1)
    
    photo_id = data_base.get_main_product_photo(reservation_details['product_id'])
    
    if photo_id:
        await manager.send_photo_message(photo_id, caption=text, reply_markup=builder.as_markup())
    else:
        await manager.edit(text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("admin_reservation_"))
async def handle_reservation_action(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    """Обрабатывает действия с резервами"""
    action = callback.data.split("_")[2]  # confirm, cancel, next, prev
    data = await state.get_data()
    reservations = data.get('reservations', [])
    current_index = data.get('current_reservation_index', 0)
    if not reservations:
        await callback.answer("Нет резервов для обработки", show_alert=True)
        return

    
    try:
        if action == "confirm":
            admin_id = callback.from_user.id
            reservation_id = reservations[current_index]['reservation_id']
            reservation_details = data_base.get_reservation_details(reservation_id)

            if not reservation_details:
                await callback.answer("Не удалось найти детали резерва.", show_alert=True)
                return

            order_id = reservation_details.get('order_id')
            if not order_id:
                await callback.answer("Ошибка: ID заказа не найден в резерве.", show_alert=True)
                return

            try:
                # Используем правильную функцию, которая списывает товар и обновляет статусы
                data_base.complete_sale_from_reservation(order_id, admin_id)
                await callback.answer("✅ Продажа подтверждена и товар списан!")

                # Отправляем уведомление покупателю
                from services.notification_service import NotificationService
                from utils.loader import bot
                notification_service = NotificationService(bot)
                admin_user = data_base.sql_get_user(admin_id, 'first_name', 'last_name')
                admin_name = f"{admin_user[0]} {admin_user[1]}" if admin_user and admin_user[0] and admin_user[1] else f"Admin {admin_id}"
                await notification_service.notify_order_confirmed(order_id, reservation_details['customer_id'], admin_name)

                # Оповещаем пользователей из листа ожидания
                product_id = reservation_details['product_id']
                size_id = data_base.get_size_id(reservation_details['size_value'])
                if size_id:
                    waiting_list_users = data_base.clear_waiting_list_and_get_users(product_id, size_id)
                    for user_id in waiting_list_users:
                        try:
                            await callback.bot.send_message(user_id, f"Товар '{reservation_details['product_name']}' (размер: {reservation_details['size_value']}), который вы ожидали, к сожалению, продан. Мы сообщим, если он снова появится в наличии.")
                        except Exception as e:
                            logger.error(f"Не удалось уведомить пользователя {user_id} из листа ожидания: {e}")

            except ValueError as e:
                logger.error(f"Ошибка завершения продажи из резерва {reservation_id}: {e}")
                await callback.answer(f"Ошибка: {e}", show_alert=True)

            
        elif action == "cancel":
            reservation_id = reservations[current_index]['reservation_id']
            data_base.update_reservation_status(reservation_id, 'cancelled')
            await callback.answer("❌ Резерв отменен!")
            
        elif action == "next":
            if current_index < len(reservations) - 1:
                await state.update_data(current_reservation_index=current_index + 1)
                await show_reservation_details(callback, state, manager, current_index + 1)
            else:
                await callback.answer("Это последний резерв")
            return
            
        elif action == "prev":
            if current_index > 0:
                await state.update_data(current_reservation_index=current_index - 1)
                await show_reservation_details(callback, state, manager, current_index - 1)
            else:
                await callback.answer("Это первый резерв")
            return
        
        # Обновляем список резервов после действия
        active_reservations = data_base.get_active_reservations()
        
        if not active_reservations:
            await show_admin_panel(callback, state, manager)
            return

        new_index = min(current_index, len(active_reservations) - 1)
        await state.update_data(reservations=active_reservations, current_reservation_index=new_index)
        await show_reservation_details(callback, state, manager, new_index)
        
    except Exception as e:
        reservation_id = reservations[current_index]['reservation_id']
        logger.error(f"Ошибка обработки резерва {reservation_id}: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)



# --- НОВЫЕ ОБРАБОТЧИКИ ДЛЯ ОТЧЕТОВ ПО ТОВАРАМ ---


@router.callback_query(F.data == "admin_inventory_reports_menu")
async def show_inventory_reports_menu(callback: CallbackQuery, manager: MessageManager):
    """Показывает меню отчетов по товарам и общий отчет."""
    stats = data_base.get_total_inventory_stats()
    text = "<b>📦 Загальний звіт по товарах</b>\n\n"
    text += f"<b>Активних товарів:</b> {stats['active_products']}\n"
    text += f"<b>Неактивних товарів:</b> {stats['inactive_products']}\n"
    text += f"<b>Загальна кількість одиниць:</b> {stats['total_quantity']}\n"
    text += f"<b>Загальна вартість товарів:</b> {stats['total_value']:.2f} €\n\n"
    text += "<b>📊 Оберіть інший звіт:</b>"

    builder = InlineKeyboardBuilder()
    builder.button(text="🗂️ За категоріями", callback_data="inv_report_category")
    builder.button(text="📂 За підкатегоріями", callback_data="inv_report_subcategory")
    builder.button(text="🏷️ За брендами", callback_data="inv_report_brand")
    builder.button(text="📏 За розмірами", callback_data="inv_report_size_total")
    builder.button(text="← Назад", callback_data="admin_panel")
    builder.adjust(1)
    await manager.edit(text, reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data == "inv_report_category")
async def handle_category_inventory_report(callback: CallbackQuery, manager: MessageManager):
    """Формирует и отправляет отчет по категориям."""
    report_data = data_base.get_inventory_by_category()
    text = "<b>🗂️ Звіт за категоріями</b>\n\n"
    if not report_data:
        text += "Немає даних для звіту."
    else:
        for item in report_data:
            text += f"<b>{item['category']}:</b>\n"
            text += f"  - Кількість товарів: {item['product_count']}\n"
            text += f"  - Загальна кількість: {item['total_quantity']}\n"
            text += f"  - Вартість: {item['total_value']:.2f} €\n\n"
    builder = InlineKeyboardBuilder()
    builder.button(text="← Назад до звітів", callback_data="admin_inventory_reports_menu")
    await manager.edit(text, reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data == "inv_report_subcategory")
async def handle_subcategory_inventory_report(callback: CallbackQuery, manager: MessageManager):
    """Формирует и отправляет отчет по подкатегориям."""
    report_data = data_base.get_inventory_by_subcategory()
    text = "<b>📂 Звіт за підкатегоріями</b>\n\n"
    if not report_data:
        text += "Немає даних для звіту."
    else:
        current_category = ""
        for item in report_data:
            if item['category'] != current_category:
                current_category = item['category']
                text += f"<b>{current_category}</b>\n"
            text += f"  - <i>{item['subcategory']}:</i> {item['product_count']} товарів, {item['total_quantity']} шт., {item['total_value']:.2f} €\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="← Назад до звітів", callback_data="admin_inventory_reports_menu")
    await manager.edit(text, reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data == "inv_report_brand")
async def handle_brand_inventory_report(callback: CallbackQuery, manager: MessageManager):
    """Формирует и отправляет отчет по брендам."""
    report_data = data_base.get_inventory_by_brand()
    text = "<b>🏷️ Звіт за брендами</b>\n\n"
    if not report_data:
        text += "Немає даних для звіту."
    else:
        for item in report_data:
            text += f"<b>{item['brand']}:</b> {item['product_count']} товарів, {item['total_quantity']} шт., {item['total_value']:.2f} €\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="← Назад до звітів", callback_data="admin_inventory_reports_menu")
    await manager.edit(text, reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("inv_report_size_"))
async def handle_size_inventory_report(callback: CallbackQuery, manager: MessageManager):
    """Формирует и отправляет отчет по размерам, возможно с фильтром по типу."""
    size_type_map = {
        'total': (None, "📏 Загальний звіт за розмірами"),
        'number': ('number', "📏 Звіт за розмірами (Куртки)"),
        'letter': ('letter', "📏 Звіт за розмірами (Трикотаж)"),
        'jeans': ('jeans', "📏 Звіт за розмірами (Джинси)")
    }
    size_type_key = callback.data.split("_")[-1]
    size_type, title = size_type_map.get(size_type_key, (None, "📏 Загальний звіт за розмірами"))

    report_data = data_base.get_inventory_by_size(size_type=size_type)
    text = f"<b>{title}</b>\n\n"
    if not report_data:
        text += "Немає даних для звіту."
    else:
        from collections import defaultdict
        type_translation = {'number': 'Куртки', 'letter': 'Трикотаж', 'jeans': 'Джинси'}
        grouped_data = defaultdict(list)
        for item in report_data:
            grouped_data[item['type']].append(item)

        for type_name, items in grouped_data.items():
            translated_type = type_translation.get(type_name, type_name)
            text += f"<b>Тип: {translated_type}</b>\n"
            size_lines = [f"  - {item['size']}: {item['total_quantity']} шт. ({item['total_value']:.2f} €)" for item in items]
            text += '\n'.join(size_lines) + "\n\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="Загальний", callback_data="inv_report_size_total")
    builder.button(text="Куртки", callback_data="inv_report_size_number")
    builder.button(text="Трикотаж", callback_data="inv_report_size_letter")
    builder.button(text="Джинси", callback_data="inv_report_size_jeans")
    builder.button(text="← Назад до звітів", callback_data="admin_inventory_reports_menu")
    builder.adjust(1, 3, 1)
    await manager.edit(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "admin_detailed_report")
async def handle_detailed_report(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    """Формирует и отправляет детальный отчет по продажам в виде CSV файла."""
    await callback.answer("⏳ Формую детальний звіт...", show_alert=False)

    try:
        # Получаем тот же период, что и в основной статистике
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')

        # Получаем данные из нового метода
        detailed_data = data_base.get_detailed_sales_data(start_date_str, end_date_str)

        if not detailed_data:
            await callback.answer("✅ Немає підтверджених замовлень за цей період для створення звіту.", show_alert=True)
            return

        # Используем io.StringIO для создания файла в памяти
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')

        # Заголовки CSV файла
        headers = [
            "ID Замовлення", "Дата підтвердження", "Клієнт", "Телефон",
            "Товар", "Бренд", "Категорія", "Розмір", "Кількість",
            "Ціна за одиницю (€)", "Вартість позиції (€)",
            "Закупівельна ціна (€)", "Прибуток (€)"
        ]
        writer.writerow(headers)

        # Записываем данные
        for row in detailed_data:
            # Безопасное форматирование числовых полей
            unit_price = float(str(row.get('unit_price', 0.0) or 0.0).replace(',', '.'))
            total_price = float(str(row.get('total_price', 0.0) or 0.0).replace(',', '.'))
            purchase_price = float(str(row.get('purchase_price', 0.0) or 0.0).replace(',', '.'))
            profit = float(str(row.get('profit', 0.0) or 0.0).replace(',', '.'))
            
            writer.writerow([
                row.get('sale_id'),
                row.get('confirmed_at', '')[:19] if row.get('confirmed_at') else '',
                row.get('user_name'),
                row.get('user_phone', 'Не вказано'),
                row.get('product_name'),
                row.get('product_brand'),
                row.get('product_category'),
                row.get('size_value', 'б/р'),
                row.get('quantity'),
                f"{unit_price:.2f}",
                f"{total_price:.2f}",
                f"{purchase_price:.2f}",
                f"{profit:.2f}"
            ])

        # Подготавливаем файл для отправки
        output.seek(0)
        report_bytes = output.getvalue().encode('utf-8')

        file_name = f"detailed_report_{start_date_str}_to_{end_date_str}.csv"

        # Оборачиваем байты в BufferedInputFile
        report_file = BufferedInputFile(report_bytes, filename=file_name)

        await callback.message.answer_document(
            document=report_file,
            caption=f"📊 Детальний звіт по продажам\n<b>Період:</b> з {start_date_str} по {end_date_str}"
        )

    except Exception as e:
        logger.error(f"Ошибка при формировании детального отчета: {e}")
        await callback.answer("❌ Помилка при формуванні звіту.", show_alert=True)

@router.callback_query(F.data.startswith("direct_order_"))
async def handle_direct_order_action(callback: CallbackQuery, manager: MessageManager):
    """
    Обрабатывает действия с заказом (подтверждение/отмена) прямо из уведомления.
    Работает без FSM, извлекая ID заказа из callback_data.
    """
    try:
        action_part, order_id_str = callback.data.split(":")
        action = action_part.split("_")[2] # confirm или cancel
        order_id = int(order_id_str)
    except (ValueError, IndexError) as e:
        logger.error(f"Ошибка разбора callback_data для прямого действия с заказом: {callback.data}, ошибка: {e}")
        await callback.answer("Сталася помилка. Спробуйте керувати замовленням через панель.", show_alert=True)
        return

    try:
        # Проверяем, существует ли еще заказ и находится ли он в статусе 'pending'
        order_status = data_base.execute_query("SELECT status FROM sales WHERE id = ?", (order_id,)).fetchone()
        if not order_status:
            await callback.answer(f"Замовлення #{order_id} не знайдено.", show_alert=True)
            await callback.message.edit_text(f"❌ Заказ #{order_id} не найден.", reply_markup=None)
            return
        if order_status[0] != 'pending':
            await callback.answer(f"Замовлення #{order_id} вже було оброблено.", show_alert=True)
            await callback.message.edit_text(f"ℹ️ Замовлення #{order_id} вже було оброблено (статус: {order_status[0]}).", reply_markup=None)
            return

        admin_id = callback.from_user.id
        admin_user = data_base.sql_get_user(admin_id, 'first_name', 'last_name')
        admin_name = f"{admin_user[0]} {admin_user[1]}" if admin_user and admin_user[0] and admin_user[1] else f"Admin {admin_id}"
        
        original_message_text = callback.message.text

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        close_button = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Закрыть", callback_data="delete_message")]
        ])

        if action == "confirm":
            data_base.complete_sale(order_id, admin_id, "Замовлення підтверджено")
            
            # Отправляем уведомление пользователю
            order_info = data_base.get_order_details(order_id)
            if order_info:
                from services.notification_service import NotificationService
                from utils.loader import bot
                notification_service = NotificationService(bot)
                await notification_service.notify_order_confirmed(order_id, order_info['user_id'], admin_name)
            
            await callback.answer("✅ Замовлення підтверджено!")
            final_text = f"<blockquote>{original_message_text}\n\n<b>--- ✅ ЗАМОВЛЕННЯ ПІДТВЕРДЖЕНО ---</b>\n<i>Адміністратор: {admin_name}</i></blockquote>"
            await callback.message.edit_text(final_text, reply_markup=close_button)

        elif action == "cancel":
            reason = "Замовлення скасовано адміністратором"
            data_base.cancel_sale(order_id, admin_id, reason)
            
            # Отправляем уведомление пользователю
            order_info = data_base.get_order_details(order_id)
            if order_info:
                from services.notification_service import NotificationService
                from utils.loader import bot
                notification_service = NotificationService(bot)
                await notification_service.notify_order_cancelled(order_id, order_info['user_id'], reason)

            await callback.answer("❌ Замовлення скасовано!")
            final_text = f"<blockquote>{original_message_text}\n\n<b>--- ❌ ЗАМОВЛЕННЯ СКАСОВАНО ---</b>\n<i>Адміністратор: {admin_name}</i></blockquote>"
            await callback.message.edit_text(final_text, reply_markup=close_button)

    except Exception as e:
        logger.error(f"Ошибка обработки прямого действия с заказом {order_id}: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


# --- НОВЫЕ ОБРАБОТЧИКИ ДЛЯ УПРАВЛЕНИЯ ПОЛЬЗОВАТЕЛЯМИ ---

USER_PAGE_SIZE = 50 # 5 users per page

async def _get_user_management_keyboard(page: int = 1):
    users, total_users = data_base.get_all_users_paginated(page=page, page_size=USER_PAGE_SIZE)
    total_pages = math.ceil(total_users / USER_PAGE_SIZE)

    builder = InlineKeyboardBuilder()
    for user in users:
        status = "🔴" if user['user_blocked'] else "🟢"
        admin_badge = " (A)" if user['is_admin'] else ""
        user_name = user['first_name'] or user['user_name'] or f"User {user['user_id']}"
        builder.button(
            text=f"{status} {user_name}{admin_badge}",
            callback_data=f"admin_user_details:{user['user_id']}"
        )
    
    # Pagination
    pagination_buttons = []
    if page > 1:
        pagination_buttons.append(
            InlineKeyboardButton(text="◀️", callback_data=f"admin_user_page:{page - 1}")
        )
    if total_pages > 1:
        pagination_buttons.append(
            InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop") # noop = no operation
        )
    if page < total_pages:
        pagination_buttons.append(
            InlineKeyboardButton(text="▶️", callback_data=f"admin_user_page:{page + 1}")
        )
    
    if pagination_buttons:
        builder.row(*pagination_buttons)

    builder.button(text="← Назад", callback_data="admin_panel")
    builder.adjust(1)
    return builder.as_markup()


@router.callback_query(F.data.in_(["admin_user_management", "admin_user_management:back"]))
async def handle_user_management(callback: CallbackQuery, manager: MessageManager):
    """Handles user management menu."""
    markup = await _get_user_management_keyboard(page=1)
    await manager.edit("👤 **Управління користувачами**", reply_markup=markup)
    await callback.answer()

@router.callback_query(F.data.startswith("admin_user_page:"))
async def handle_user_management_page(callback: CallbackQuery, manager: MessageManager):
    """Handles pagination for user management."""
    page = int(callback.data.split(":")[1])
    markup = await _get_user_management_keyboard(page=page)
    await manager.edit("👤 **Управління користувачами**", reply_markup=markup)
    await callback.answer()

@router.callback_query(F.data.startswith("admin_user_details:"))
async def handle_user_details(callback: CallbackQuery, manager: MessageManager):
    """Shows details and actions for a specific user."""
    user_id = int(callback.data.split(":")[1])
    
    user_info = data_base.sql_get_user(user_id, 'user_blocked', 'first_name', 'user_name')
    if not user_info:
        await callback.answer("Користувача не знайдено.", show_alert=True)
        return

    is_blocked, first_name, username = user_info[0], user_info[1], user_info[2]
    user_display_name = first_name or username or f"User {user_id}"

    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data=f"admin_user_stats:{user_id}")
    if is_blocked:
        builder.button(text="✅ Розблокувати", callback_data=f"admin_user_unblock:{user_id}")
    else:
        builder.button(text="🚫 Заблокувати", callback_data=f"admin_user_block:{user_id}")
    builder.button(text="🗑️ Видалити", callback_data=f"admin_user_delete:{user_id}")
    builder.button(text="← Назад до списку", callback_data="admin_user_management:back")
    builder.adjust(1)

    text = f"<b>👤 Дії для користувача</b>\n\n"
    text += f"🆔 <b>ID:</b> {user_id}\n"
    text += f"📝 <b>Ім'я:</b> {user_display_name}\n"
    text += f"🔒 <b>Статус:</b> {'🔴 Заблокований' if is_blocked else '🟢 Активний'}\n"
    
    await manager.edit(text, reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("admin_user_block:"))
async def handle_user_block(callback: CallbackQuery, manager: MessageManager):
    """Blocks a user."""
    user_id = int(callback.data.split(":")[1])
    data_base.update_user_blocked(user_id, True)
    await callback.answer("Користувача заблоковано.", show_alert=True)
    # Refresh the details view
    await handle_user_details(callback, manager)

@router.callback_query(F.data.startswith("admin_user_unblock:"))
async def handle_user_unblock(callback: CallbackQuery, manager: MessageManager):
    """Unblocks a user."""
    user_id = int(callback.data.split(":")[1])
    data_base.update_user_blocked(user_id, False)
    await callback.answer("Користувача розблоковано.", show_alert=True)
    # Refresh the details view
    await handle_user_details(callback, manager)

@router.callback_query(F.data.startswith("admin_user_delete:"))
async def handle_user_delete(callback: CallbackQuery, manager: MessageManager):
    """Shows a confirmation for deleting a user with safety check."""
    user_id = int(callback.data.split(":")[1])
    
    # Выполняем проверку безопасности удаления
    safety_info = data_base.check_user_deletion_safety(user_id)
    
    if not safety_info["exists"]:
        await callback.answer("Користувача не знайдено.", show_alert=True)
        return
    
    # Формируем текст с информацией о пользователе и связанных данных
    text = f"<b>🗑️ Видалення користувача</b>\n\n"
    text += f"👤 <b>Користувач:</b> {safety_info['first_name']} (ID: {user_id})\n"
    text += f"👑 <b>Адміністратор:</b> {'Так' if safety_info['is_admin'] else 'Ні'}\n\n"
    
    if safety_info["statistics"]:
        text += "<b>📊 Пов'язані дані, які будуть видалені:</b>\n"
        for table, count in safety_info["statistics"].items():
            table_names = {
                "loyalty_history": "історія лояльності",
                "product_activation_history": "історія активації товарів (як адмін)", 
                "inventory_receipts": "надходження товарів (як адмін)",
                "sales": "замовлення",
                "cart": "товари в кошику",
                "favorites": "товари в обраному",
                "users": "рефералів"
            }
            table_label = table_names.get(table, table)
            text += f"   • {table_label}: {count} записів\n"
    
    if safety_info["warnings"]:
        text += "\n⚠️ <b>Попередження:</b>\n"
        for warning in safety_info["warnings"]:
            text += f"   • {warning}\n"
    
    text += "\n❗ <b>Ця дія незворотна!</b> Всі дані користувача будуть повністю видалені."
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Так, видалити", callback_data=f"admin_user_delete_confirm:{user_id}")
    builder.button(text="❌ Ні, назад", callback_data=f"admin_user_details:{user_id}")
    builder.adjust(1)

    await manager.edit(text, reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("admin_user_delete_confirm:"))
async def handle_user_delete_confirm(callback: CallbackQuery, manager: MessageManager):
    """Deletes a user completely with detailed feedback."""
    user_id = int(callback.data.split(":")[1])
    admin_id = callback.from_user.id
    
    try:
        # Получаем информацию о пользователе перед удалением для логирования
        user_info = data_base.sql_get_user(user_id, 'first_name', 'last_name', 'user_name', 'is_admin')
        if not user_info:
            await callback.answer("Користувача не знайдено.", show_alert=True)
            return
            
        first_name, last_name, username, is_admin = user_info
        user_display_name = first_name or username or f"User {user_id}"
        
        # Выполняем безопасное удаление
        logger.info(f"Admin {admin_id} is deleting user {user_id} ({user_display_name})")
        data_base.delete_user_completely(user_id)
        
        # Формируем сообщение об успешном удалении
        success_text = f"✅ <b>Користувача успішно видалено!</b>\n\n"
        success_text += f"👤 <b>Видалено:</b> {user_display_name} (ID: {user_id})\n"
        success_text += f"👑 <b>Був адміністратором:</b> {'Так' if is_admin else 'Ні'}\n"
        success_text += f"🔧 <b>Видалив:</b> Admin {admin_id}\n\n"
        success_text += "📋 Всі пов'язані дані користувача були безпечно видалені з бази даних."
        
        await manager.edit(success_text, reply_markup=None)
        await callback.answer("Користувача успішно видалено!", show_alert=True)
        
        # Возвращаемся к списку пользователей через 3 секуды
        import asyncio
        await asyncio.sleep(3)
        await handle_user_management(callback, manager)
        
        logger.info(f"User {user_id} ({user_display_name}) successfully deleted by admin {admin_id}")
        
    except Exception as e:
        error_msg = f"Помилка при видаленні користувача: {str(e)}"
        logger.error(f"Failed to delete user {user_id} by admin {admin_id}: {e}")
        await callback.answer(error_msg, show_alert=True)
        
        # Показываем детали ошибки в сообщении
        error_text = f"❌ <b>Помилка видалення!</b>\n\n"
        error_text += f"👤 <b>Користувач:</b> {user_id}\n"
        error_text += f"❗ <b>Помилка:</b> {str(e)}\n\n"
        error_text += "Спробуйте ще раз або зверніться до розробника."
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Спробувати ще раз", callback_data=f"admin_user_delete:{user_id}")
        builder.button(text="← Назад до деталей", callback_data=f"admin_user_details:{user_id}")
        builder.adjust(1)
        
        await manager.edit(error_text, reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("admin_user_stats:"))
async def handle_user_stats(callback: CallbackQuery, manager: MessageManager):
    """Displays statistics for a specific user."""
    user_id = int(callback.data.split(":")[1])
    
    stats = data_base.get_user_stats(user_id)
    
    if not stats:
        await callback.answer("Не вдалось отримати статистику користувача.", show_alert=True)
        return
        
    text = f"<b>📊 Статистика користувача {stats['first_name'] or stats['user_name']}</b> (<code>{stats['user_id']}</code>)\n\n"
    text += f"<b>Основна інформація:</b>\n"
    text += f"- Ім'я: {stats['first_name']}\n"
    text += f"- Username: @{stats['user_name']}\n"
    text += f"- Телефон: {stats['phone'] or 'Не вказано'}\n"
    text += f"- Дата реєстрації: {stats['registered_at'][:19]}\n\n"
    
    text += f"<b>Активність:</b>\n"
    text += f"- Завершено замовлень: {stats['completed_orders_count']}\n"
    text += f"- Загальна сума покупок: {stats['total_spent_from_sales']:.2f} €\n"
    text += f"- Товарів в кошику: {stats['cart_items_count']}\n"
    text += f"- Товарів в обраному: {stats['favorites_count']}\n\n"
    
    text += f"<b>Лояльність:</b>\n"
    text += f"- Рівень: {stats['level'] or 'N/A'}\n"
    text += f"- Бали: {stats['loyalty_points']}\n"
    text += f"- Запрошено користувачів: {stats['referrals_count']}"

    builder = InlineKeyboardBuilder()
    builder.button(text="← Назад", callback_data=f"admin_user_details:{user_id}")
    
    await manager.edit(text, reply_markup=builder.as_markup())
    await callback.answer()