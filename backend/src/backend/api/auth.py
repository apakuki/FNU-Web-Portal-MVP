import asyncio
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.auth import (
    create_access_token,
    get_current_user,
    hash_jti,
    verify_password,
)
from src.backend.config import settings
from src.backend.db.models import Session, User
from src.backend.db.schemas import (
    LoginRequest,
    LoginResponse,
    MeResponse,
    MessageResponse,
    ResetPasswordConfirmRequest,
    ResetPasswordRequest,
    UserResponse,
)
from src.backend.db.session import get_session
from src.backend.rate_limit import limiter
from src.backend.services.audit_service import write_audit_log

router = APIRouter(prefix="/auth", tags=["auth"])

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


async def _check_lockout(email: str, db: AsyncSession) -> None:
    result = await db.execute(
        select(User).where(User.email == email)
    )
    user = result.scalar_one_or_none()
    if user and user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
        if user.locked_until and user.locked_until > datetime.now(UTC):
            raise HTTPException(
                status_code=429, detail="Too many failed attempts. Try again later."
            )


async def _record_failed_attempt(email: str, db: AsyncSession) -> None:
    await db.execute(
        update(User)
        .where(User.email == email)
        .values(
            failed_login_attempts=User.failed_login_attempts + 1,
            locked_until=datetime.now(UTC) + timedelta(minutes=LOCKOUT_MINUTES),
        )
    )
    await db.commit()


async def _clear_failed_attempts(user_id: object, db: AsyncSession) -> None:
    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(failed_login_attempts=0, locked_until=None)
    )


@router.post("/login", response_model=LoginResponse)
@limiter.limit("10/minute")
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> LoginResponse:
    await _check_lockout(body.email, db)

    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        if user:
            await _record_failed_attempt(body.email, db)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account disabled")

    await _clear_failed_attempts(user.id, db)

    token, jti = create_access_token(str(user.id), user.role)
    token_hash = hash_jti(jti)

    session = Session(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes),
    )
    db.add(session)
    await db.commit()

    asyncio.create_task(
        write_audit_log(
            actor_user_id=user.id,
            action="auth.login",
            target_type="user",
            target_id=str(user.id),
            ip_address=request.client.host if request.client else None,
        )
    )

    return LoginResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> MessageResponse:
    auth = request.headers.get("Authorization", "")
    token = auth.split(" ", 1)[1]
    from src.backend.auth import decode_token

    payload = decode_token(token)
    token_hash = hash_jti(payload["jti"])

    await db.execute(
        update(Session)
        .where(Session.token_hash == token_hash)
        .values(revoked_at=datetime.now(UTC))
    )
    await db.commit()

    asyncio.create_task(
        write_audit_log(
            actor_user_id=user.id,
            action="auth.logout",
            target_type="user",
            target_id=str(user.id),
            ip_address=request.client.host if request.client else None,
        )
    )

    return MessageResponse(detail="Logged out")


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(get_current_user)) -> MeResponse:
    return MeResponse(user=UserResponse.model_validate(user))


@router.post("/reset-password", response_model=MessageResponse)
@limiter.limit("3/minute")
async def reset_password(body: ResetPasswordRequest, request: Request) -> MessageResponse:
    return MessageResponse(detail="If that email exists, a reset link has been sent.")


@router.post("/reset-password/confirm", response_model=MessageResponse)
@limiter.limit("5/minute")
async def reset_password_confirm(
    body: ResetPasswordConfirmRequest,
    request: Request,
) -> MessageResponse:
    raise HTTPException(status_code=400, detail="Invalid or expired token")
