from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

# Создаем роутер для общих команд
router = Router()

@router.message(CommandStart())
async def handle_start(message: Message):
    """
    Этот хендлер будет срабатывать на команду /start
    """
    await message.answer(f"Привет, {message.from_user.full_name}!")
