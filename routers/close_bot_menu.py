from aiogram import Router, Bot, F
from aiogram.types import Message

from keyboards.bot_menu import update_menu_for_user

router = Router()


@router.message(F.text == '/close')
async def del_main_menu(message: Message, bot: Bot):
    await bot.delete_my_commands()
    await message.answer(text='Кнопка "Menu" удалена')


@router.message(F.text == '/open')
async def del_main_menu(message: Message):
    await update_menu_for_user(message.from_user.id)
    await message.answer(text='Кнопка "Menu" добавлена')
