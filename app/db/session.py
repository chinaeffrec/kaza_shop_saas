from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.engine import engine

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_session():
    async with SessionLocal() as session:
        yield session