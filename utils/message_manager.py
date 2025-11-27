from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, FSInputFile
from aiogram.exceptions import TelegramBadRequest

# Ленивый импорт для избежания циклических зависимостей
from utils import logger
import os


class MessageManager:
    def __init__(self, bot: Bot, state: FSMContext, chat_id: int):
        self.bot = bot
        self.state = state
        self.chat_id = chat_id

    async def get_active_msg_id(self) -> int | None:
        """Получает ID активного сообщения из FSM или базы данных."""
        try:
            data = await self.state.get_data()
            if "active_msg_id" in data and data["active_msg_id"] is not None:
                logger.debug(f"[CACHE] Получен active_msg_id из FSM: {data['active_msg_id']} (чат: {self.chat_id})")
                return data["active_msg_id"]

            from data_base.models import data_base
            msg_id = data_base.get_active_msg_id(self.chat_id)
            if msg_id is not None:
                logger.debug(f"[DATABASE] Получен active_msg_id из БД: {msg_id} (чат: {self.chat_id})")
                await self.state.update_data(active_msg_id=msg_id)
                return msg_id

            logger.debug(f"[NOT FOUND] Нет active_msg_id для чата: {self.chat_id}")
            return None

        except Exception as e:
            logger.error(f"Ошибка при получении active_msg_id: {e}")
            return None

    async def _update_active_msg_id(self, msg_id: int):
        try:
            await self.state.update_data(active_msg_id=msg_id)
            from data_base.models import data_base
            data_base.set_active_msg_id(self.chat_id, msg_id)
            logger.debug(f"Обновлен active_msg_id в FSM и БД: {msg_id}")
        except Exception as e:
            logger.error(f"Ошибка при обновлении active_msg_id: {e}")

    async def send(self, text: str, reply_markup=None, edit_mode: bool = False) -> Message | None:
        try:
            logger.info(f"Отправка сообщения (edit_mode={edit_mode}) в чат: {self.chat_id}")
            old_msg_id = await self.get_active_msg_id()
            new_msg = None

            if edit_mode and old_msg_id:
                try:
                    new_msg = await self.bot.edit_message_text(
                        chat_id=self.chat_id,
                        message_id=old_msg_id,
                        text=text,
                        reply_markup=reply_markup
                    )
                    logger.info(f"Сообщение {old_msg_id} успешно отредактировано")
                    # Сохраняем тип сообщения
                    await self.state.update_data(active_msg_type='text')
                    return new_msg
                except TelegramBadRequest as e:
                    logger.warning(f"Не удалось отредактировать сообщение {old_msg_id}: {e}")

            # Сначала отправляем новое сообщение
            new_msg = await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                reply_markup=reply_markup
            )

            # Только после успешной отправки нового сообщения удаляем старое
            if old_msg_id and new_msg:
                try:
                    await self.bot.delete_message(self.chat_id, old_msg_id)
                    logger.debug(f"Старое сообщение {old_msg_id} удалено после отправки нового")
                except TelegramBadRequest as e:
                    # logger.warning(f"Не удалось удалить сообщение {old_msg_id}: {e}")
                    pass

            logger.info(f"Новое сообщение отправлено: {new_msg.message_id}")
            await self._update_active_msg_id(new_msg.message_id)
            # Сохраняем тип сообщения
            await self.state.update_data(active_msg_type='text')
            return new_msg

        except Exception as e:
            logger.error(f"Критическая ошибка в send(): {e}")
            return None

    async def edit_reply_markup(self, reply_markup, message_id: int | None = None) -> Message | None:
        """Редактирует только клавиатуру сообщения."""
        try:
            msg_id_to_edit = message_id or await self.get_active_msg_id()
            if not msg_id_to_edit:
                logger.warning("Нет active_msg_id для редактирования клавиатуры")
                return None

            edited_msg = await self.bot.edit_message_reply_markup(
                chat_id=self.chat_id,
                message_id=msg_id_to_edit,
                reply_markup=reply_markup
            )
            logger.info(f"Клавиатура для сообщения {msg_id_to_edit} успешно обновлена")
            return edited_msg
        except Exception as e:
            logger.error(f"Ошибка в edit_reply_markup: {e}")
            return None

    async def edit(self, text: str, reply_markup=None) -> Message | None:
        data = await self.state.get_data()
        msg_type = data.get('active_msg_type', 'text')
        if msg_type != 'text':
            # Было медиа, отправляем новое сообщение
            return await self.send(text, reply_markup)
        return await self.send(text, reply_markup, edit_mode=True)

    async def send_photo_message(self, photo: str, caption: str | None = None, reply_markup=None) -> Message | None:
        try:
            logger.info(f"Отправка фото-сообщения в чат: {self.chat_id}")
            old_msg_id = await self.get_active_msg_id()

            # Убрана проверка длины строки для локальных файлов
            if not isinstance(photo, str):
                logger.warning(f"⚠️ Неверный тип фото: {type(photo)}")
                return await self.send("⚠️ Фото имеет неверный формат.", reply_markup)

            # Проверяем сначала локальный файл
            if os.path.exists(photo):
                photo_input = FSInputFile(photo)
            # Если не файл, считаем это file_id от Telegram
            else:
                photo_input = photo
                # Дополнительная проверка для file_id (опционально)
                if len(photo) < 20:
                    logger.warning(f"⚠️ Короткий file_id: {photo}")
                    return await self.send("⚠️ Неверный идентификатор фото.", reply_markup)

            # Сначала отправляем новое фото-сообщение
            new_msg = await self.bot.send_photo(
                chat_id=self.chat_id,
                photo=photo_input,
                caption=caption,
                reply_markup=reply_markup
            )

            # Только после успешной отправки нового сообщения удаляем старое
            if old_msg_id and new_msg:
                try:
                    await self.bot.delete_message(self.chat_id, old_msg_id)
                    logger.debug(f"Старое сообщение {old_msg_id} удалено после отправки нового фото")
                except TelegramBadRequest as e:
                    pass

            logger.info(f"Новое фото-сообщение отправлено: {new_msg.message_id}")
            await self._update_active_msg_id(new_msg.message_id)
            # Сохраняем тип сообщения
            await self.state.update_data(active_msg_type='photo')
            return new_msg

        except TelegramBadRequest as e:
            logger.error(f"Ошибка при отправке фото: {e}")
            error_text = "Не удалось отправить фото."
            if caption:
                error_text += f"\nОписание: {caption}"
            return await self.send(error_text, reply_markup)

    async def edit_photo_caption(self, caption: str, reply_markup=None,
                                 message_id: int | None = None) -> Message | None:
        try:
            msg_id_to_edit = message_id or await self.get_active_msg_id()
            if not msg_id_to_edit:
                logger.warning("Нет active_msg_id для редактирования")
                return await self.send(caption, reply_markup)

            try:
                edited_msg = await self.bot.edit_message_caption(
                    chat_id=self.chat_id,
                    message_id=msg_id_to_edit,
                    caption=caption,
                    reply_markup=reply_markup
                )
                logger.info(f"Подпись к фото {msg_id_to_edit} успешно обновлена")
                return edited_msg
            except TelegramBadRequest as e:
                logger.warning(f"Не удалось отредактировать подпись фото: {e}")

            try:
                edited_msg = await self.bot.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=msg_id_to_edit,
                    text=caption,
                    reply_markup=reply_markup
                )
                logger.info(f"Сообщение {msg_id_to_edit} отредактировано как текст")
                return edited_msg
            except TelegramBadRequest as e:
                logger.warning(f"Не удалось отредактировать как текст: {e}")

            return await self.send(caption, reply_markup)

        except Exception as e:
            logger.error(f"Ошибка в edit_photo_caption: {e}")
            return None

    async def edit_media(self, media, caption: str | None = None, reply_markup=None,
                        message_id: int | None = None) -> Message | None:
        """Редактирует медиа сообщение"""
        try:
            msg_id_to_edit = message_id or await self.get_active_msg_id()
            if not msg_id_to_edit:
                logger.warning("Нет active_msg_id для редактирования")
                return await self.send_photo_message(media, caption, reply_markup)

            try:
                edited_msg = await self.bot.edit_message_media(
                    chat_id=self.chat_id,
                    message_id=msg_id_to_edit,
                    media=media,
                    reply_markup=reply_markup
                )
                logger.info(f"Медиа сообщение {msg_id_to_edit} успешно отредактировано")
                return edited_msg
            except TelegramBadRequest as e:
                logger.warning(f"Не удалось отредактировать медиа: {e}")
                # Если не удалось отредактировать, отправляем новое
                return await self.send_photo_message(media, caption, reply_markup)

        except Exception as e:
            logger.error(f"Ошибка в edit_media: {e}")
            return None

    async def send_video_message(self, video: str, caption: str | None = None, reply_markup=None) -> Message | None:
        try:
            logger.info(f"Отправка видео-сообщения в чат: {self.chat_id}")
            old_msg_id = await self.get_active_msg_id()

            if not isinstance(video, str):
                logger.warning(f"⚠️ Неверный тип видео: {type(video)}")
                return await self.send("⚠️ Видео имеет неверный формат.", reply_markup)

            if os.path.exists(video):
                video_input = FSInputFile(video)
            else:
                video_input = video
                if len(video) < 20:
                    logger.warning(f"⚠️ Короткий file_id: {video}")
                    return await self.send("⚠️ Неверный идентификатор видео.", reply_markup)

            new_msg = await self.bot.send_video(
                chat_id=self.chat_id,
                video=video_input,
                caption=caption,
                reply_markup=reply_markup
            )

            if old_msg_id and new_msg:
                try:
                    await self.bot.delete_message(self.chat_id, old_msg_id)
                    logger.debug(f"Старое сообщение {old_msg_id} удалено после отправки нового видео")
                except TelegramBadRequest as e:
                    pass

            logger.info(f"Новое видео-сообщение отправлено: {new_msg.message_id}")
            await self._update_active_msg_id(new_msg.message_id)
            await self.state.update_data(active_msg_type='video')
            return new_msg

        except TelegramBadRequest as e:
            logger.error(f"Ошибка при отправке видео: {e}")
            error_text = "Не удалось отправить видео."
            if caption:
                error_text += f"\nОписание: {caption}"
            return await self.send(error_text, reply_markup)

    async def send_document_message(self, document: str, caption: str | None = None, reply_markup=None) -> Message | None:
        """
        Отправляет документ в чат, удаляет старое сообщение, обновляет active_msg_id и тип сообщения.
        """
        try:
            logger.info(f"Отправка документа в чат: {self.chat_id}")
            old_msg_id = await self.get_active_msg_id()

            if not isinstance(document, str):
                logger.warning(f"⚠️ Неверный тип документа: {type(document)}")
                return await self.send("⚠️ Документ имеет неверный формат.", reply_markup)

            if os.path.exists(document):
                document_input = FSInputFile(document)
            else:
                document_input = document
                if len(document) < 20:
                    logger.warning(f"⚠️ Короткий file_id: {document}")
                    return await self.send("⚠️ Неверный идентификатор документа.", reply_markup)

            new_msg = await self.bot.send_document(
                chat_id=self.chat_id,
                document=document_input,
                caption=caption,
                reply_markup=reply_markup
            )

            if old_msg_id and new_msg:
                try:
                    await self.bot.delete_message(self.chat_id, old_msg_id)
                    logger.debug(f"Старое сообщение {old_msg_id} удалено после отправки нового документа")
                except TelegramBadRequest as e:
                    pass

            logger.info(f"Новый документ отправлен: {new_msg.message_id}")
            await self._update_active_msg_id(new_msg.message_id)
            await self.state.update_data(active_msg_type='document')
            return new_msg

        except TelegramBadRequest as e:
            logger.error(f"Ошибка при отправке документа: {e}")
            error_text = "Не удалось отправить документ."
            if caption:
                error_text += f"\nОписание: {caption}"
            return await self.send(error_text, reply_markup)

    async def send_audio_message(self, audio: str, caption: str | None = None, reply_markup=None) -> Message | None:
        try:
            logger.info(f"Отправка аудио в чат: {self.chat_id}")
            old_msg_id = await self.get_active_msg_id()

            if not isinstance(audio, str):
                logger.warning(f"⚠️ Неверный тип аудио: {type(audio)}")
                return await self.send("⚠️ Аудио имеет неверный формат.", reply_markup)

            if os.path.exists(audio):
                audio_input = FSInputFile(audio)
            else:
                audio_input = audio
                if len(audio) < 20:
                    logger.warning(f"⚠️ Короткий file_id: {audio}")
                    return await self.send("⚠️ Неверный идентификатор аудио.", reply_markup)

            new_msg = await self.bot.send_audio(
                chat_id=self.chat_id,
                audio=audio_input,
                caption=caption,
                reply_markup=reply_markup
            )

            if old_msg_id and new_msg:
                try:
                    await self.bot.delete_message(self.chat_id, old_msg_id)
                    logger.debug(f"Старое сообщение {old_msg_id} удалено после отправки нового аудио")
                except TelegramBadRequest as e:
                    pass

            logger.info(f"Новое аудио отправлено: {new_msg.message_id}")
            await self._update_active_msg_id(new_msg.message_id)
            await self.state.update_data(active_msg_type='audio')
            return new_msg

        except TelegramBadRequest as e:
            logger.error(f"Ошибка при отправке аудио: {e}")
            error_text = "Не удалось отправить аудио."
            if caption:
                error_text += f"\nОписание: {caption}"
            return await self.send(error_text, reply_markup)

    async def send_media_message(self, media_type: str, file: str, caption: str | None = None, reply_markup=None) -> Message | None:
        """
        Универсальный метод для отправки любого типа медиа.
        media_type: 'photo', 'video', 'document', 'audio'
        """
        if media_type == 'photo':
            return await self.send_photo_message(file, caption, reply_markup)
        elif media_type == 'video':
            return await self.send_video_message(file, caption, reply_markup)
        elif media_type == 'document':
            return await self.send_document_message(file, caption, reply_markup)
        elif media_type == 'audio':
            return await self.send_audio_message(file, caption, reply_markup)
        else:
            logger.warning(f"Неизвестный тип медиа: {media_type}")
            return await self.send("⚠️ Неизвестный тип медиа.", reply_markup)
