import sqlite3
from typing import Tuple, Any, List
from utils import logger

class BaseRepository:
    def __init__(self, db_name: str):
        self.db_name = f"{db_name}.db"
        self._db = None

    def _inject_db_instance(self, db_instance):
        """Получает экземпляр главного класса Database для доступа к другим репозиториям."""
        self._db = db_instance

    def _execute_query(self, query: str, params: Tuple[Any, ...] = ()) -> sqlite3.Cursor:
        """Выполняет SQL-запрос с параметрами."""
        try:
            with sqlite3.connect(self.db_name) as db:
                cursor = db.cursor()
                cursor.execute(query, params)
                db.commit()
                return cursor
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            raise

    def _execute_query_many(self, query: str, params: List[Tuple[Any, ...]]) -> None:
        """Выполняет SQL-запрос с несколькими наборами параметров."""
        try:
            with sqlite3.connect(self.db_name) as db:
                cursor = db.cursor()
                cursor.executemany(query, params)
                db.commit()
        except sqlite3.Error as e:
            logger.error(f"Database error (executemany): {e}")
            raise
