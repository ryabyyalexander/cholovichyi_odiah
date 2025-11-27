import json
from typing import Optional, List, Tuple, Any, Dict

from .base_repository import BaseRepository


class UserRepository(BaseRepository):
    """Репозиторий для управления пользователями."""

    def sql_new_user(self, user_id: int, first_name: str, last_name: Optional[str],
                     user_name: Optional[str], is_admin: bool) -> bool:
        """
        Регистрирует нового пользователя.

        Returns:
            True если пользователь был добавлен, False если уже существует
        """
        if not self.sql_user_exists(user_id):
            self._execute_query('''
                INSERT INTO users (user_id, first_name, last_name, user_name, is_admin, level)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, first_name, last_name, user_name, is_admin, None))
            return True
        return False

    def sql_get_user(self, user_id: int, *fields: str) -> Optional[Tuple]:
        """Получает данные пользователя по ID"""
        fields_to_select = ', '.join(fields) if fields else '*'
        cursor = self._execute_query(
            f"SELECT {fields_to_select} FROM users WHERE user_id = ?",
            (user_id,)
        )
        return cursor.fetchone()

    def sql_user_exists(self, user_id: int) -> bool:
        """Проверяет существование пользователя"""
        cursor = self._execute_query(
            "SELECT 1 FROM users WHERE user_id = ?",
            (user_id,)
        )
        return cursor.fetchone() is not None

    def increment_restart_count(self, user_id: int) -> None:
        """Инкрементирует счетчик перезапусков"""
        self._execute_query(
            "UPDATE users SET restart_count = restart_count + 1 WHERE user_id = ?",
            (user_id,)
        )

    def increment_activity_count(self, user_id: int, weight: float = 1) -> None:
        """Инкрементирует счетчик активности."""
        self._execute_query(
            "UPDATE users SET restart_count = restart_count + ? WHERE user_id = ?",
            (round(weight), user_id)
        )

    def update_user_blocked(self, user_id: int, status: bool) -> None:
        """Обновляет статус блокировки пользователя"""
        self._execute_query(
            "UPDATE users SET user_blocked = ? WHERE user_id = ?",
            (status, user_id)
        )

    def get_restart_count(self, user_id: int) -> int:
        """Возвращает количество перезапусков бота пользователем"""
        cursor = self._execute_query(
            "SELECT restart_count FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        return result[0] if result else 0

    def activate_user(self, user_id: int) -> None:
        """Активирует пользователя (дает доступ к боту)"""
        self._execute_query(
            "UPDATE users SET is_active = 1 WHERE user_id = ?",
            (user_id,)
        )

    def set_user_level(self, user_id: int, level: str) -> None:
        """Устанавливает уровень лояльности для пользователя."""
        self._execute_query(
            "UPDATE users SET level = ? WHERE user_id = ?",
            (level, user_id)
        )

    def get_pending_users(self) -> List[Tuple[int, str, str]]:
        """Возвращает список пользователей, ожидающих активации"""
        cursor = self._execute_query(
            "SELECT user_id, first_name, user_name FROM users WHERE is_active = 0"
        )
        return cursor.fetchall()

    def is_user_active(self, user_id: int) -> bool:
        """Проверяет, активирован ли пользователь"""
        cursor = self._execute_query(
            "SELECT is_active FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        return bool(result[0]) if result else False

    def get_list_admins(self) -> List[int]:
        """Возвращает список ID администраторов"""
        cursor = self._execute_query("SELECT user_id FROM users WHERE is_admin = 1")
        return [row[0] for row in cursor.fetchall()]

    def get_unblocked_users(self) -> List[int]:
        """Возвращает список ID всех пользователей, которые не заблокировали бота."""
        cursor = self._execute_query(
            "SELECT user_id FROM users WHERE user_blocked != 1"
        )
        return [row[0] for row in cursor.fetchall()]

    def get_users_by_level(self, level: str) -> List[int]:
        """Возвращает список ID пользователей по уровню лояльности."""
        cursor = self._execute_query(
            "SELECT user_id FROM users WHERE level = ? AND user_blocked != 1",
            (level,)
        )
        return [row[0] for row in cursor.fetchall()]

    def get_phone(self, user_id: int) -> Optional[str]:
        """Возвращает номер телефона пользователя"""
        cursor = self._execute_query(
            "SELECT phone FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        return result[0] if result else None

    def get_active_msg_id(self, user_id: int) -> Optional[int]:
        """Возвращает ID активного сообщения из словаря"""
        cursor = self._execute_query(
            "SELECT active_msg_id FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        if result and result[0]:
            try:
                msg_ids = json.loads(result[0])
                return msg_ids.get('active')
            except (json.JSONDecodeError, KeyError):
                return None
        return None

    def get_register_msg_id(self, user_id: int) -> Optional[int]:
        """Возвращает ID сообщения о регистрации из словаря"""
        cursor = self._execute_query(
            "SELECT active_msg_id FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        if result and result[0]:
            try:
                msg_ids = json.loads(result[0])
                return msg_ids.get('register')
            except (json.JSONDecodeError, KeyError):
                return None
        return None

    def set_active_msg_id(self, user_id: int, message_id: Optional[int]) -> None:
        """Сохраняет ID активного сообщения в словарь"""
        cursor = self._execute_query(
            "SELECT active_msg_id FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        
        msg_ids = {}
        if result and result[0]:
            try:
                msg_ids = json.loads(result[0])
            except json.JSONDecodeError:
                msg_ids = {}
        
        if message_id:
            msg_ids['active'] = message_id
        elif 'active' in msg_ids:
            del msg_ids['active']
        
        msg_ids_json = json.dumps(msg_ids) if msg_ids else None
        self._execute_query(
            "UPDATE users SET active_msg_id = ? WHERE user_id = ?",
            (msg_ids_json, user_id)
        )

    def set_register_msg_id(self, user_id: int, message_id: Optional[int]) -> None:
        """Сохраняет ID сообщения о регистрации в словарь"""
        cursor = self._execute_query(
            "SELECT active_msg_id FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        
        msg_ids = {}
        if result and result[0]:
            try:
                msg_ids = json.loads(result[0])
            except json.JSONDecodeError:
                msg_ids = {}
        
        if message_id:
            msg_ids['register'] = message_id
        elif 'register' in msg_ids:
            del msg_ids['register']
        
        msg_ids_json = json.dumps(msg_ids) if msg_ids else None
        self._execute_query(
            "UPDATE users SET active_msg_id = ? WHERE user_id = ?",
            (msg_ids_json, user_id)
        )

    def clear_register_msg_id(self, user_id: int) -> None:
        """Очищает ID сообщения о регистрации из словаря"""
        self.set_register_msg_id(user_id, None)

    def get_and_clear_register_msg_id(self, user_id: int) -> Optional[int]:
        """Получает и очищает ID сообщения о регистрации."""
        msg_id = self.get_register_msg_id(user_id)
        if msg_id:
            self.clear_register_msg_id(user_id)
        return msg_id

    def set_user_filters(self, user_id: int, filters: dict) -> None:
        """Сохраняет фильтры пользователя в базу данных (как JSON)."""
        filters_json = json.dumps(filters, ensure_ascii=False)
        self._execute_query(
            "UPDATE users SET filters = ? WHERE user_id = ?",
            (filters_json, user_id)
        )

    def get_user_filters(self, user_id: int) -> dict:
        """Возвращает фильтры пользователя из базы данных (как dict)."""
        cursor = self._execute_query(
            "SELECT filters FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        if result and result[0]:
            try:
                return json.loads(result[0])
            except Exception:
                return {}
        return {}

    def set_slider_speed(self, user_id: int, speed: int) -> None:
        """Сохраняет скорость слайдера в поле slider_speed"""
        self._execute_query(
            "UPDATE users SET slider_speed = ? WHERE user_id = ?",
            (str(speed), user_id)
        )

    def get_slider_speed(self, user_id: int) -> int:
        """Получает скорость слайдера из slider_speed (если есть), иначе возвращает None"""
        cursor = self._execute_query(
            "SELECT slider_speed FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        if result and result[0]:
            try:
                return int(result[0])
            except ValueError:
                return None
        return None

    def register_user_with_referrer(self, user_id: int, first_name: str, last_name: Optional[str],
                                    user_name: Optional[str], is_admin: bool, referrer_id: Optional[int] = None) -> bool:
        """
        Регистрирует нового пользователя с возможностью указать реферера.
        """
        if not self.sql_user_exists(user_id):
            self._execute_query('''
                INSERT INTO users (user_id, first_name, last_name, user_name, is_admin, referrer_id, level)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, first_name, last_name, user_name, is_admin, referrer_id, None))
            return True
        return False

    def get_referrals(self, referrer_id: int) -> list:
        """
        Возвращает список пользователей, которых пригласил данный пользователь.
        """
        cursor = self._execute_query(
            "SELECT user_id, first_name, last_name, user_name FROM users WHERE referrer_id = ?",
            (referrer_id,)
        )
        return cursor.fetchall()

    def has_referrer(self, user_id: int) -> bool:
        """
        Проверяет, установлен ли referrer_id у пользователя.
        """
        cursor = self._execute_query(
            "SELECT referrer_id FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        return result is not None and result[0] is not None

    def set_phone(self, user_id: int, phone: str) -> None:
        """Устанавливает номер телефона для пользователя."""
        self._execute_query(
            "UPDATE users SET phone = ? WHERE user_id = ?",
            (phone, user_id)
        )

    def clear_waiting_list_and_get_users(self, product_id: int, size_id: int) -> List[int]:
        """Очищает лист ожидания для конкретного товара и размера и возвращает ID пользователей."""
        cursor = self._execute_query(
            "SELECT user_id FROM waiting_list WHERE product_id = ? AND size_id = ?",
            (product_id, size_id)
        )
        user_ids = [row[0] for row in cursor.fetchall()]
        if user_ids:
            self._execute_query(
                "DELETE FROM waiting_list WHERE product_id = ? AND size_id = ?",
                (product_id, size_id)
            )
        return user_ids

    def get_user_referrals_count(self, user_id: int) -> int:
        cursor = self._execute_query("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,))
        return cursor.fetchone()[0]

    def get_user_total_spent(self, user_id: int) -> float:
        cursor = self._execute_query("SELECT total_spent FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 0.0

    def get_user_level(self, user_id: int) -> Optional[str]:
        cursor = self._execute_query("SELECT level FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else None

    def update_user_size(self, user_id: int, size_data: str) -> None:
        self._execute_query("UPDATE users SET size = ? WHERE user_id = ?", (size_data, user_id))

    def get_waiting_list(self, user_id: int) -> List[Dict[str, Any]]:
        cursor = self._execute_query(
            """SELECT wl.id, p.name, s.value as size FROM waiting_list wl
               JOIN products p ON wl.product_id = p.id
               JOIN sizes s ON wl.size_id = s.id
               WHERE wl.user_id = ? AND wl.status = 'active'""",
            (user_id,)
        )
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def remove_from_waiting_list(self, waiting_list_id: int) -> None:
        self._execute_query("DELETE FROM waiting_list WHERE id = ?", (waiting_list_id,))
