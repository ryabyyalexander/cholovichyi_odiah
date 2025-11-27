from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram import F
from filters import IsAdmin
from fsm.states import State_add_photo
from utils import admins, bot, safe_delete_message

router = Router()

# Временные хранилища для разных типов медиа (можно заменить на сохранение в БД)
audios: list[str] = []
voices: list[str] = []
documents: list[str] = []
stickers: list[str] = []
animations: list[str] = []


@router.message((F.photo | F.video | F.sticker | F.document | F.voice | F.audio | F.animation),
                IsAdmin, StateFilter(State_add_photo.start))
async def set_media(message: Message, state: FSMContext):
    """
    Обрабатывает все типы медиа-сообщений от администратора в состоянии добавления фото.
    Сохраняет фото и видео в состояние FSM для последующего создания товаров.
    Другие типы медиа сохраняются во временные списки (можно расширить для сохранения в БД).
    """
    data = await state.get_data()
    media_list = data.get('media_list', [])
    content_type = message.content_type
    user_id = message.from_user.id

    # Обработка фото и видео (основные типы для товаров)
    if content_type in ['photo', 'video'] and user_id in admins:
        await message.delete()  # Удаляем исходное сообщение для чистоты чата

        # Получаем file_id в зависимости от типа контента
        file_id = message.photo[-1].file_id if content_type == 'photo' else message.video.file_id
        media_type = 'photo' if content_type == 'photo' else 'video'
        caption = message.caption or ''  # Подпись может быть пустой

        # Формируем структурированные данные медиа
        media_data = {
            'type_media': media_type,
            'path': file_id,
            'caption': caption,
            'content_type': content_type,
            'date': message.date.isoformat()  # Сохраняем дату получения
        }

        # Добавляем медиа в список и обновляем состояние
        media_list.append(media_data)
        await state.update_data(media_list=media_list)

        # Отправляем подтверждение и удаляем его через 2 секунды
        confirmation = await bot.send_message(user_id, f'✅ {media_type.capitalize()} сохранено')
        await safe_delete_message(confirmation, 2)

    # Обработка стикеров (дополнительный функционал)
    elif content_type == 'sticker':
        await message.delete()
        sticker_id = message.sticker.file_id

        # Можно добавить сохранение в БД вместо временного списка
        stickers.append(sticker_id)

        # Отправляем стикер обратно как подтверждение
        confirmation = await bot.send_sticker(
            chat_id=message.from_user.id,
            sticker=sticker_id
        )
        await safe_delete_message(confirmation, 7)

    # Обработка документов (пример расширения функционала)
    elif content_type == 'document':
        await message.delete()
        document_id = message.document.file_id
        documents.append(document_id)

        # Логирование (в реальном проекте лучше использовать logger)
        print(f"Документ сохранен: {document_id}")

    # Обработка голосовых сообщений
    elif content_type == 'voice':
        await message.delete()
        voice_id = message.voice.file_id
        voices.append(voice_id)
        print(f"Голосовое сообщение сохранено: {voice_id}")

    # Обработка аудиофайлов
    elif content_type == 'audio':
        await message.delete()
        audio_id = message.audio.file_id
        audios.append(audio_id)
        print(f"Аудиофайл сохранен: {audio_id}")

    # Обработка анимаций (GIF)
    elif content_type == 'animation':
        await message.delete()
        animation_id = message.animation.file_id
        animations.append(animation_id)
        print(f"Анимация сохранена: {animation_id}")

    # Для всех необработанных типов можно добавить логирование
    else:
        print(f"Получен неподдерживаемый тип контента: {content_type}")