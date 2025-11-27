from .base_repository import BaseRepository
from typing import List, Dict, Any

class ProductViewRepository(BaseRepository):
    """Репозиторий для управления просмотрами товаров."""

    def add_product_view(self, user_id: int, product_id: int, view_type: str, view_duration: int) -> None:
        """Добавляет запись о просмотре товара."""
        self._execute_query(
            "INSERT INTO product_views (user_id, product_id, view_type, view_duration) VALUES (?, ?, ?, ?)",
            (user_id, product_id, view_type, view_duration)
        )

    def get_user_product_views(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        query = "SELECT * FROM product_views WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?"
        cursor = self._execute_query(query, (user_id, limit))
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_user_unique_product_views(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        query = """
            SELECT * FROM (
                SELECT *, ROW_NUMBER() OVER(PARTITION BY product_id ORDER BY timestamp DESC) as rn
                FROM product_views
                WHERE user_id = ?
            ) WHERE rn = 1 ORDER BY timestamp DESC LIMIT ?
        """
        cursor = self._execute_query(query, (user_id, limit))
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_product_view_stats(self, product_id: int) -> Dict[str, Any]:
        query = """
            SELECT 
                COUNT(*) as total_views,
                COUNT(DISTINCT user_id) as unique_users,
                AVG(view_duration) as avg_duration
            FROM product_views 
            WHERE product_id = ?
        """
        cursor = self._execute_query(query, (product_id,))
        stats = cursor.fetchone()
        return {'total_views': stats[0], 'unique_users': stats[1], 'avg_duration': stats[2]} if stats else {}

    def get_user_view_stats(self, user_id: int) -> Dict[str, Any]:
        query = """
            SELECT 
                COUNT(*) as total_views,
                COUNT(DISTINCT product_id) as unique_products,
                SUM(view_duration) as total_duration
            FROM product_views 
            WHERE user_id = ?
        """
        cursor = self._execute_query(query, (user_id,))
        stats = cursor.fetchone()
        return {'total_views': stats[0], 'unique_products': stats[1], 'total_duration': stats[2]} if stats else {}

    def get_most_viewed_products(self, limit: int = 10) -> List[Dict[str, Any]]:
        query = """
            SELECT product_id, COUNT(*) as view_count
            FROM product_views
            GROUP BY product_id
            ORDER BY view_count DESC
            LIMIT ?
        """
        cursor = self._execute_query(query, (limit,))
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_recent_views(self, hours: int = 24) -> List[Dict[str, Any]]:
        query = "SELECT * FROM product_views WHERE timestamp >= datetime('now', ?)"
        params = (f'-{hours} hours',)
        cursor = self._execute_query(query, params)
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def delete_old_views(self, days: int = 90) -> int:
        query = "DELETE FROM product_views WHERE timestamp < datetime('now', ?)"
        params = (f'-{days} days',)
        cursor = self._execute_query(query, params)
        return cursor.rowcount
