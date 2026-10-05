from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,
)
sessionmaker = async_sessionmaker(bind =engine, 
class_=AsyncSession,
 expire_on_commit=False,
 autoflush=False,
 )

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with sessionmaker() as session:
        yield session

class Base(DeclarativeBase):
    pass
