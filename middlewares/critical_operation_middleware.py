import asyncio
import time
import logging
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, CallbackQuery
from typing import Callable, Awaitable, Dict, Any

logger = logging.getLogger(__name__)

class CriticalOperationMiddleware(BaseMiddleware):
    def __init__(self):
        self.processing_operations = {}  # {user_id: operation_type}
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Проверяем только CallbackQuery события
        if not isinstance(event, CallbackQuery):
            return await handler(event, data)

        # Полное исключение для pause/play в слайдере
        if event.data in ("pause", "play"):
            return await handler(event, data)

        user_id = event.from_user.id
        callback_data = event.data
        
        # Определяем критические операции
        critical_operations = [
            "edit_", "set_", "add_size:", "select_qty:", "update_qty:",
            "product_delete:", "product_confirm_delete:", "product_cancel_delete:",
            "media_action:", "detail_edit:", "detail_prev:", "detail_next:",
            "prev", "next", "edit_product", "detail_view:"
        ]
        
        # Проверяем, является ли это критической операцией
        is_critical = any(callback_data.startswith(op) for op in critical_operations)
        
        if is_critical:
            # Проверяем, не выполняется ли уже критическая операция для этого пользователя
            if user_id in self.processing_operations:
                current_operation = self.processing_operations[user_id]
                logger.warning(f"Critical operation already in progress for user {user_id}: {current_operation}, new: {callback_data}")
                try:
                    await event.answer("⏳ Операція вже виконується...", show_alert=False)
                except Exception as e:
                    logger.warning(f"Failed to answer callback for critical operation protection: {e}")
                return
            
            # Отмечаем начало критической операции
            self.processing_operations[user_id] = callback_data
            logger.debug(f"Starting critical operation for user {user_id}: {callback_data}")
            
            try:
                # Выполняем обработчик
                result = await handler(event, data)
                return result
            finally:
                # Убираем отметку о выполнении операции
                if user_id in self.processing_operations:
                    del self.processing_operations[user_id]
                    logger.debug(f"Finished critical operation for user {user_id}: {callback_data}")
        
        # Для некритических операций просто выполняем обработчик
        return await handler(event, data) 