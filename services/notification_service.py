"""
Сервис для отправки уведомлений администраторам.
"""

from utils import admins
from aiogram import Bot
from data_base.models import data_base
from utils.loader import bot
import json
import asyncio
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.category_utils import get_category_label, get_subcategory_label
from utils import logger

class NotificationService:
    """Сервис для отправки уведомлений администраторам"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
    
    async def notify_new_order(self, order_id: int, user_id: int, total_amount: float, 
                              items_count: int, user_name: str, cart_items: list) -> None:
        """
        Отправляет уведомление всем админам о новом заказе.
        
        Args:
            order_id: ID заказа
            user_id: ID пользователя
            total_amount: Общая сумма заказа
            items_count: Количество товаров
            user_name: Имя пользователя
        """
        try:
            # Получаем полную информацию о клиенте
            user_info = data_base.sql_get_user(user_id, 'first_name', 'last_name', 'user_name', 'phone', 'is_active')
            
            # Получаем детали заказа
            order_details = data_base.get_order_details(order_id)
            
            # Формируем информацию о клиенте
            client_info = self._format_client_info(user_info, user_id)
            
            # Формируем информацию о корзине
            cart_info = self._format_cart_info(order_details, cart_items)
            
            # Формируем текст уведомления
            notification_text = (
                f"<blockquote>\n"
                f"🚀 <b>Новый заказ #{order_id}</b>\n\n"
                f"{client_info}\n"
                f"📦 <b>ЗАКАЗ:</b>\n{cart_info}\n"
                f"\n⏰ Время: {self._get_current_time()}\n"
                f"</blockquote>"
            )
            
            # Создаем кнопки
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Підтвердити", callback_data=f"direct_order_confirm:{order_id}"),
                    InlineKeyboardButton(text="Резерв", callback_data=f"reserve_order:{order_id}"),
                    InlineKeyboardButton(text="❌ Скасувати", callback_data=f"direct_order_cancel:{order_id}")
                ],
                [
                    InlineKeyboardButton(text="Закрыть", callback_data="delete_message")
                ]
            ])

            # Отправляем уведомление всем админам
            for admin_id in admins:
                try:
                    await self.bot.send_message(
                        chat_id=admin_id,
                        text=notification_text,
                        parse_mode="HTML",
                        reply_markup=keyboard
                    )
                    logger.info(f"Уведомление о заказе {order_id} отправлено админу {admin_id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Ошибка в notify_new_order: {e}")
    
    def _format_client_info(self, user_info: tuple, user_id: int) -> str:
        """Форматирует информацию о клиенте"""
        if not user_info:
            return f"🆔 ID: {user_id}\n❌ Данные не найдены"
        
        first_name, last_name, username, phone, is_active = user_info
        
        # Формируем имя
        full_name = ""
        if first_name and last_name:
            full_name = f"{first_name} {last_name}"
        elif first_name:
            full_name = first_name
        elif last_name:
            full_name = last_name
        else:
            full_name = "Не указано"
        
        # Формируем username
        username_text = f"@{username}" if username else ""
        
        # Телефон
        phone_text = phone if phone else "Не указан"
        
        # Итоговая строка: имя, телефон, username (без ID и статуса)
        result = f"👤  {full_name}\n"
        result += f"📱   Телефон: {phone_text}\n"
        if username_text:
            result += f"{username_text}\n"
        return result
    
    def _format_cart_info(self, order_details: dict, cart_items: list) -> str:
        """Форматирует информацию о корзине в стиле главной страницы"""
        if not order_details:
            return "❌ Данные заказа не найдены"
        
        items = cart_items
        total_amount = order_details.get('total_amount', 0)
        discount_amount = order_details.get('discount_amount', 0)
        final_amount = order_details.get('final_amount', 0)
        
        # Формируем список товаров в стиле корзины
        items_text = ""
        for i, item in enumerate(items, 1):
            product_name = item.get('name', 'Неизвестный товар')
            product_id = item.get('product_id', 0)
            category = item.get('category', '')
            subcategory = item.get('subcategory', '')
            size_value = item.get('size_value', '')
            quantity = item.get('quantity', 1)
            unit_price = item.get('unit_price', 0)
            total_price = item.get('total_price', 0)
            
            # Формируем категорию/подкатегорию
            category_info = ""
            if category and subcategory:
                category_info = f"{category}/{subcategory}"
            elif category:
                category_info = category
            elif subcategory:
                category_info = subcategory
            
            # Формируем строку товара в стиле корзины
            item_line = f"{i} /ID_{product_id} {category_info}"
            if size_value:
                item_line += f"\n{size_value} розм. {quantity} шт. x {unit_price:.2f} €"
            else:
                item_line += f" {quantity} шт. x {unit_price:.2f} €"
            
            items_text += item_line + "\n\n"
        
        # Формируем итоговую информацию
        summary = f"Сума: {total_amount:.2f} €"
        
        if discount_amount > 0:
            summary += f"\nПерсональна знижка - {discount_amount:.2f} €"
        
        summary += f"\n\nК оплате: {final_amount:.2f} €"
        
        return f"{items_text}{summary}"
    
    async def notify_order_confirmed(self, order_id: int, user_id: int, admin_name: str) -> None:
        """
        Отправляет уведомление пользователю о подтверждении заказа и начисляет баллы лояльности.

        Args:
            order_id: ID заказа
            user_id: ID пользователя
            admin_name: Имя администратора
        """
        try:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            from services.loyalty_service import LoyaltyService

            # --- ИНТЕГРАЦИЯ СИСТЕМЫ ЛОЯЛЬНОСТИ ---
            order_details = data_base.get_order_details(order_id)
            points_earned_text = ""

            if not order_details:
                logger.error(f"Не удалось получить детали заказа {order_id} для начисления баллов.")
                notification_text = (
                    f"<blockquote>"
                    f"✅ <b>Заказ #{order_id} подтвержден!</b>\n\n"
                    f"Ваш заказ был обработан администратором {admin_name}.\n"
                    f"Ожидайте звонка для уточнения деталей доставки."
                    f"</blockquote>"
                )
            else:
                final_amount = order_details['final_amount']

                loyalty_service = LoyaltyService(data_base)
                points_earned = loyalty_service.add_points_for_purchase(user_id, final_amount)
                points_earned_text = f"\n\n<b>⭐ Начислено баллов лояльности: {points_earned}</b>"

                # Проверка на реферальный бонус
                user_data = data_base.sql_get_user(user_id, 'referrer_id', 'total_spent')
                if user_data:
                    referrer_id, total_spent = user_data
                    if referrer_id and total_spent == final_amount:
                        loyalty_service.add_referral_bonus(referrer_id, user_id)

                notification_text = (
                    f"<blockquote>"
                    f"✅ <b>Заказ #{order_id} подтвержден!</b>\n\n"
                    f"Ваш заказ был обработан администратором {admin_name}.\n"
                    f"Ожидайте звонка для уточнения деталей доставки."
                    f"{points_earned_text}"
                    f"</blockquote>"
                )
            # --- КОНЕЦ ИНТЕГРАЦИИ ---

            close_button = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Закрыть", callback_data="delete_message")]
            ])

            await self.bot.send_message(
                chat_id=user_id,
                text=notification_text,
                parse_mode="HTML",
                reply_markup=close_button
            )
            logger.info(f"Уведомление о подтверждении заказа {order_id} отправлено пользователю {user_id}")

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о подтверждении заказа: {e}")
    
    async def notify_order_cancelled(self, order_id: int, user_id: int, reason: str) -> None:
        """
        Отправляет уведомление пользователю об отмене заказа.
        
        Args:
            order_id: ID заказа
            user_id: ID пользователя
            reason: Причина отмены
        """
        try:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

            notification_text = (
                f"<blockquote>"
                f"❌ <b>Заказ #{order_id} отменен</b>\n\n"
                f"Причина: {reason}\n\n"
                f"Если у вас есть вопросы, свяжитесь с администрацией."
                f"</blockquote>"
            )
            
            close_button = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Закрыть", callback_data="delete_message")]
            ])

            await self.bot.send_message(
                chat_id=user_id,
                text=notification_text,
                parse_mode="HTML",
                reply_markup=close_button
            )
            logger.info(f"Уведомление об отмене заказа {order_id} отправлено пользователю {user_id}")
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления об отмене заказа: {e}")
    
    async def notify_low_stock(self, product_id: int, product_name: str, 
                              size_value: str, current_quantity: int) -> None:
        """
        Отправляет уведомление админам о низком остатке товара.
        
        Args:
            product_id: ID товара
            product_name: Название товара
            size_value: Размер
            current_quantity: Текущее количество
        """
        try:
            notification_text = (
                f"⚠️ <b>Низкий остаток товара</b>\n\n"
                f"📦 Товар: {product_name}\n"
                f"🆔 ID: {product_id}\n"
                f"📏 Размер: {size_value}\n"
                f"🔢 Остаток: {current_quantity} шт.\n\n"
                f"Рекомендуется пополнить склад."
            )
            
            for admin_id in admins:
                try:
                    await self.bot.send_message(
                        chat_id=admin_id,
                        text=notification_text,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления о низком остатке админу {admin_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Ошибка в notify_low_stock: {e}")
    
    async def notify_product_activated(self, product_id: int, product_name: str, 
                                     admin_name: str) -> None:
        """
        Отправляет уведомление админам об активации товара.
        
        Args:
            product_id: ID товара
            product_name: Название товара
            admin_name: Имя администратора
        """
        try:
            notification_text = (
                f"✅ <b>Товар активирован</b>\n\n"
                f"📦 Товар: {product_name}\n"
                f"🆔 ID: {product_id}\n"
                f"👤 Активировал: {admin_name}\n\n"
                f"Товар теперь виден пользователям."
            )
            
            for admin_id in admins:
                try:
                    await self.bot.send_message(
                        chat_id=admin_id,
                        text=notification_text,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления об активации товара админу {admin_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Ошибка в notify_product_activated: {e}")
    
    def _get_current_time(self) -> str:
        """Возвращает текущее время в удобном формате"""
        from datetime import datetime
        return datetime.now().strftime("%d.%m.%Y %H:%M")

async def trigger_discount_notifications(product_id: int, new_discount: int):
    """
    Finds users subscribed to size-based discounts for a given product
    and sends them a notification.
    """
    product = data_base.sql_get_product(product_id)
    if not product or not product.get('is_active'):
        return

    available_sizes = data_base.get_available_sizes(product_id)
    product_sizes = set(available_sizes.keys())

    if not product_sizes:
        return

    subscribers = data_base.get_subscribers('size_discounts')

    for sub_info in subscribers:
        user_id = sub_info['user_id']
        if not sub_info['filters']:
            continue

        try:
            filters = json.loads(sub_info['filters'])
        except json.JSONDecodeError:
            continue

        subscribed_sizes = set(filters.values())
        matching_sizes = subscribed_sizes.intersection(product_sizes)

        if matching_sizes:
            # This user is subscribed to a size that is available for this product
            product_name = product['name']
            category = get_category_label(product['category'])
            subcategory = get_subcategory_label(product['category'], product['subcategory'])
            sale_price = product['sale_price']
            new_discount_price = round(sale_price - (sale_price * new_discount / 100), 2)
            size_str = ", ".join(matching_sizes)

            text = (
                f"<blockquote>"
                f"🔥 <b>Скидка на товар вашего размера!</b>\n\n"
                f"/ID_{product_id} {category}/{subcategory}\n"
                f"<b>{product_name}</b>\n"
                f"Размер: <b>{size_str}</b>\n\n"
                f"Старая цена: <code>{sale_price} €</code>\n"
                f"Новая скидка: <b>{new_discount}%</b>\n"
                f"Новая цена: <b>{new_discount_price} €</b>"
                f"</blockquote>"
            )

            builder = InlineKeyboardBuilder()
            builder.button(text="Закрыть", callback_data="delete_message")

            try:
                main_photo_id = data_base.get_main_product_photo(product_id)
                if main_photo_id:
                    await bot.send_photo(
                        chat_id=user_id,
                        photo=main_photo_id,
                        caption=text,
                        parse_mode="HTML",
                        reply_markup=builder.as_markup()
                    )
                else:
                    await bot.send_message(user_id, text, parse_mode="HTML", reply_markup=builder.as_markup())

                await asyncio.sleep(0.1)  # simple anti-spam measure
            except Exception as e:
                logger.error(f"Failed to send notification to {user_id}: {e}")
                pass