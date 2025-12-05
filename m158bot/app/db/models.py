import datetime
from sqlalchemy import (
    create_engine, BigInteger, String, ForeignKey, DateTime, func, Boolean, JSON, Integer, Float
)
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Base class for all models
class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    first_name: Mapped[str] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str] = mapped_column(String(255), nullable=True)
    user_name: Mapped[str] = mapped_column(String(255), nullable=True, unique=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=True)
    
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    user_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    
    registered_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=func.now()
    )
    
    # --- Поля для фичей ---
    filters: Mapped[dict] = mapped_column(JSON, nullable=True)
    loyalty_points: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[str] = mapped_column(String(50), nullable=True, default='bronze')
    
    # Связь для реферальной системы
    referrer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.user_id'), nullable=True)

    # --- Поля для MessageManager ---
    active_msg_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    active_msg_type: Mapped[str] = mapped_column(String(50), nullable=True, default='text')


class Product(Base):
    __tablename__ = 'products'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    vendor_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_description: Mapped[str] = mapped_column(String, nullable=True)
    
    purchase_price: Mapped[float] = mapped_column(Float, nullable=False)
    sale_price: Mapped[float] = mapped_column(Float, nullable=False)
    discount: Mapped[int] = mapped_column(Integer, default=0)
    
    category: Mapped[str] = mapped_column(String(100), nullable=True)
    subcategory: Mapped[str] = mapped_column(String(100), nullable=True)
    brand: Mapped[str] = mapped_column(String(100), nullable=True)
    season: Mapped[str] = mapped_column(String(100), nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

# В будущем здесь будут и другие модели: ProductMedia, ProductVariant, Order и т.д.

async def create_tables(engine: AsyncEngine):
    """Асинхронно создает все таблицы в базе данных"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
