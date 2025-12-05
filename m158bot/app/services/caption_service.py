import asyncio
import datetime
from itertools import cycle

from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup

from .message_service import MessageService
from ..lexicon import CAPTION_ANIMATION_PHRASES

# Словари для названий месяцев и дней недели на украинском
_MONTHS = {
    1: "січня", 2: "лютого", 3: "березня", 4: "квітня",
    5: "травня", 6: "червня", 7: "липня", 8: "серпня",
    9: "вересня", 10: "жовтня", 11: "листопада", 12: "грудня"
}

_DAYS_OF_WEEK = {
    0: "понеділок", 1: "вівторок", 2: "середа",
    3: "четвер", 4: "п'ятниця", 5: "субота", 6: "неділя"
}

def _get_formatted_date() -> str:
    """Возвращает отформатированную текущую дату."""
    now = datetime.datetime.now()
    day = now.day
    month = _MONTHS[now.month]
    day_of_week = _DAYS_OF_WEEK[now.weekday()]
    return f"{day} {month}, {day_of_week}"


async def get_start_caption(
    user_full_name: str,
    is_new: bool,
    is_admin: bool,
    animation_phrase: str | None = None
) -> str:
    """
    Собирает и возвращает текст приветственного сообщения для команды /start.
    """
    # 1. Формируем приветствие
    if is_new:
        text = f"Добро пожаловать, {user_full_name}!\n\n" \
               f"Вы успешно зарегистрированы."
        if is_admin:
            text += "\n\n**Вам предоставлены права администратора.**"
    else:
        text = f"С возвращением, {user_full_name}!"
        if is_admin:
            text += "\n\nВы вошли как **администратор**."

    # 2. Получаем дату
    formatted_date = _get_formatted_date()

    # 3. Собираем все вместе
    # (В будущем сюда будут добавляться блоки со статистикой, фильтрами и т.д.)
    blocks = [formatted_date, text]
    if animation_phrase:
        blocks.append(f"<i>{animation_phrase}</i>")

    final_caption = "\n\n".join(blocks)
    
    return final_caption


async def animate_start_caption(
    user_full_name: str,
    is_new: bool,
    is_admin: bool,
    message_service: MessageService,
    keyboard: InlineKeyboardMarkup
):
    """
    Анимирует подпись к приветственному сообщению, циклически меняя фразу.
    """
    try:
        # Создаем бесконечный итератор по фразам
        phrase_cycler = cycle(CAPTION_ANIMATION_PHRASES)
        
        while True:
            await asyncio.sleep(3) # Задержка между сменой фраз

            # Получаем следующую фразу
            next_phrase = next(phrase_cycler)
            
            # Генерируем новый текст подписи
            new_caption = await get_start_caption(
                user_full_name=user_full_name,
                is_new=is_new,
                is_admin=is_admin,
                animation_phrase=next_phrase
            )
            
            # Плавно редактируем подпись
            await message_service.edit_caption(
                caption=new_caption,
                reply_markup=keyboard
            )

    except asyncio.CancelledError:
        # Это нормальное завершение, когда задача отменяется (например, при новом /start)
        pass
    except TelegramBadRequest as e:
        # Если сообщение было удалено или что-то пошло не так, просто прекращаем анимацию
        if "message to edit not found" in str(e) or "message is not modified" in str(e):
            pass
        else:
            # В случае других ошибок можно добавить логирование
            pass
    except Exception:
        # Любые другие исключения также просто останавливают анимацию
        pass
