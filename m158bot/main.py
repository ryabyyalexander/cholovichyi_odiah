import asyncio
import logging

from app.loader import dp, bot, engine, db_session_factory
from app.handlers import common
from app.db.models import create_tables
from app.middlewares.message_middleware import MessageServiceMiddleware

async def main():
    """Основная функция для запуска бота"""
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

    # Создание таблиц в базе данных
    await create_tables(engine)

    # Применяем middleware к роутеру
    # Это гарантирует, что он будет работать для всех хендлеров в common.router
    common.router.message.middleware(MessageServiceMiddleware(session_pool=db_session_factory))
    common.router.callback_query.middleware(MessageServiceMiddleware(session_pool=db_session_factory))

    # Регистрация роутеров
    dp.include_router(common.router)
    
    # Удаление вебхука (если он был установлен) и запуск polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())