from typing import List

from .base_repository import BaseRepository


class FavoriteRepository(BaseRepository):
    """Репозиторий для управления избранными товарами."""

    def add_to_favorites(self, user_id: int, product_id: int) -> None:
        """Добавляет товар в избранное."""
        self._execute_query(
            "INSERT OR IGNORE INTO favorites (user_id, product_id) VALUES (?, ?)",
            (user_id, product_id)
        )

    def remove_from_favorites(self, user_id: int, product_id: int) -> None:
        """Удаляет товар из избранного."""
        self._execute_query(
            "DELETE FROM favorites WHERE user_id = ? AND product_id = ?",
            (user_id, product_id)
        )

    def get_favorites(self, user_id: int) -> List[int]:
        """Получает список ID избранных товаров пользователя."""
        cursor = self._execute_query(
            "SELECT product_id FROM favorites WHERE user_id = ?",
            (user_id,)
        )
        return [row[0] for row in cursor.fetchall()]

    def is_product_in_favorites(self, user_id: int, product_id: int) -> bool:
        """Проверяет, находится ли товар в избранном у пользователя."""
        cursor = self._execute_query(
            "SELECT 1 FROM favorites WHERE user_id = ? AND product_id = ?",
            (user_id, product_id)
        )
        return cursor.fetchone() is not None
