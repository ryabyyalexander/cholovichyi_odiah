#import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio

from middlewares.message_manager_middlewares import MessageManagerMiddleware
from middlewares.anti_spam_middleware import AntiSpamMiddleware
from middlewares.critical_operation_middleware import CriticalOperationMiddleware
from middlewares.activity_tracker_middleware import ActivityTrackerMiddleware
from utils import admin
from utils.config import Config, load_config#, admin

storage = MemoryStorage()

config: Config = load_config()
bot = Bot(token=config.tg_bot.token, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher(storage=storage)


dp.message.middleware(MessageManagerMiddleware(bot))
dp.callback_query.middleware(MessageManagerMiddleware(bot))
dp.callback_query.middleware(AntiSpamMiddleware(cooldown=0.3))
dp.callback_query.middleware(CriticalOperationMiddleware())

# Middleware для отслеживания активности
from data_base.models import data_base
dp.message.middleware(ActivityTrackerMiddleware(data_base))
dp.callback_query.middleware(ActivityTrackerMiddleware(data_base))

keep_alive_task = None

async def keep_alive():
    global bot
    while True:
        try:
            await bot.get_me()
        except Exception as e:
            print(f"Keep-alive error: {e}")
        await asyncio.sleep(60)

async def on_startup():
    global keep_alive_task
    print('bot online')
    keep_alive_task = asyncio.create_task(keep_alive())
    msg = await bot.send_message(admin, 'bot online')
    await asyncio.sleep(2)
    await msg.delete()


async def on_shutdown():
    global keep_alive_task
    print('bot closed')
    if isinstance(keep_alive_task, asyncio.Task) and not keep_alive_task.done():
        keep_alive_task.cancel()
    await storage.close()
    msg = await bot.send_message(admin, 'bot closed')
    await asyncio.sleep(2)
    await msg.delete()
