from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from ..services.message_service import MessageService

# Создаем роутер для общих команд
router = Router()


@router.message(CommandStart())
async def handle_start(message: Message, message_service: MessageService):
    """
    Этот хендлер будет срабатывать на команду /start.
    Он регистрирует пользователя и отправляет приветственное сообщение.
    """
    # Middleware уже создал для нас user_repo и передал его в message_service.
    
    user, is_new = await message_service.user_repo.get_or_create(
        user_id=message.from_user.id,
        defaults={
            'first_name': message.from_user.first_name,
            'last_name': message.from_user.last_name,
            'user_name': message.from_user.username
        }
    )

    if is_new:
        text = f"Добро пожаловать, {message.from_user.full_name}!\n\n" \
               f"Вы успешно зарегистрированы."
    else:
        text = f"С возвращением, {message.from_user.full_name}!"

    await message_service.send_message(text)
    await message.delete()
