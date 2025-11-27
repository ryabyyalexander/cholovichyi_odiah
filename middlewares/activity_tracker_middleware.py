import logging
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, CallbackQuery, Message
from typing import Callable, Awaitable, Dict, Any

logger = logging.getLogger(__name__)

class ActivityTrackerMiddleware(BaseMiddleware):
    """
    Middleware для отслеживания активности пользователей.
    Увеличивает счетчик активности при каждом взаимодействии с ботом.
    """
    
    def __init__(self, database=None):
        super().__init__()
        self.database = database

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем user_id из события
        user_id = None
        
        if isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            action_data = event.data
        elif isinstance(event, Message):
            user_id = event.from_user.id
            action_data = event.text or ""
        else:
            # Для других типов событий пропускаем
            return await handler(event, data)

        # Отслеживаем любой клик (кроме команд)
        if self._should_track_activity(action_data) and self.database:
            try:
                # Увеличиваем счетчик активности с использованием константы из lexicon
                from utils.lexicon import DISCOUNT_SETTINGS
                weight = DISCOUNT_SETTINGS['CLICK_ACTIVITY_WEIGHT']
                self.database.increment_activity_count(user_id, weight)
                    
                logger.debug(f"Activity tracked for user {user_id}: {action_data} (+{weight} point)")
            except Exception as e:
                logger.error(f"Failed to track activity for user {user_id}: {e}")

        return await handler(event, data)



    def _should_track_activity(self, action_data: str) -> bool:
        """
        Проверяет, нужно ли отслеживать данное действие как активность.
        Теперь отслеживаем любой клик, кроме команд.
        
        Args:
            action_data: Данные действия (callback_data или текст сообщения)
            
        Returns:
            True если действие нужно отслеживать, False если исключение
        """
        if not action_data:
            return False
            
        # Исключаем только команды
        if action_data.startswith('/'):
            return False
            
        # Исключаем пустые или системные сообщения
        if action_data in ['', 'None', 'null']:
            return False
            
        # Все остальные действия считаем активностью
        return True 