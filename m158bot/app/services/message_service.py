import os
from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, FSInputFile, InputMediaPhoto, InputMediaVideo
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

    def _get_file_input(self, file_path_or_id: str):
        """Определяет, является ли файл локальным путем или file_id."""
        if os.path.exists(file_path_or_id):
            return FSInputFile(file_path_or_id)
        return file_path_or_id

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
                return edited_msg
            except TelegramBadRequest:
                pass

        # Отправляем новое сообщение
        new_msg = await self.bot.send_message(
            chat_id=self.chat_id,
            text=text,
            reply_markup=reply_markup
        )

        if old_msg_id:
            try:
                await self.bot.delete_message(self.chat_id, old_msg_id)
            except TelegramBadRequest:
                pass

        await self._update_active_message(new_msg.message_id, 'text')
        return new_msg

    async def send_media(
        self,
        file_path_or_id: str,
        media_type: str = 'photo',
        caption: str = None,
        reply_markup: InlineKeyboardMarkup = None
    ) -> Message:
        """
        Отправляет медиа-сообщение (фото/видео), заменяя предыдущее.
        """
        old_msg_id, old_msg_type = await self._get_active_message()
        file_input = self._get_file_input(file_path_or_id)

        # Пытаемся отредактировать, если старое сообщение тоже было медиа
        if old_msg_id and old_msg_type in ('photo', 'video'):
            try:
                media: InputMediaPhoto | InputMediaVideo
                if media_type == 'photo':
                    media = InputMediaPhoto(media=file_input, caption=caption)
                elif media_type == 'video':
                    media = InputMediaVideo(media=file_input, caption=caption)
                else: # Если тип не поддерживается для редактирования, отправляем новое
                    raise TelegramBadRequest("Unsupported media type for editing")

                edited_msg = await self.bot.edit_message_media(
                    chat_id=self.chat_id,
                    message_id=old_msg_id,
                    media=media,
                    reply_markup=reply_markup
                )
                await self._update_active_message(edited_msg.message_id, media_type)
                return edited_msg
            except TelegramBadRequest:
                pass # Если не удалось отредактировать, просто отправляем новое

        # Отправляем новое медиа-сообщение
        new_msg: Message
        if media_type == 'photo':
            new_msg = await self.bot.send_photo(
                chat_id=self.chat_id,
                photo=file_input,
                caption=caption,
                reply_markup=reply_markup
            )
        elif media_type == 'video':
            new_msg = await self.bot.send_video(
                chat_id=self.chat_id,
                video=file_input,
                caption=caption,
                reply_markup=reply_markup
            )
        else:
            # В качестве запасного варианта отправляем текстовое сообщение об ошибке
            return await self.send_message(f"Ошибка: неизвестный тип медиа '{media_type}'")

        # После успешной отправки нового, удаляем старое
        if old_msg_id:
            try:
                await self.bot.delete_message(self.chat_id, old_msg_id)
            except TelegramBadRequest:
                pass

        await self._update_active_message(new_msg.message_id, media_type)
        return new_msg

    async def edit_caption(self, caption: str, reply_markup: InlineKeyboardMarkup = None) -> Message:
        """Редактирует подпись к существующему медиа-сообщению."""
        old_msg_id, old_msg_type = await self._get_active_message()

        if old_msg_id and old_msg_type in ('photo', 'video'):
            try:
                edited_msg = await self.bot.edit_message_caption(
                    chat_id=self.chat_id,
                    message_id=old_msg_id,
                    caption=caption,
                    reply_markup=reply_markup
                )
                return edited_msg
            except TelegramBadRequest:
                # Если не удалось (например, у сообщения нет caption),
                # то заменяем его на текстовое
                return await self.send_message(caption, reply_markup)
        else:
            # Если старое сообщение было текстовым или его не было,
            # просто отправляем новое текстовое сообщение
            return await self.send_message(caption, reply_markup)
