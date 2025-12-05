from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from ..services.message_service import MessageService
from ..config import settings

# Создаем роутер для общих команд
router = Router()


@router.message(CommandStart())
async def handle_start(message: Message, message_service: MessageService):
    """
    Этот хендлер будет срабатывать на команду /start.
    Он регистрирует пользователя и отправляет приветственное сообщение.
    """
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

    if is_new:
        text = f"Добро пожаловать, {message.from_user.full_name}!\n\n" \
               f"Вы успешно зарегистрированы."
        if user.is_admin:
            text += "\n\n**Вам предоставлены права администратора.**"
    else:
        text = f"С возвращением, {message.from_user.full_name}!"
        if user.is_admin:
            text += "\n\nВы вошли как **администратор**."

    # Путь к фото. Убедитесь, что он правильный относительно корня проекта.
    photo_path = "media/men.jpg" 

    await message_service.send_media(
        file_path_or_id=photo_path,
        media_type='photo',
        caption=text
    )
    await message.delete()
