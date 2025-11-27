from aiogram.types import BotCommand

from utils import MENU_COMMANDS, ADMIN_COMMANDS, admins
from utils.loader import bot


async def set_main_menu(user_id=None):

    if user_id in admins:
        main_menu_commands = [
            BotCommand(command=command, description=description)
            for command, description in {**MENU_COMMANDS, **ADMIN_COMMANDS}.items()]

    else:
        main_menu_commands = [
            BotCommand(command=command, description=description)
            for command, description in MENU_COMMANDS.items()]
    await bot.set_my_commands(main_menu_commands)

async def update_menu_for_user(user_id: int):
    """Обновляет меню команд для конкретного пользователя"""
    await set_main_menu(user_id)