"""Profile + photo upload API — Part 11.

Profile edit is scoped to the authenticated user (users can only see and
update their own). Photo upload validates magic bytes, strips EXIF, and
resizes server-side before persisting. The photo is served via an
auth-gated endpoint — the raw bytes never sit on disk outside the DB.
"""

from __future__ import annotations

import io
import logging
import re
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from PIL import Image, ImageOps
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.auth import get_current_user, require_role
from src.backend.config import settings
from src.backend.db.models import ProfilePhoto, StudentProfile, User
from src.backend.db.session import get_session
from src.backend.services.audit_service import write_audit_log

logger = logging.getLogger(__name__)

router = APIRouter(tags=["profile"])


# --- Schemas ---


class ProfileOut(BaseModel):
    user_id: str
    full_name: str
    email: str
    phone: str | None = None
    banner_id: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    country: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    emergency_contact_relationship: str | None = None
    has_photo: bool = False


class ProfileUpdateRequest(BaseModel):
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    address_line1: str | None = Field(default=None, max_length=200)
    address_line2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=80)
    emergency_contact_name: str | None = Field(default=None, max_length=120)
    emergency_contact_phone: str | None = Field(default=None, max_length=40)
    emergency_contact_relationship: str | None = Field(default=None, max_length=60)


# --- Helpers ---


_PHONE_RE = re.compile(r"^[+0-9 ()\-]{5,40}$")

# JPEG, PNG, WebP magic bytes.
_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_WEBP_MAGIC_PREFIX = b"RIFF"
_WEBP_MAGIC_SUFFIX = b"WEBP"


def _detect_image_mime(data: bytes) -> str | None:
    if data.startswith(_JPEG_MAGIC):
        return "image/jpeg"
    if data.startswith(_PNG_MAGIC):
        return "image/png"
    if (
        len(data) >= 12
        and data[:4] == _WEBP_MAGIC_PREFIX
        and data[8:12] == _WEBP_MAGIC_SUFFIX
    ):
        return "image/webp"
    return None


async def _get_or_create_profile(
    db: AsyncSession, user_id: Any
) -> StudentProfile:
    profile = await db.scalar(
        select(StudentProfile).where(StudentProfile.user_id == user_id)
    )
    if profile is None:
        profile = StudentProfile(user_id=user_id)
        db.add(profile)
        await db.flush()
    return profile


def process_profile_photo(
    raw: bytes,
    *,
    max_bytes: int = settings.profile_photo_max_bytes,
    target_size: int = settings.profile_photo_target_size,
) -> tuple[bytes, str]:
    """Validate magic bytes, strip EXIF, resize to a square. Returns (bytes, mime)."""
    if len(raw) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Photo exceeds maximum size of {max_bytes // 1024} KB",
        )
    mime = _detect_image_mime(raw)
    if mime is None:
        raise HTTPException(status_code=400, detail="Only JPEG/PNG/WebP images are accepted")

    try:
        img = Image.open(io.BytesIO(raw))
        # Apply EXIF orientation THEN drop EXIF on save.
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        # Centre-crop to a square, then resize.
        short_side = min(img.size)
        left = (img.size[0] - short_side) // 2
        top = (img.size[1] - short_side) // 2
        img = img.crop((left, top, left + short_side, top + short_side))
        img = img.resize((target_size, target_size), Image.Resampling.LANCZOS)
    except Exception as exc:  # noqa: BLE001 — Pillow raises a mix of errors
        raise HTTPException(status_code=400, detail="Unable to process image") from exc

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue(), "image/jpeg"


async def _profile_to_out(user: User, profile: StudentProfile | None, db: AsyncSession) -> ProfileOut:
    has_photo = await db.scalar(
        select(ProfilePhoto.id).where(ProfilePhoto.user_id == user.id)
    )
    return ProfileOut(
        user_id=str(user.id),
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        banner_id=user.banner_id,
        address_line1=profile.address_line1 if profile else None,
        address_line2=profile.address_line2 if profile else None,
        city=profile.city if profile else None,
        country=profile.country if profile else None,
        emergency_contact_name=profile.emergency_contact_name if profile else None,
        emergency_contact_phone=profile.emergency_contact_phone if profile else None,
        emergency_contact_relationship=profile.emergency_contact_relationship if profile else None,
        has_photo=has_photo is not None,
    )


