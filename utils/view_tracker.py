# utils/view_tracker.py

import time
from typing import Dict, Optional, List
from data_base.models import data_base
from utils import logger


class ViewTracker:
    """Утилита для отслеживания просмотров товаров пользователями"""
    
    def __init__(self):
        self._view_sessions: Dict[str, Dict] = {}  # {session_key: session_data}
    
    def start_view_session(self, user_id: int, product_id: int, view_type: str = 'slider') -> str:
        """
        Начинает сессию просмотра товара.
        
        Args:
            user_id: ID пользователя
            product_id: ID товара
            view_type: Тип просмотра
            
        Returns:
            Ключ сессии для последующего использования
        """
        session_key = f"{user_id}_{product_id}_{view_type}_{int(time.time())}"
        self._view_sessions[session_key] = {
            'user_id': user_id,
            'product_id': product_id,
            'view_type': view_type,
            'start_time': time.time(),
            'duration': 0
        }
        logger.debug(f"Started view session: {session_key}")
        return session_key
    
    def end_view_session(self, session_key: str) -> Optional[int]:
        """
        Завершает сессию просмотра и возвращает длительность.
        
        Args:
            session_key: Ключ сессии
            
        Returns:
            Длительность просмотра в секундах или None если сессия не найдена
        """
        if session_key not in self._view_sessions:
            return None
        
        session = self._view_sessions[session_key]
        duration = int(time.time() - session['start_time'])
        session['duration'] = duration
        
        # Записываем просмотр в базу данных
        data_base.add_product_view(
            user_id=session['user_id'],
            product_id=session['product_id'],
            view_type=session['view_type'],
            view_duration=duration
        )
        
        # Удаляем сессию
        del self._view_sessions[session_key]
        logger.debug(f"Ended view session: {session_key}, duration: {duration}s")
        return duration
    
    def quick_view(self, user_id: int, product_id: int, view_type: str = 'slider') -> None:
        """
        Быстрая запись просмотра без отслеживания времени.
        
        Args:
            user_id: ID пользователя
            product_id: ID товара
            view_type: Тип просмотра
        """
        data_base.add_product_view(
            user_id=user_id,
            product_id=product_id,
            view_type=view_type,
            view_duration=0
        )
        logger.debug(f"Quick view recorded: user_id={user_id}, product_id={product_id}, type={view_type}")
    
    def get_user_view_history(self, user_id: int, limit: int = 20) -> List[Dict]:
        """
        Получает историю просмотров пользователя.
        
        Args:
            user_id: ID пользователя
            limit: Максимальное количество записей
            
        Returns:
            Список просмотров
        """
        return data_base.get_user_product_views(user_id, limit)
    
    def get_user_unique_view_history(self, user_id: int, limit: int = 20) -> List[Dict]:
        """
        Получает уникальную историю просмотров пользователя (без дублей).
        Для каждого товара берется только последний просмотр.
        
        Args:
            user_id: ID пользователя
            limit: Максимальное количество записей
            
        Returns:
            Список уникальных просмотров
        """
        return data_base.get_user_unique_product_views(user_id, limit)
    
    def get_product_stats(self, product_id: int) -> Dict:
        """
        Получает статистику просмотров товара.
        
        Args:
            product_id: ID товара
            
        Returns:
            Статистика просмотров
        """
        return data_base.get_product_view_stats(product_id)
    
    def get_user_stats(self, user_id: int) -> Dict:
        """
        Получает статистику просмотров пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Статистика просмотров пользователя
        """
        return data_base.get_user_view_stats(user_id)
    
    def get_popular_products(self, limit: int = 10) -> List[Dict]:
        """
        Получает список популярных товаров.
        
        Args:
            limit: Максимальное количество товаров
            
        Returns:
            Список популярных товаров
        """
        return data_base.get_most_viewed_products(limit)
    
    def get_recent_activity(self, hours: int = 24) -> List[Dict]:
        """
        Получает недавнюю активность просмотров.
        
        Args:
            hours: Количество часов для поиска
            
        Returns:
            Список недавних просмотров
        """
        return data_base.get_recent_views(hours)
    
    def cleanup_old_data(self, days: int = 90) -> int:
        """
        Очищает старые данные о просмотрах.
        
        Args:
            days: Количество дней, после которых данные считаются старыми
            
        Returns:
            Количество удаленных записей
        """
        return data_base.delete_old_views(days)


# Глобальный экземпляр трекера просмотров
view_tracker = ViewTracker() 