"""Настройка асинхронного движка и сессий SQLAlchemy."""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Базовый класс для всех ORM-моделей."""


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Зависимость FastAPI: отдаёт сессию БД и закрывает её после запроса."""
    async with SessionLocal() as session:
        yield session
