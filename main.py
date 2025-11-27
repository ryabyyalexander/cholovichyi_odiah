from utils.loader import dp, bot, on_startup, on_shutdown
from keyboards.bot_menu import set_main_menu
from routers.router import register_all_routers

if __name__ == "__main__":
    dp.startup.register(set_main_menu)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    register_all_routers(dp)

    dp.run_polling(bot)
