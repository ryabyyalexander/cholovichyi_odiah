from typing import List, Dict, Any, Optional
import json

from .base_repository import BaseRepository


class SubscriptionRepository(BaseRepository):
    """Репозиторий для управления подписками."""

    def get_subscription_topics(self) -> List[Dict[str, Any]]:
        cursor = self._execute_query("SELECT * FROM subscriptions")
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_subscribers(self, topic_key: str) -> List[Dict[str, Any]]:
        cursor = self._execute_query(
            """SELECT u.user_id, us.filters FROM user_subscriptions us
               JOIN users u ON us.user_id = u.user_id
               JOIN subscriptions s ON us.subscription_id = s.id
               WHERE s.topic_key = ? AND u.user_blocked != 1""",
            (topic_key,)
        )
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_subscribers_for_brand(self, brand: str) -> List[int]:
        cursor = self._execute_query(
            """SELECT us.user_id FROM user_subscriptions us
               JOIN subscriptions s ON us.subscription_id = s.id
               WHERE s.topic_key = 'brand_news' AND json_extract(us.filters, '$.brand') = ?""",
            (brand,)
        )
        return [row[0] for row in cursor.fetchall()]

    def get_user_subscriptions(self, user_id: int) -> List[Dict[str, Any]]:
        cursor = self._execute_query(
            """SELECT s.topic_key, us.filters FROM user_subscriptions us
               JOIN subscriptions s ON us.subscription_id = s.id
               WHERE us.user_id = ?""",
            (user_id,)
        )
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def add_user_subscription(self, user_id: int, topic_key: str, filters: Optional[Dict[str, Any]] = None) -> None:
        cursor = self._execute_query("SELECT id FROM subscriptions WHERE topic_key = ?", (topic_key,))
        topic_id = cursor.fetchone()[0]
        filters_json = json.dumps(filters) if filters else None
        self._execute_query(
            "INSERT OR REPLACE INTO user_subscriptions (user_id, subscription_id, filters) VALUES (?, ?, ?)",
            (user_id, topic_id, filters_json)
        )

    def remove_user_subscription(self, user_id: int, topic_key: str) -> None:
        cursor = self._execute_query("SELECT id FROM subscriptions WHERE topic_key = ?", (topic_key,))
        topic_id = cursor.fetchone()[0]
        self._execute_query(
            "DELETE FROM user_subscriptions WHERE user_id = ? AND subscription_id = ?",
            (user_id, topic_id)
        )