# --- Routes ---


@router.get("/api/profile", response_model=ProfileOut)
async def get_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> ProfileOut:
    profile = await db.scalar(
        select(StudentProfile).where(StudentProfile.user_id == user.id)
    )
    return await _profile_to_out(user, profile, db)


@router.put("/api/profile", response_model=ProfileOut)
async def update_profile(
    request: Request,
    body: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> ProfileOut:
    if body.phone is not None and body.phone != "" and not _PHONE_RE.match(body.phone):
        raise HTTPException(status_code=400, detail="Invalid phone number")
    if body.emergency_contact_phone is not None and body.emergency_contact_phone != "" \
            and not _PHONE_RE.match(body.emergency_contact_phone):
        raise HTTPException(status_code=400, detail="Invalid emergency contact phone")

    profile = await _get_or_create_profile(db, user.id)
    before = {
        "email": user.email,
        "phone": user.phone,
        "address_line1": profile.address_line1,
        "city": profile.city,
    }

    if body.phone is not None:
        user.phone = body.phone or None
    if body.email is not None and body.email != user.email:
        # Enforce email uniqueness
        existing = await db.scalar(select(User).where(User.email == body.email))
        if existing and existing.id != user.id:
            raise HTTPException(status_code=400, detail="Email already in use")
        user.email = body.email

    for field in (
        "address_line1",
        "address_line2",
        "city",
        "country",
        "emergency_contact_name",
        "emergency_contact_phone",
        "emergency_contact_relationship",
    ):
        value = getattr(body, field)
        if value is not None:
            setattr(profile, field, value or None)

    await db.commit()
    await db.refresh(user)
    await db.refresh(profile)

    await write_audit_log(
        actor_user_id=user.id,
        action="profile.update",
        target_type="user",
        target_id=str(user.id),
        before=before,
        after={
            "email": user.email,
            "phone": user.phone,
            "address_line1": profile.address_line1,
            "city": profile.city,
        },
        ip_address=request.client.host if request.client else None,
    )
    return await _profile_to_out(user, profile, db)


@router.post("/api/profile/photo", response_model=ProfileOut)
async def upload_profile_photo(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> ProfileOut:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty upload")

    processed, mime = process_profile_photo(raw)

    photo = await db.scalar(
        select(ProfilePhoto).where(ProfilePhoto.user_id == user.id)
    )
    if photo is None:
        photo = ProfilePhoto(
            user_id=user.id,
            mime_type=mime,
            size_bytes=len(processed),
            image_data=processed,
        )
        db.add(photo)
    else:
        photo.mime_type = mime
        photo.size_bytes = len(processed)
        photo.image_data = processed

    await db.commit()

    await write_audit_log(
        actor_user_id=user.id,
        action="profile.photo.upload",
        target_type="user",
        target_id=str(user.id),
        after={"mime_type": mime, "size_bytes": len(processed)},
        ip_address=request.client.host if request.client else None,
    )

    profile = await db.scalar(
        select(StudentProfile).where(StudentProfile.user_id == user.id)
    )
    return await _profile_to_out(user, profile, db)


@router.get("/api/profile/photo/me")
async def get_my_photo(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> Response:
    photo = await db.scalar(
        select(ProfilePhoto).where(ProfilePhoto.user_id == user.id)
    )
    if photo is None:
        raise HTTPException(status_code=404, detail="No photo uploaded")
    return Response(
        content=photo.image_data,
        media_type=photo.mime_type,
        headers={"Cache-Control": "private, max-age=60"},
    )


@router.get("/api/admin/students/{user_id}/photo")
async def get_student_photo(
    user_id: str,
    _staff: User = Depends(require_role("admin", "staff", "lecturer")),
    db: AsyncSession = Depends(get_session),
) -> Response:
    """Staff view — enables showing student photos in admin screens."""
    photo = await db.scalar(
        select(ProfilePhoto).where(ProfilePhoto.user_id == user_id)
    )
    if photo is None:
        raise HTTPException(status_code=404, detail="No photo on file")
    return Response(
        content=photo.image_data,
        media_type=photo.mime_type,
        headers={"Cache-Control": "private, max-age=60"},
    )
