from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User
from .sqlalchemy import SQLAlchemyRepository


class UserRepository(SQLAlchemyRepository):
    model = User

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_or_create(self, user_id: int, defaults: dict = None) -> tuple[User, bool]:
        """
        Получает пользователя или создает нового, если он не существует.
        """
        instance = await self.get_one_or_none(user_id=user_id)
        if instance:
            return instance, False

        if defaults is None:
            defaults = {}
        
        create_data = {'user_id': user_id, **defaults}
        instance = await self.create(create_data)
        return instance, True

    async def update_message_info(self, user_id: int, msg_id: int | None, msg_type: str | None):
        """
        Обновляет информацию о последнем сообщении пользователя.
        """
        await self.update(user_id, {'active_msg_id': msg_id, 'active_msg_type': msg_type})
