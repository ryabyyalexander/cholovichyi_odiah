import sqlite3
import os
import asyncio
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

BOT_TOKEN = "6376524115:AAHWu2n6FNGET-aaCDYcyRobRwkLGygFfiw"
DB_PATH = "../bot_original.db"
OUTPUT_DIR = "../media/telegram"

async def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_file_id FROM product_media")
    file_ids = [row[0] for row in cursor.fetchall()]
    conn.close()

    bot = Bot(token=BOT_TOKEN)

    success_count = 0
    error_count = 0

    for file_id in file_ids:
        try:
            file_info = await bot.get_file(file_id)
            file_path = file_info.file_path
            file_extension = os.path.splitext(file_path)[1]
            # Используем telegram_file_id как имя файла, заменяя невалидные символы
            safe_file_id = file_id.replace('/', '_').replace('\\', '_')
            file_name = f"{safe_file_id}{file_extension}"
            destination_path = os.path.join(OUTPUT_DIR, file_name)
            await bot.download_file(file_path, destination_path)
            print(f"Downloaded {file_name} (file_id: {file_id})")
            success_count += 1
        except TelegramBadRequest as e:
            print(f"Error downloading file_id {file_id}: {e}")
            error_count += 1
        except Exception as e:
            print(f"An unexpected error occurred for file_id {file_id}: {e}")
            error_count += 1
    
    await bot.session.close()

    print(f"\nDownload complete.")
    print(f"Successfully downloaded: {success_count} files.")
    print(f"Errors: {error_count} files.")

if __name__ == "__main__":
    asyncio.run(main())