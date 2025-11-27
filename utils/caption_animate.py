import asyncio

from aiogram.exceptions import TelegramBadRequest

from utils import logger, MessageManager
from utils.functions import get_caption
from utils.lexicon import caption_intro


async def animate_caption(manager: MessageManager, start_kb, message_id: int, state=None):
    """Анимация текста с постепенным раскрытием"""
    lines = caption_intro.split('\n')
    if not lines:  # Защита от пустого текста
        return

    try:
        for k in range(1, len(lines) + 1):  # Итерация от 1 до длины списка
            await asyncio.sleep(3)  # Задержка между шагами

            if asyncio.current_task().cancelled():
                logger.debug("Анимация прервана (задача отменена)")
                return

            caption = await get_caption(state, k)
            if not caption:  # Если caption пустой, пропускаем шаг
                continue

            try:
                await manager.bot.edit_message_text(
                    chat_id=manager.chat_id,
                    message_id=message_id,
                    text=caption,
                    reply_markup=start_kb
                )
            except TelegramBadRequest as e:
                if "message to edit not found" in str(e):
                    return
                logger.error(f"Ошибка редактирования сообщения: {e}")
                return

    except  TelegramBadRequest as e:
        pass
