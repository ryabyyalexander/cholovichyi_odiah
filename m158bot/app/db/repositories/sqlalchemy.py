from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .abstract import AbstractRepository


class SQLAlchemyRepository(AbstractRepository):
    """
    Реализация паттерна 'Репозиторий' для SQLAlchemy.
    """
    model = None

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_one_or_none(self, **filter_by) -> Any | None:
        stmt = select(self.model).filter_by(**filter_by)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, **filter_by) -> list[Any]:
        stmt = select(self.model).filter_by(**filter_by)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, data: dict) -> Any:
        stmt = insert(self.model).values(**data).returning(self.model)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.scalar_one()

    async def update(self, pk: Any, data: dict) -> Any:
        stmt = update(self.model).where(self.model.user_id == pk).values(**data).returning(self.model)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.scalar_one()
