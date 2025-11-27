from aiogram import Dispatcher

from . import (
    user_block_bot,
    close_bot_menu,
    start_router, new_arrivals_router, registration_router, admin_router, create_product_router,
    saves_id_media_router,
    edit_product_router,
    edit_media_router,
    slider_router,
    echo_router,
    navigation_router, profile_router, admin_panel_router,
    product_view_router, orders_router, subscription_router
)


def register_all_routers(dp: Dispatcher) -> None:
    """
    Регистрирует все роутеры в диспетчере.
    """
    dp.include_router(user_block_bot.router)
    dp.include_router(close_bot_menu.router)
    dp.include_router(start_router.router)
    dp.include_router(new_arrivals_router.router)
    dp.include_router(admin_router.router)
    dp.include_router(registration_router.router)
    dp.include_router(profile_router.router)
    dp.include_router(orders_router.router)
    dp.include_router(create_product_router.router)
    dp.include_router(saves_id_media_router.router)
    dp.include_router(navigation_router.router)
    dp.include_router(product_view_router.router)
    dp.include_router(edit_product_router.router)
    dp.include_router(edit_media_router.router)
    dp.include_router(slider_router.router)
    dp.include_router(admin_panel_router.router)
    dp.include_router(subscription_router.router)
    dp.include_router(echo_router.router)
