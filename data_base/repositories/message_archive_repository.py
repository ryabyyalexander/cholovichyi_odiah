from typing import List

from .base_repository import BaseRepository


class MessageArchiveRepository(BaseRepository):
    """Репозиторий для управления архивом сообщений."""

    def add_message_to_archive(self, name: str, content: str) -> int:
        """Добавляет сообщение в архив и возвращает его ID."""
        cursor = self._execute_query(
            "INSERT INTO message_archive (name, content) VALUES (?, ?)",
            (name, content)
        )
        return cursor.lastrowid

    def add_archive_recipients(self, archive_id: int, user_ids: List[int]) -> None:
        """Добавляет получателей для заархивированного сообщения."""
        params = [(archive_id, user_id) for user_id in user_ids]
        self._execute_query_many(
            "INSERT INTO archived_message_recipients (archive_id, user_id) VALUES (?, ?)",
            params
        )
