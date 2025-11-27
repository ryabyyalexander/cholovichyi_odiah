import asyncio
import sqlite3
import logging
import os
from aiogram import Bot
from aiogram.types import BufferedInputFile
from aiogram.exceptions import TelegramBadRequest
import io

# =====================================================================================
# НАСТРОЙКИ МИГРАЦИИ - ЗАПОЛНИТЕ ЭТИ ПОЛЯ
# =====================================================================================

# Вставьте сюда токен СТАРОГО бота, с которого нужно перенести файлы
OLD_BOT_TOKEN = "6376524115:AAHWu2n6FNGET-aaCDYcyRobRwkLGygFfiw"

# Вставьте сюда токен НОВОГО бота, на который нужно перенести файлы
NEW_BOT_TOKEN = "7103067751:AAGtZDwOp8UrdvwpVjRsI9zofwx4o2UGo78"

# Вставьте сюда ваш Telegram ID (число). Бот будет отправлять файлы вам в личные сообщения,
# чтобы получить новые file_id. Узнать свой ID можно у бота @userinfobot
ADMIN_CHAT_ID = 379349263  # Замените на ваш реальный ID

# =====================================================================================
# КОНФИГУРАЦИЯ СКРИПТА (обычно менять не нужно)
# =====================================================================================

DB_NAME = "bot.db"
LOG_FILE = "migration.log"
# Задержка между отправкой файлов, чтобы не попасть под лимиты Telegram
SLEEP_DELAY = 1.5  # Немного увеличено из-за более тяжелых операций

# =====================================================================================
# ЛОГИКА СКРИПТА (ИСПРАВЛЕННАЯ ВЕРСИЯ)
# =====================================================================================

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, mode='w'), # Перезаписывать лог при каждом запуске
        logging.StreamHandler()
    ]
)

async def migrate_media():
    """
    Основная функция для выполнения миграции медиафайлов
    с использованием логики "скачать-загрузить".
    """
    if OLD_BOT_TOKEN == "YOUR_OLD_BOT_TOKEN_HERE" or \
       NEW_BOT_TOKEN == "YOUR_NEW_BOT_TOKEN_HERE" or \
       ADMIN_CHAT_ID == 000000000:
        logging.error("Пожалуйста, заполните OLD_BOT_TOKEN, NEW_BOT_TOKEN и ADMIN_CHAT_ID в скрипте.")
        return

    if not os.path.exists(DB_NAME):
        logging.error(f"Файл базы данных '{DB_NAME}' не найден. Убедитесь, что скрипт находится в той же папке.")
        return

    logging.info("Начало миграции медиафайлов (v2: скачать-загрузить).")
    logging.info(f"База данных: {DB_NAME}")
    logging.info(f"Целевой чат для пересылки: {ADMIN_CHAT_ID}")

    old_bot = Bot(token=OLD_BOT_TOKEN)
    new_bot = Bot(token=NEW_BOT_TOKEN)
    
    conn = None
    updated_count = 0
    error_count = 0

    try:
        # Проверка доступности ботов и ADMIN_CHAT_ID
        try:
            await old_bot.get_me()
            logging.info("Старый бот успешно подключился.")
            await new_bot.send_chat_action(ADMIN_CHAT_ID, 'typing')
            logging.info("Новый бот успешно подключился и имеет доступ к чату администратора.")
        except Exception as e:
            logging.error(f"Ошибка при инициализации ботов: {e}")
            logging.error("Проверьте правильность токенов и ADMIN_CHAT_ID. Также убедитесь, что вы начали диалог с обоими ботами.")
            return

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute("SELECT id, telegram_file_id, media_type FROM product_media")
        media_records = cursor.fetchall()
        total_records = len(media_records)
        logging.info(f"Найдено {total_records} записей в таблице product_media для обработки.")

        for index, (record_id, old_file_id, media_type) in enumerate(media_records):
            logging.info(f"[{index + 1}/{total_records}] Обработка записи ID: {record_id}...")
            
            if not old_file_id:
                logging.warning(f"-> Пропущена запись ID: {record_id}, так как telegram_file_id пуст.")
                continue

            new_file_id = None
            try:
                # 1. Получаем информацию о файле от старого бота
                file_info = await old_bot.get_file(old_file_id)
                
                # 2. Скачиваем файл в память
                file_bytes_io = await old_bot.download_file(file_info.file_path)
                
                # 3. Готовим файл для загрузки
                input_file = BufferedInputFile(file_bytes_io.read(), filename=f"migration_{record_id}")

                # 4. Загружаем файл через нового бота
                message = None
                if media_type == 'photo':
                    message = await new_bot.send_photo(chat_id=ADMIN_CHAT_ID, photo=input_file)
                    if message.photo:
                        new_file_id = message.photo[-1].file_id
                elif media_type == 'video':
                    message = await new_bot.send_video(chat_id=ADMIN_CHAT_ID, video=input_file)
                    if message.video:
                        new_file_id = message.video.file_id
                elif media_type == 'document':
                    message = await new_bot.send_document(chat_id=ADMIN_CHAT_ID, document=input_file)
                    if message.document:
                        new_file_id = message.document.file_id
                else:
                    logging.warning(f"-> Неизвестный тип медиа '{media_type}' для записи ID: {record_id}. Пропускаем.")
                    error_count += 1
                    continue

                # 5. Обновляем базу данных
                if new_file_id:
                    cursor.execute("UPDATE product_media SET telegram_file_id = ? WHERE id = ?", (new_file_id, record_id))
                    logging.info(f"-> Успешно обновлено. Новый file_id: {new_file_id}")
                    updated_count += 1
                else:
                    logging.error(f"-> Ошибка: не удалось получить новый file_id после загрузки для записи ID: {record_id}.")
                    error_count += 1

            except TelegramBadRequest as e:
                if "file is too big" in str(e) or "FILE_REFERENCE_EXPIRED" in str(e) or "wrong file identifier" in str(e):
                    logging.error(f"-> Ошибка Telegram для записи ID {record_id} (file_id: {old_file_id}): {e}. Возможно, файл устарел или недоступен на серверах Telegram. Пропускаем.")
                    error_count += 1
                else:
                    logging.error(f"-> Непредвиденная ошибка Telegram для записи ID {record_id}: {e}")
                    error_count += 1
            except Exception as e:
                logging.error(f"-> Критическая ошибка при обработке записи ID {record_id}: {e}")
                error_count += 1
            
            await asyncio.sleep(SLEEP_DELAY)

        conn.commit()
        logging.info("Все записи обработаны. Изменения сохранены в базе данных.")

    except sqlite3.Error as e:
        logging.error(f"Ошибка при работе с базой данных: {e}")
        if conn:
            conn.rollback()
    except Exception as e:
        logging.error(f"Произошла общая ошибка: {e}")
    finally:
        if conn:
            conn.close()
            logging.info("Соединение с базой данных закрыто.")
        if old_bot:
            await old_bot.session.close()
            logging.info("Сессия старого бота закрыта.")
        if new_bot:
            await new_bot.session.close()
            logging.info("Сессия нового бота закрыта.")

    logging.info("="*30)
    logging.info("Миграция завершена.")
    logging.info(f"Всего обработано записей: {updated_count + error_count}")
    logging.info(f"Успешно обновлено: {updated_count}")
    logging.info(f"Ошибок / пропущено: {error_count}")
    logging.info(f"Подробный отчет находится в файле {LOG_FILE}")
    logging.info("="*30)


if __name__ == "__main__":
    asyncio.run(migrate_media())