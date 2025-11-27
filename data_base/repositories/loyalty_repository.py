from typing import List
from dataclasses import dataclass
from datetime import datetime


@dataclass
class LoyaltyHistory:
    user_id: int
    event: str
    points: int
    created_at: datetime


from .base_repository import BaseRepository


class LoyaltyRepository(BaseRepository):
    """Репозиторий для управления баллами лояльности."""

    def add_loyalty_points(self, user_id: int, points: int, event: str) -> None:
        """Начисляет баллы лояльности и записывает в историю."""
        self._execute_query(
            "UPDATE users SET loyalty_points = loyalty_points + ? WHERE user_id = ?",
            (points, user_id)
        )
        self._execute_query(
            "INSERT INTO loyalty_history (user_id, event, points) VALUES (?, ?, ?)",
            (user_id, event, points)
        )

    def get_loyalty_history(self, user_id: int) -> List[LoyaltyHistory]:
        """Получает историю начисления баллов лояльности."""
        cursor = self._execute_query(
            "SELECT event, points, created_at FROM loyalty_history WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )
        return [LoyaltyHistory(user_id, row[0], row[1], row[2]) for row in cursor.fetchall()]
