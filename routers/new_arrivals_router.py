from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from data_base.models import data_base
from utils.filter_manager import FilterManager
from utils.slider_manager import SliderManager, format_media
from utils.message_manager import MessageManager

router = Router()


@router.message(Command("new"))
async def new_arrivals_handler(message: Message, state: FSMContext, manager: MessageManager):
    """
    Обработчик команды /new.
    Очищает фильтры, устанавливает фильтр на 'надходження' и запускает слайдер.
    """
    # Очищаем все предыдущие фильтры для чистоты
    await FilterManager.clear_all_filters(state)

    # Программно устанавливаем фильтр на новинки
    await FilterManager.set_filter(state, 'season', 'надходження')

    # Получаем активные фильтры (теперь там только 'season': 'надходження')
    active_filters = await FilterManager.get_active_filters(state)

    # Получаем товары по этому фильтру
    product_media = data_base.get_filtered_product_media(**active_filters)

    if not product_media:
        await manager.send("😔 На жаль, зараз немає новинок.")
        return

    # Сохраняем найденные медиа в состояние
    await state.update_data(product_media=product_media)

    # Получаем корзину пользователя
    user_id = message.from_user.id
    cart_items = data_base.get_cart(user_id)
    await state.update_data(cart_items=cart_items)

    # Форматируем данные и запускаем слайдер
    media, ids = format_media(product_media)
    slider_manager = SliderManager(manager, state)
    await slider_manager.start_slider(
        media_list=media,
        product_ids=ids,
        source="main",  # Источник как будто зашли с главного меню
        user_id=user_id,
        cart_items=cart_items,
        breadcrumbs="main"
    )
    await message.delete()
