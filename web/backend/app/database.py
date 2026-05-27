"""
OpsBrain Web — Database Configuration

SQLite 数据库配置。
首次启动自动创建表和默认管理员账号。
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from logging_setup import get_logger

log = get_logger(__name__)

# ── Database path ──────────────────────────────────────────────────────────
DB_DIR = Path(os.environ.get("OPSBRAIN_HOME", "/var/lib/opsbrain"))
DB_PATH = DB_DIR / "opsbrain.db"
DB_URL = f"sqlite+aiosqlite:///{DB_PATH}"

engine = create_async_engine(DB_URL, echo=False, connect_args={"check_same_thread": False})
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    """创建所有表，初始化默认数据"""
    DB_DIR.mkdir(parents=True, exist_ok=True)

    from .models import User, Setting, ApiKey, ProjectConfig, AgentConfig, TopologySave, Subagent, FeishuConfig  # noqa

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    log.info("Database initialized", extra={"path": str(DB_PATH)})


async def get_session() -> AsyncSession:
    """获取数据库会话"""
    async with async_session() as session:
        yield session
