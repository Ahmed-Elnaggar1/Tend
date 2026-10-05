import pytest
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings
from app.db import get_db_session
from app.main import app


@pytest.fixture(autouse=True)
async def override_db():
    """Ensure each async test gets its own isolated connection pool on its active event loop."""
    test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    test_sessionmaker = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _get_test_db():
        async with test_sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db_session] = _get_test_db
    yield
    app.dependency_overrides.clear()
    await test_engine.dispose()
