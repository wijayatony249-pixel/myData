"""
Manajemen Koneksi Basis Data Master myData.
Mendukung PostgreSQL (asyncpg) untuk produksi klaster 10 node,
serta SQLite lokal mandiri untuk pengujian tanpa ketergantungan server eksternal.
"""

from typing import AsyncGenerator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from common.config import DATABASE_URL
from master.models import Base

is_postgres = "postgresql" in DATABASE_URL

if is_postgres:
    # Mode Produksi Multi-Node (PostgreSQL + asyncpg)
    async_engine = create_async_engine(
        DATABASE_URL,
        pool_size=20,
        max_overflow=10,
        echo=False
    )
    AsyncSessionLocal = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False
    )
    
    async def init_db():
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
    async def get_db() -> AsyncGenerator[AsyncSession, None]:
        async with AsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
else:
    # Mode Lokal / Dev Mandiri (SQLite Cepat & Ringan)
    sync_url = DATABASE_URL.replace("+aiosqlite", "")
    sync_engine = create_engine(
        sync_url,
        connect_args={"check_same_thread": False},
        echo=False
    )
    SyncSessionLocal = sessionmaker(bind=sync_engine, autoflush=False, expire_on_commit=False)
    
    class AsyncSessionWrapper:
        """Wrapper asinkron untuk session sinkron SQLite."""
        def __init__(self, session):
            self._s = session

        async def execute(self, stmt):
            return self._s.execute(stmt)

        def add(self, instance):
            self._s.add(instance)

        async def delete(self, instance):
            self._s.delete(instance)

        async def commit(self):
            self._s.commit()

        async def flush(self):
            self._s.flush()

        async def rollback(self):
            self._s.rollback()

        async def close(self):
            self._s.close()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            if exc_type:
                self._s.rollback()
            else:
                self._s.commit()
            self._s.close()

    def AsyncSessionLocal():
        return AsyncSessionWrapper(SyncSessionLocal())

    async def init_db():
        Base.metadata.create_all(sync_engine)

    async def get_db():
        session = AsyncSessionLocal()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
