"""Digital student ID card — Part 11.

`GET /api/id-card` issues a fresh signed QR payload for the authenticated
student. The payload itself encodes only `(user_id, banner_id, expiry)` —
no PII. `GET /api/verify/{qr}` is the public verification endpoint scanned
by hand-helds; it returns only non-sensitive info (name, programme,
validity). No grades, balance, or contact info ever leak through here.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.auth import get_current_user
from src.backend.banner import get_banner_client
from src.backend.config import settings
from src.backend.db.models import ProfilePhoto, User
from src.backend.db.session import get_session
from src.backend.services.id_card_service import (
    ExpiredIdCardError,
    InvalidIdCardSignatureError,
    sign_id_card,
    verify_id_card,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["id-card"])


class IdCardOut(BaseModel):
    user_id: str
    banner_id: str
    full_name: str
    qr_payload: str
    expires_at: datetime
    verify_url: str
    has_photo: bool


class VerifyOut(BaseModel):
    valid: bool
    full_name: str | None = None
    banner_id: str | None = None
    programme: str | None = None
    photo_url: str | None = None
    expires_at: datetime | None = None
    reason: str | None = None


@router.get("/api/id-card", response_model=IdCardOut)
async def get_my_id_card(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> IdCardOut:
    if user.role != "student":
        raise HTTPException(status_code=403, detail="ID cards are issued to students")
    if not user.banner_id:
        raise HTTPException(status_code=400, detail="No Banner ID linked to account")

    qr, expires_at = sign_id_card(user_id=user.id, banner_id=user.banner_id)
    has_photo = await db.scalar(
        select(ProfilePhoto.id).where(ProfilePhoto.user_id == user.id)
    )
    return IdCardOut(
        user_id=str(user.id),
        banner_id=user.banner_id,
        full_name=user.full_name,
        qr_payload=qr,
        expires_at=expires_at,
        verify_url=f"{settings.public_app_url.rstrip('/')}/verify/{qr}",
        has_photo=has_photo is not None,
    )


@router.get("/api/verify/{qr_payload}", response_model=VerifyOut)
async def verify_id_card_endpoint(
    qr_payload: str,
    db: AsyncSession = Depends(get_session),
) -> VerifyOut:
    """Public endpoint — no auth. Returns only public-safe info."""
    try:
        payload = verify_id_card(qr_payload)
    except ExpiredIdCardError:
        return VerifyOut(valid=False, reason="ID card has expired")
    except InvalidIdCardSignatureError:
        return VerifyOut(valid=False, reason="Invalid or tampered QR code")

    try:
        user_uuid = uuid.UUID(payload["u"])
    except (KeyError, ValueError):
        return VerifyOut(valid=False, reason="Invalid payload")

    user = await db.scalar(select(User).where(User.id == user_uuid))
    if user is None or not user.is_active:
        return VerifyOut(valid=False, reason="No active student record")

    programme = None
    if user.banner_id:
        try:
            banner = get_banner_client()
            student = await banner.get_student(user.banner_id)
            programme = getattr(student, "programme_name", None) or getattr(
                student, "programme_code", None
            )
        except Exception:
            logger.exception("Banner lookup failed for verify(%s)", user.banner_id)

    has_photo = await db.scalar(
        select(ProfilePhoto.id).where(ProfilePhoto.user_id == user.id)
    )
    photo_url = (
        f"{settings.public_app_url.rstrip('/')}/api/verify/{qr_payload}/photo"
        if has_photo
        else None
    )

    expires_at = datetime.fromtimestamp(payload["e"], tz=UTC)
    return VerifyOut(
        valid=True,
        full_name=user.full_name,
        banner_id=user.banner_id,
        programme=programme,
        photo_url=photo_url,
        expires_at=expires_at,
    )


@router.get("/api/verify/{qr_payload}/photo")
async def verify_photo(
    qr_payload: str,
    db: AsyncSession = Depends(get_session),
) -> Response:
    """Public photo serve — only returns bytes if the QR signature is valid."""

    try:
        payload = verify_id_card(qr_payload)
    except (ExpiredIdCardError, InvalidIdCardSignatureError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        user_uuid = uuid.UUID(payload["u"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Invalid payload") from exc

    photo = await db.scalar(
        select(ProfilePhoto).where(ProfilePhoto.user_id == user_uuid)
    )
    if photo is None:
        raise HTTPException(status_code=404, detail="No photo on file")

    return Response(
        content=photo.image_data,
        media_type=photo.mime_type,
        headers={"Cache-Control": "public, max-age=300"},
    )
