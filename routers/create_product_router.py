from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile, InputMediaPhoto, InputMediaVideo

from data_base.models import data_base
from enums import MainMenu
from enums.create_product_enum import CreateProduct
from filters import IsAdmin
from fsm.states import State_add_photo
from keyboards.kb import create_keyboard, NavigationCallback

from utils.message_manager import MessageManager
from utils import safe_delete_message, logger
from utils.slider_manager import SliderManager
import asyncio

router = Router()


@router.message(((F.text == 'Создать товар') | (F.text == '+') | (F.text == 'П') | (F.text == 'п') | (F.text == 'g') | (F.text == 'G')), IsAdmin)
async def start_loader(message: Message, state: FSMContext):
    """Начинает процесс загрузки товаров"""
    await state.set_state(State_add_photo.start)
    await state.update_data(media_list=[])
    await message.delete()

    await message.answer_photo(
        photo=FSInputFile('media/men.jpg'),
        caption='Загрузите фото товаров',
        reply_markup=create_keyboard(CreateProduct, "", "create_product", add_back=False, adjust=(1,))
    )


@router.callback_query(F.data == "admin_add_product", IsAdmin)
async def start_loader_callback(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    """Начинает процесс загрузки товаров по кнопке из админ-панели"""
    await state.set_state(State_add_photo.start)
    await state.update_data(media_list=[])
    await manager.send_photo_message(
        photo='media/men.jpg',
        caption='Загрузите фото товаров',
        reply_markup=create_keyboard(CreateProduct, "", "create_product", add_back=False, adjust=(1,))
    )
    await callback.answer()


@router.callback_query(
    NavigationCallback.filter(F.action == "create_product"),
    StateFilter(State_add_photo.start)
)
async def handle_product_creation(
    callback: CallbackQuery,
    state: FSMContext,
    callback_data: NavigationCallback
):
    await callback.answer()
    data = await state.get_data()
    media_list = data.get('media_list', [])

    if not media_list:
        await callback.answer()
        msg = await callback.message.answer('⚠️ Сначала загрузите фото')
        await safe_delete_message(msg, 2)
        return

    try:
        message_manager = MessageManager(callback.bot, state, callback.message.chat.id)
        slider_manager = SliderManager(message_manager, state)
        if callback_data.current_level == CreateProduct.ONE.value:
            product_ids = data_base.create_products_with_media(media_list, create_separate=False)
            await slider_manager.start_slider(
                media_list,
                product_ids=[product_ids[0]] * len(media_list),
                user_id=callback.from_user.id,
                breadcrumbs="main"
            )
            # data = await state.get_data()
            # if data.get("playing"):
            #     await asyncio.create_task(slider_manager.autoplay_slideshow())
        elif callback_data.current_level == CreateProduct.MORE.value:
            product_ids = data_base.create_products_with_media(media_list, create_separate=True)
            await slider_manager.start_slider(media_list, product_ids=product_ids, user_id=callback.from_user.id, breadcrumbs="main")
            # data = await state.get_data()
            # if data.get("playing"):
            #     await asyncio.create_task(slider_manager.autoplay_slideshow())
        elif callback_data.current_level == CreateProduct.PHOTO.value:
            await slider_manager.start_slider(media_list, user_id=callback.from_user.id, breadcrumbs="main")
            # data = await state.get_data()
            # if data.get("playing"):
            #     await asyncio.create_task(slider_manager.autoplay_slideshow())

        await callback.message.delete()
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await callback.answer("⚠️ Ошибка при создании слайдера", show_alert=True)
    # finally:
    #     await state.clear()


async def update_message_with_media(message: Message, media_data: dict, caption: str):
    """Обновляет сообщение с медиа и подписью"""
    media_class = InputMediaPhoto if media_data['type_media'] == 'photo' else InputMediaVideo
    await message.edit_media(
        media=media_class(
            media=media_data['path'],
            caption=caption
        ),
        reply_markup=create_keyboard(MainMenu, "", "main")
    )

