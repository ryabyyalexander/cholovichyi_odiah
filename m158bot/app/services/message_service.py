from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest

from ..db.repositories.user import UserRepository


class MessageService:
    """
    Сервис для управления сообщениями, реализующий "режим чистой ленты".
    """

    def __init__(self, bot: Bot, state: FSMContext, user_repo: UserRepository, chat_id: int, user_id: int):
        self.bot = bot
        self.state = state
        self.user_repo = user_repo
        self.chat_id = chat_id
        self.user_id = user_id

    async def _get_active_message(self) -> tuple[int | None, str | None]:
        """Получает ID и тип активного сообщения (сначала из FSM, потом из БД)."""
        data = await self.state.get_data()
        msg_id = data.get("active_msg_id")
        msg_type = data.get("active_msg_type")

        if msg_id is not None:
            return msg_id, msg_type

        user = await self.user_repo.get_one_or_none(user_id=self.user_id)
        if user and user.active_msg_id:
            await self.state.update_data(active_msg_id=user.active_msg_id, active_msg_type=user.active_msg_type)
            return user.active_msg_id, user.active_msg_type

        return None, None

    async def _update_active_message(self, msg_id: int, msg_type: str):
        """Обновляет ID и тип активного сообщения в FSM и БД."""
        await self.state.update_data(active_msg_id=msg_id, active_msg_type=msg_type)
        await self.user_repo.update_message_info(self.user_id, msg_id, msg_type)

    async def send_message(self, text: str, reply_markup: InlineKeyboardMarkup = None) -> Message:
        """
        Отправляет текстовое сообщение, заменяя предыдущее "активное" сообщение.
        """
        old_msg_id, old_msg_type = await self._get_active_message()

        # Если старое сообщение было текстовым, пытаемся его отредактировать
        if old_msg_id and old_msg_type == 'text':
            try:
                edited_msg = await self.bot.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=old_msg_id,
                    text=text,
                    reply_markup=reply_markup
                )
                # Тип не менялся, ID тот же, обновлять не нужно, если только не было ошибки
                return edited_msg
            except TelegramBadRequest:
                # Ошибка может возникнуть, если сообщение то же самое или его не существует.
                # В этом случае, мы просто продолжаем и отправляем новое.
                pass

        # Отправляем новое сообщение
        new_msg = await self.bot.send_message(
            chat_id=self.chat_id,
            text=text,
            reply_markup=reply_markup
        )

        # После успешной отправки нового, удаляем старое
        if old_msg_id:
            try:
                await self.bot.delete_message(self.chat_id, old_msg_id)
            except TelegramBadRequest:
                pass  # Ничего страшного, если не удалось удалить

        # Обновляем информацию о новом активном сообщении
        await self._update_active_message(new_msg.message_id, 'text')
        return new_msg
