from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

SQLALCHEMY_DATABASE_URL = "postgresql+asyncpg://heyroute_app:heyroute-db-123@localhost/heyroute"
engine = create_async_engine(SQLALCHEMY_DATABASE_URL, echo=True)
SessionLocal = async_sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

async def get_db():
    async with SessionLocal() as session:
        yield session

