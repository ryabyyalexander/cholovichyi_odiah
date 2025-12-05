from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


class AbstractRepository(ABC):
    """
    Абстрактный базовый класс для всех репозиториев.
    """
    model = None

    def __init__(self, session: AsyncSession):
        self.session = session

    @abstractmethod
    async def get_one_or_none(self, **filter_by) -> Any | None:
        raise NotImplementedError

    @abstractmethod
    async def get_all(self, **filter_by) -> list[Any]:
        raise NotImplementedError

    @abstractmethod
    async def create(self, data: dict) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def update(self, pk: Any, data: dict) -> Any:
        raise NotImplementedError
