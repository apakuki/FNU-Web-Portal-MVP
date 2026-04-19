import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.config import settings
from src.backend.db.models import Session, User
from src.backend.db.session import get_session

security = HTTPBearer()

VALID_ROLES = {"student", "staff", "finance", "manager", "lecturer", "vc", "admin"}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(user_id: str, role: str) -> tuple[str, str]:
    jti = str(uuid.uuid4())
    payload = {
        "sub": user_id,
        "role": role,
        "jti": jti,
        "exp": datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes),
        "iat": datetime.now(UTC),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, jti


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def hash_jti(jti: str) -> str:
    return hashlib.sha256(jti.encode()).hexdigest()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_session),
) -> User:
    payload = decode_token(credentials.credentials)

    token_hash = hash_jti(payload["jti"])
    result = await db.execute(
        select(Session).where(
            Session.token_hash == token_hash,
            Session.revoked_at.is_(None),
            Session.expires_at > datetime.now(UTC),
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=401, detail="Session invalid or expired")

    result = await db.execute(select(User).where(User.id == uuid.UUID(payload["sub"])))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return user


def require_role(*roles: str):
    async def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return role_checker


async def get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> User | None:
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return None
    try:
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=auth.split(" ", 1)[1]
        )
        return await get_current_user(credentials, db)
    except HTTPException:
        return None
