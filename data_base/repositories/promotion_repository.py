from typing import List, Dict, Any, Optional

from .base_repository import BaseRepository


class PromotionRepository(BaseRepository):
    """Репозиторий для управления акциями."""

    def get_all_promotions(self) -> List[Dict[str, Any]]:
        """Возвращает список всех акций."""
        cursor = self._execute_query("SELECT * FROM promotions ORDER BY start_date DESC")
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def activate_promotion(self, promotion_id: int) -> None:
        """Активирует акцию по ID."""
        self._execute_query("UPDATE promotions SET is_active = 1 WHERE id = ?", (promotion_id,))

    def deactivate_promotion(self, promotion_id: int) -> None:
        """Деактивирует акцию по ID."""
        self._execute_query("UPDATE promotions SET is_active = 0 WHERE id = ?", (promotion_id,))

    def get_active_promotion(self) -> Optional[Dict[str, Any]]:
        """Возвращает активную акцию."""
        cursor = self._execute_query("SELECT * FROM promotions WHERE is_active = 1 LIMIT 1")
        data = cursor.fetchone()
        if not data:
            return None
        columns = [column[0] for column in cursor.description]
        return dict(zip(columns, data))
