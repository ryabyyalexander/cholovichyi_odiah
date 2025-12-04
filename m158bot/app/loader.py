from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import settings

# Создаем асинхронный "движок" для SQLAlchemy на основе строки подключения из конфига
engine = create_async_engine(
    settings.db.build_connection_str(),
    echo=False,  # echo=True будет логировать все SQL-запросы. Полезно для отладки.
)

# Создаем фабрику сессий, которая будет создавать новые сессии для каждого запроса
db_session_factory = async_sessionmaker(
    bind=engine,
    expire_on_commit=False  # Важно для асинхронного кода
)

# Инициализация бота и диспетчера
storage = MemoryStorage()
bot = Bot(token=settings.bot.token, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher(storage=storage)
