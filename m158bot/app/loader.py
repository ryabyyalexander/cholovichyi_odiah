from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis
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

# Инициализация хранилища Redis для FSM
redis_client = Redis(host=settings.redis.host, port=settings.redis.port)
storage = RedisStorage(redis=redis_client)

# Инициализация бота и диспетчера
bot = Bot(token=settings.bot.token, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher(storage=storage)
