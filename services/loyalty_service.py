from data_base.models import BotDatabase, LoyaltyHistory
from enums.profile_enum import LoyaltyLevelEnum, LoyaltyEventEnum
from datetime import datetime
from typing import Optional
from aiogram.types import CallbackQuery
from keyboards.kb import order_points_keyboard
from utils.lexicon import LOYALTY_LEXICON

# --- Константы для настройки системы лояльности ---
POINTS_PERCENT = 1  # 1 балл за 1 евро
MAX_DISCOUNT_PERCENT = 0.3  # Максимум 30% стоимости можно оплатить баллами
REFERRAL_BONUS = 100  # Бонус за реферала

# Уровни лояльности и необходимое количество баллов
LEVELS = [
    (LoyaltyLevelEnum.BRONZE, 0),      # Начальный уровень
    (LoyaltyLevelEnum.SILVER, 1000),   # от 1000 баллов
    (LoyaltyLevelEnum.GOLD, 5000),     # от 5000 баллов
    (LoyaltyLevelEnum.DIAMOND, 10000), # от 10000 баллов
]

class LoyaltyService:
    def __init__(self, db: BotDatabase):
        self.db = db

    def add_points_for_purchase(self, user_id: int, amount: int):
        """
        Начисляет баллы за покупку и логирует операцию.
        """
        points = int(amount * POINTS_PERCENT)
        self.db.execute_query(
            "UPDATE users SET loyalty_points = loyalty_points + ?, total_spent = total_spent + ? WHERE user_id = ?",
            (points, amount, user_id)
        )
        self.log_event(user_id, LoyaltyEventEnum.PURCHASE, points)
        self.update_user_level(user_id)
        return points

    def add_bonus_points(self, user_id: int, points: int, event: LoyaltyEventEnum = LoyaltyEventEnum.PURCHASE):
        """
        Начисляет бонусные баллы, логирует операцию как указанное событие,
        но не увеличивает total_spent.
        """
        self.db.execute_query(
            "UPDATE users SET loyalty_points = loyalty_points + ? WHERE user_id = ?",
            (points, user_id)
        )
        self.log_event(user_id, event, points)
        self.update_user_level(user_id)
        return points

    def log_pseudo_purchase_only(self, user_id: int, points: int):
        """
        ТОЛЬКО логирует псевдо-покупку в историю, не изменяя баллы и уровень пользователя.
        """
        self.log_event(user_id, LoyaltyEventEnum.PURCHASE, points)

    

    def add_referral_bonus(self, referrer_id: int, friend_id: int):
        """
        Начисляет бонус за реферала (после первого заказа друга).
        """
        self.db.execute_query(
            "UPDATE users SET loyalty_points = loyalty_points + ? WHERE user_id = ?",
            (REFERRAL_BONUS, referrer_id)
        )
        self.log_event(referrer_id, LoyaltyEventEnum.REFERRAL, REFERRAL_BONUS)
        # Можно добавить связь с другом в истории, если нужно

    def get_referral_points(self, user_id: int) -> int:
        """
        Возвращает количество реферальных баллов пользователя из истории лояльности.
        """
        cur = self.db.execute_query(
            "SELECT SUM(points) FROM loyalty_history WHERE user_id = ? AND event = ?",
            (user_id, LoyaltyEventEnum.REFERRAL.value)
        )
        result = cur.fetchone()
        return int(result[0]) if result and result[0] is not None else 0

    def get_purchase_points(self, user_id: int) -> int:
        """
        Возвращает количество баллов за покупки пользователя из истории лояльности.
        """
        cur = self.db.execute_query(
            "SELECT SUM(points) FROM loyalty_history WHERE user_id = ? AND event = ?",
            (user_id, LoyaltyEventEnum.PURCHASE.value)
        )
        result = cur.fetchone()
        return int(result[0]) if result and result[0] is not None else 0

    def get_total_points_from_history(self, user_id: int) -> int:
        """
        Возвращает сумму всех начисленных баллов пользователя по истории лояльности.
        """
        cur = self.db.execute_query(
            "SELECT SUM(points) FROM loyalty_history WHERE user_id = ?",
            (user_id,)
        )
        result = cur.fetchone()
        return int(result[0]) if result and result[0] is not None else 0

    def update_user_level(self, user_id: int, progress_points: Optional[float] = None) -> Optional[str]:
        """
        Проверяет и обновляет уровень пользователя на основе суммы баллов (loyalty_points + бонус активности + реферальные баллы, если progress_points передан).
        Возвращает текст уведомления при повышении уровня.
        """
        user = self.db.sql_get_user(user_id, 'level', 'loyalty_points', 'restart_count', 'phone')
        if not user:
            return None
        current_level = user[0]
        points = user[1]
        activity = user[2]
        phone = user[3]

        if not phone:
            return None # Не обновляем уровень, если нет номера телефона

        if progress_points is None:
            # Добавляем реферальные баллы к расчету
            referral_points = self.get_referral_points(user_id)
            progress_points = points + (activity / 5) + referral_points
        new_level = LoyaltyLevelEnum.BRONZE
        for level, threshold in reversed(LEVELS):
            if progress_points >= threshold:
                new_level = level
                break
        if new_level.value != current_level:
            self.db.execute_query(
                "UPDATE users SET level = ? WHERE user_id = ?",
                (new_level.value, user_id)
            )
            return LOYALTY_LEXICON['level_up_notification'].format(level=new_level.value.capitalize())
        else:
            self.db.execute_query(
                "UPDATE users SET level = ? WHERE user_id = ?",
                (new_level.value, user_id)
            )
            return None

    def log_event(self, user_id: int, event: LoyaltyEventEnum, points: int):
        """
        Записывает событие в таблицу истории лояльности.
        """
        self.db.execute_query(
            "INSERT INTO loyalty_history (user_id, event, points, created_at) VALUES (?, ?, ?, ?)",
            (user_id, event.value, points, datetime.now())
        )

    def get_points_balance(self, user_id: int) -> int:
        user = self.db.sql_get_user(user_id, 'loyalty_points')
        return user[0] if user else 0

    def get_user_level(self, user_id: int) -> str:
        user = self.db.sql_get_user(user_id, 'level', 'phone')
        if user and user[1]:  # Проверяем наличие номера телефона
            return user[0] if user[0] else "Користувач"
        return "Користувач"

    def get_loyalty_history(self, user_id: int, limit: int = 20):
        cur = self.db.execute_query(
            "SELECT event, points, created_at FROM loyalty_history WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        )
        return cur.fetchall()

    def get_next_level_progress(self, user_id: int, progress_points: Optional[float] = None) -> tuple[int, str]:
        """
        Возвращает количество баллов до следующего уровня и название следующего уровня.
        Использует сумму (loyalty_points + бонус активности + реферальные баллы), если progress_points передан.
        """
        user = self.db.sql_get_user(user_id, 'level', 'loyalty_points', 'restart_count')
        if not user:
            return 0, "Максимальний"
        current_level = user[0]
        points = user[1]
        activity = user[2]
        if progress_points is None:
            # Добавляем реферальные баллы к расчету
            referral_points = self.get_referral_points(user_id)
            progress_points = points + (activity / 5) + referral_points
        for i, (level, threshold) in enumerate(LEVELS):
            if level.value == current_level:
                if i < len(LEVELS) - 1:
                    next_level, next_threshold = LEVELS[i + 1]
                else:
                    return 0, "Максимальний"
                break
        else:
            next_level, next_threshold = LEVELS[1]
        points_needed = next_threshold - progress_points
        return max(int(points_needed), 0), next_level.value.capitalize()

    # --- Задел для промокодов, миссий и сезонных бонусов ---
    def apply_promo(self, user_id: int, promo_code: str):
        pass  # TODO: реализовать

    def apply_seasonal_bonus(self, user_id: int):
        pass  # TODO: реализовать

    def apply_mission_reward(self, user_id: int, mission_id: int):
        pass  # TODO: реализовать

# --- Пример интеграции лояльности в оформление заказа ---
async def process_order_with_loyalty(
    callback: CallbackQuery,
    user_id: int,
    order_amount: int,
    db: BotDatabase,
    manager,
    use_points: bool = False # Параметр оставлен для совместимости, но не используется
):
    """
    Пример функции для оформления заказа с учётом системы лояльности.
    Больше не обрабатывает списание баллов или реферальный бонус за первую покупку.
    Только начисляет баллы за покупку.
    :param callback: CallbackQuery пользователя
    :param user_id: ID пользователя
    :param order_amount: Сумма заказа (в копейках/грн)
    :param db: экземпляр BotDatabase
    :param manager: MessageManager для отправки сообщений
    :param use_points: использовать ли баллы (игнорируется)
    """
    loyalty = LoyaltyService(db)
    
    # Списание баллов и реферальный бонус за первую покупку удалены.
    # Теперь всегда используется полная сумма заказа.
    final_amount = order_amount
    points_earned = loyalty.add_points_for_purchase(user_id, final_amount)
    
    # Вернуть итоговые значения для дальнейшей обработки
    return {
        'final_amount': final_amount,
        'points_used': 0, # Всегда 0
        'points_earned': points_earned
    }

# --- Конец примера интеграции --- 