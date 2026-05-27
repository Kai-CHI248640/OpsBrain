"""
OpsBrain Web — Authentication

JWT 认证 + 密码哈希。首次启动时自动创建默认 admin 账号。
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional

import jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from logging_setup import get_logger
from .database import get_session, async_session
from .models import User

log = get_logger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("OPSBRAIN_JWT_SECRET", "opsbrain-dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

security = HTTPBearer(auto_error=False)


# ── Password Hashing ───────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


# ── JWT ────────────────────────────────────────────────────────────────────

def create_access_token(user_id: str, username: str) -> str:
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "username": username,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> User:
    """从 JWT token 获取当前用户"""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or disabled")

    return user


# ── First-run setup ────────────────────────────────────────────────────────

async def ensure_admin_exists() -> bool:
    """检查并确保存在至少一个 admin 用户"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.role == "admin", User.is_active == True)
        )
        admin = result.scalar_one_or_none()

    if admin:
        return False  # 已有管理员
    return True  # 尚无管理员，需要初始化
