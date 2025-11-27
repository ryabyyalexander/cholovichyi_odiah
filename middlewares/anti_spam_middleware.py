import asyncio
import time
import logging
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, CallbackQuery
from typing import Callable, Awaitable, Dict, Any

logger = logging.getLogger(__name__)

class AntiSpamMiddleware(BaseMiddleware):
    def __init__(self, cooldown: float = 0.3):
        self.cooldown = cooldown
        self.user_timestamps = {}  # {user_id: last_click_time}
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
        current_time = time.time()
        
        # Минимальная задержка для кнопок слайдера (кроме pause/play)
        slider_buttons = ("prev", "next")
        effective_cooldown = 0.1 if event.data in slider_buttons else self.cooldown
        
        # Проверяем, не слишком ли рано пользователь нажал кнопку
        if user_id in self.user_timestamps:
            time_since_last_click = current_time - self.user_timestamps[user_id]
            if time_since_last_click < effective_cooldown:
                remaining_time = effective_cooldown - time_since_last_click
                logger.debug(f"Spam protection: user {user_id} clicked too fast ({time_since_last_click:.2f}s < {effective_cooldown}s), callback_data: {event.data}")
                # Отвечаем на callback, чтобы убрать "часики" у кнопки
                try:
                    await event.answer(f"⏳ Зачекайте {remaining_time:.1f}с...", show_alert=False)
                except Exception as e:
                    logger.warning(f"Failed to answer callback for spam protection: {e}")
                return
        
        # Обновляем время последнего клика
        self.user_timestamps[user_id] = current_time
        
        # Очищаем старые записи (старше 1 минуты) для экономии памяти
        self._cleanup_old_records(current_time)
        
        logger.debug(f"Processing callback for user {user_id}: {event.data}")
        return await handler(event, data)
    
    def _cleanup_old_records(self, current_time: float):
        """Очищает старые записи для экономии памяти"""
        cutoff_time = current_time - 60  # Удаляем записи старше 1 минуты
        keys_to_remove = [
            user_id for user_id, timestamp in self.user_timestamps.items()
            if timestamp < cutoff_time
        ]
        for key in keys_to_remove:
            del self.user_timestamps[key]
        
        if keys_to_remove:
            logger.debug(f"Cleaned up {len(keys_to_remove)} old spam protection records") 