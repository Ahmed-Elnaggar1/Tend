from collections.abc import AsyncGenerator
import os 
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_async_engine(
    DATABASE_URL,
    echo=True,
)
sessionmaker = async_sessionmaker(bind =engine, 
class_=AsyncSession,
 expire_on_commit=False,
 autoflush=False,
 )

async def get_db_session()->AsyncGenerator[AsyncSession,None]:
    async with sessionmaker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

class Base(DeclarativeBase):
    pass
