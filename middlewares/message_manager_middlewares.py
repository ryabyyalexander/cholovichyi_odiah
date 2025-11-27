# middlewares/message_manager_middleware.py

from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject, Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from typing import Callable, Awaitable, Dict, Any

from utils import logger
from utils.message_manager import MessageManager



class MessageManagerMiddleware(BaseMiddleware):
    def __init__(self, bot: Bot):
        self.bot = bot
        logger.debug("MessageManagerMiddleware initialized")

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, Message):
            chat_id = event.chat.id
            logger.debug(f"Processing Message event in chat: {chat_id}")
        elif isinstance(event, CallbackQuery):
            chat_id = event.message.chat.id
            logger.debug(f"Processing CallbackQuery event in chat: {chat_id}")
        else:
            logger.debug(f"Skipping unsupported event type: {type(event)}")
            return await handler(event, data)

        state: FSMContext = data.get("state")
        if not state:
            logger.warning(f"No FSMContext found for chat: {chat_id}")
            return await handler(event, data)

        logger.debug(f"Creating MessageManager for chat: {chat_id}")
        data["manager"] = MessageManager(
            bot=self.bot,
            state=state,
            chat_id=chat_id
        )

        return await handler(event, data)