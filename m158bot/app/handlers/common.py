import asyncio

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from ..services.message_service import MessageService
from ..config import settings
from ..keyboards.inline import get_main_menu_keyboard
from ..services.caption_service import get_start_caption, animate_start_caption

# Создаем роутер для общих команд
router = Router()


@router.message(CommandStart())
async def handle_start(message: Message, message_service: MessageService, state: FSMContext):
    """
    Этот хендлер будет срабатывать на команду /start.
    Он регистрирует пользователя и отправляет приветственное сообщение.
    """
    # --- Остановка предыдущей анимации ---
    data = await state.get_data()
    if "animation_task" in data and data["animation_task"]:
        data["animation_task"].cancel()

    await message.delete()
    
    user_id = message.from_user.id
    
    # Готовим данные для регистрации или обновления
    user_defaults = {
        'first_name': message.from_user.first_name,
        'last_name': message.from_user.last_name,
        'user_name': message.from_user.username
    }
    
    # Проверяем, является ли пользователь админом
    if user_id in settings.bot.admins:
        user_defaults['is_admin'] = True

    user, is_new = await message_service.user_repo.get_or_create(
        user_id=user_id,
        defaults=user_defaults
    )

    # Генерируем текст приветствия через специальный сервис (без анимации для первого сообщения)
    text = await get_start_caption(
        user_full_name=message.from_user.full_name,
        is_new=is_new,
        is_admin=user.is_admin,
        animation_phrase=None # Первая отправка без анимированной строки
    )

    # Путь к фото. Убедитесь, что он правильный относительно корня проекта.
    photo_path = "media/men.jpg" 

    # Генерируем клавиатуру в зависимости от прав пользователя
    keyboard = get_main_menu_keyboard(is_admin=user.is_admin)

    # Отправляем стартовое сообщение
    await message_service.send_media(
        file_path_or_id=photo_path,
        media_type='photo',
        caption=text,
        reply_markup=keyboard
    )

    # --- Запуск новой анимации ---
    animation_task = asyncio.create_task(animate_start_caption(
        user_full_name=message.from_user.full_name,
        is_new=is_new,
        is_admin=user.is_admin,
        message_service=message_service,
        keyboard=keyboard
    ))
    await state.update_data(animation_task=animation_task)
