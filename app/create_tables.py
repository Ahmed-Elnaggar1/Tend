import asyncio
from sqlalchemy import text
from app.db import Base, engine
import app.models  # Crucial: this registers the models with Base!


async def main():
  async with engine.begin() as conn:
    print("Enabling pgvector extension...")
    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
    print("Creating tables in PostgreSQL...")
    await conn.run_sync(Base.metadata.create_all)
    print("Done! Tables created successfully.")


if __name__ == "__main__":
  asyncio.run(main())
