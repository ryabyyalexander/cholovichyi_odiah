from aiogram.types import Message, CallbackQuery
from aiogram import Router, F

router = Router()


@router.message()
async def send_echo(message: Message):
    try:
        await message.delete()
    except TypeError:
        await message.reply(text='Данный тип апдейтов не поддерживается методом send_copy')


@router.callback_query(F.data == "delete_message")
async def delete_message_callback(callback: CallbackQuery):
    """Удаляет сообщение, к которому привязана кнопка."""
    try:
        await callback.message.delete()
        await callback.answer()
    except Exception as e:
        # Логируем ошибку, если не удалось удалить сообщение
        # (например, оно слишком старое)
        print(f"Could not delete message: {e}")
        await callback.answer("Не удалось удалить сообщение.", show_alert=True)