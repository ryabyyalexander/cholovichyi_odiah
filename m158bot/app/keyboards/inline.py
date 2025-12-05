from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup


def get_main_menu_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    """
    Генерирует главное меню в зависимости от прав пользователя.
    """
    builder = InlineKeyboardBuilder()

    # Добавляем кнопки, которые видят все пользователи
    builder.button(text="Каталог", callback_data="catalog")
    builder.button(text="Профіль", callback_data="profile")

    # Если пользователь - админ, добавляем админ-кнопку
    if is_admin:
        builder.button(text="Адмін-панель", callback_data="admin_panel")

    # Расставляем кнопки в рядах. Если есть админ-кнопка, будет 3 в ряд, иначе - 2.
    builder.adjust(3 if is_admin else 2)

    return builder.as_markup()
