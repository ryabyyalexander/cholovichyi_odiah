import asyncio
import logging

from app.loader import dp, bot, engine
from app.handlers import common
from app.db.models import create_tables

async def main():
    """Основная функция для запуска бота"""
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

    # Создание таблиц в базе данных
    await create_tables(engine)
    
    # Регистрация роутеров
    dp.include_router(common.router)
    
    # Удаление вебхука (если он был установлен) и запуск polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())