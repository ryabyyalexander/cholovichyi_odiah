import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(filename)s:%(lineno)d #%(levelname)-8s '
           '[%(asctime)s] - %(name)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),  # Запись логов в файл
        # logging.StreamHandler()  # Вывод логов в консоль
    ]
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)