from typing import Callable, Awaitable, Dict, Any

from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy.ext.asyncio import async_sessionmaker

from ..db.repositories.user import UserRepository
from ..services.message_service import MessageService


class MessageServiceMiddleware(BaseMiddleware):
    """
    Middleware для внедрения MessageService в обработчики.
    """

    def __init__(self, session_pool: async_sessionmaker):
        self.session_pool = session_pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        
        if isinstance(event, (Message, CallbackQuery)):
            user = data.get("event_from_user")
            chat = data.get("event_chat")
            
            if not user or not chat:
                return await handler(event, data)

            async with self.session_pool() as session:
                user_repo = UserRepository(session)
                
                data["message_service"] = MessageService(
                    bot=data['bot'],
                    state=data['state'],
                    user_repo=user_repo,
                    chat_id=chat.id,
                    user_id=user.id
                )
                return await handler(event, data)
        
        return await handler(event, data)
