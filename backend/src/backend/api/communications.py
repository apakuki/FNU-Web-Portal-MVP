"""Admin communications — notification templates + batch send (Part 11).

Admins manage templates and fire off batch sends (email or SMS) to a
filtered student cohort. Every batch write lands in the audit log with a
hash of the rendered body so we can prove what was sent without keeping
a full copy of every interpolated variant.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.auth import require_role
from src.backend.db.models import Notification, NotificationTemplate, User
from src.backend.db.session import get_session
from src.backend.services.audit_service import write_audit_log
from src.backend.services.notification_service import (
    render_template_by_code,
    send_notification,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["communications"])


# --- Schemas ---------------------------------------------------------------


class TemplateOut(BaseModel):
    id: str
    code: str
    name: str
    channel: str
    subject_template: str | None
    body_template: str
    is_active: bool
    updated_at: datetime


class TemplateUpsert(BaseModel):
    code: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9_.]+$")
    name: str = Field(min_length=1, max_length=200)
    channel: str = Field(pattern=r"^(email|sms)$")
    subject_template: str | None = Field(default=None, max_length=200)
    body_template: str = Field(min_length=1, max_length=8000)
    is_active: bool = True


class BatchSendRequest(BaseModel):
    template_code: str = Field(min_length=1)
    role: str | None = Field(
        default="student", pattern=r"^(student|staff|lecturer|finance|manager|vc|admin)$"
    )
    banner_id_prefix: str | None = Field(default=None, max_length=10)
    variables: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False


class BatchSendResponse(BaseModel):
    template_code: str
    channel: str
    recipient_count: int
    sent: int
    failed: int
    dry_run: bool
    content_hash: str


class NotificationRow(BaseModel):
    id: str
    channel: str
    subject: str | None
    recipient_email: str | None
    recipient_phone: str | None
    status: str
    template_code: str | None
    queued_at: datetime
    sent_at: datetime | None
    error_message: str | None


# --- Template CRUD ---------------------------------------------------------


@router.get("/api/admin/notification-templates", response_model=list[TemplateOut])
async def list_templates(
    _admin: User = Depends(require_role("admin", "staff")),
    db: AsyncSession = Depends(get_session),
) -> list[TemplateOut]:
    rows = (
        await db.scalars(select(NotificationTemplate).order_by(NotificationTemplate.code))
    ).all()
    return [
        TemplateOut(
            id=str(r.id),
            code=r.code,
            name=r.name,
            channel=r.channel,
            subject_template=r.subject_template,
            body_template=r.body_template,
            is_active=r.is_active,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


@router.put("/api/admin/notification-templates/{code}", response_model=TemplateOut)
async def upsert_template(
    code: str,
    body: TemplateUpsert,
    request: Request,
    admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_session),
) -> TemplateOut:
    if code != body.code:
        raise HTTPException(status_code=400, detail="URL code and body code must match")

    existing = await db.scalar(
        select(NotificationTemplate).where(NotificationTemplate.code == code)
    )
    if existing is None:
        tpl = NotificationTemplate(
            code=body.code,
            name=body.name,
            channel=body.channel,
            subject_template=body.subject_template,
            body_template=body.body_template,
            is_active=body.is_active,
        )
        db.add(tpl)
        action = "notification_template.create"
        before = None
    else:
        tpl = existing
        before = {
            "name": tpl.name,
            "channel": tpl.channel,
            "subject_template": tpl.subject_template,
            "body_template": tpl.body_template,
            "is_active": tpl.is_active,
        }
        tpl.name = body.name
        tpl.channel = body.channel
        tpl.subject_template = body.subject_template
        tpl.body_template = body.body_template
        tpl.is_active = body.is_active
        action = "notification_template.update"

    await db.commit()
    await db.refresh(tpl)

    await write_audit_log(
        actor_user_id=admin.id,
        action=action,
        target_type="notification_template",
        target_id=tpl.code,
        before=before,
        after={
            "name": tpl.name,
            "channel": tpl.channel,
            "is_active": tpl.is_active,
        },
        ip_address=request.client.host if request.client else None,
    )

    return TemplateOut(
        id=str(tpl.id),
        code=tpl.code,
        name=tpl.name,
        channel=tpl.channel,
        subject_template=tpl.subject_template,
        body_template=tpl.body_template,
        is_active=tpl.is_active,
        updated_at=tpl.updated_at,
    )


# --- Batch send ------------------------------------------------------------


@router.post("/api/admin/communications/batch", response_model=BatchSendResponse)
async def batch_send(
    body: BatchSendRequest,
    request: Request,
    admin: User = Depends(require_role("admin", "staff")),
    db: AsyncSession = Depends(get_session),
) -> BatchSendResponse:
    rendered = await render_template_by_code(body.template_code, body.variables)
    if rendered is None:
        raise HTTPException(status_code=404, detail="Template not found or inactive")
    subject, tpl_body, channel = rendered

    content_hash = hashlib.sha256(
        f"{subject or ''}\n---\n{tpl_body}".encode()
    ).hexdigest()

    q = select(User).where(User.is_active.is_(True))
    if body.role:
        q = q.where(User.role == body.role)
    if body.banner_id_prefix:
        q = q.where(User.banner_id.like(f"{body.banner_id_prefix}%"))

    recipients = (await db.scalars(q)).all()
    recipient_count = len(recipients)

    if body.dry_run:
        await write_audit_log(
            actor_user_id=admin.id,
            action="communications.batch.preview",
            target_type="template",
            target_id=body.template_code,
            after={"recipient_count": recipient_count, "content_hash": content_hash},
            ip_address=request.client.host if request.client else None,
        )
        return BatchSendResponse(
            template_code=body.template_code,
            channel=channel,
            recipient_count=recipient_count,
            sent=0,
            failed=0,
            dry_run=True,
            content_hash=content_hash,
        )

    sent = 0
    failed = 0
    for r in recipients:
        try:
            if channel == "email" and not r.email:
                failed += 1
                continue
            if channel == "sms" and not r.phone:
                failed += 1
                continue
            await send_notification(
                channel=channel,
                recipient_email=r.email if channel == "email" else None,
                recipient_phone=r.phone if channel == "sms" else None,
                recipient_user_id=r.id,
                subject=subject,
                body=tpl_body,
                template_code=body.template_code,
            )
            sent += 1
        except Exception:
            logger.exception("batch send failed for user %s", r.id)
            failed += 1

    await write_audit_log(
        actor_user_id=admin.id,
        action="communications.batch.send",
        target_type="template",
        target_id=body.template_code,
        after={
            "recipient_count": recipient_count,
            "sent": sent,
            "failed": failed,
            "content_hash": content_hash,
            "role": body.role,
            "banner_id_prefix": body.banner_id_prefix,
        },
        ip_address=request.client.host if request.client else None,
    )

    return BatchSendResponse(
        template_code=body.template_code,
        channel=channel,
        recipient_count=recipient_count,
        sent=sent,
        failed=failed,
        dry_run=False,
        content_hash=content_hash,
    )


@router.get("/api/admin/notifications", response_model=list[NotificationRow])
async def list_notifications(
    status: str | None = None,
    limit: int = 50,
    _admin: User = Depends(require_role("admin", "staff")),
    db: AsyncSession = Depends(get_session),
) -> list[NotificationRow]:
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be 1..500")

    q = select(Notification).order_by(Notification.queued_at.desc()).limit(limit)
    if status:
        q = q.where(Notification.status == status)

    rows = (await db.scalars(q)).all()
    return [
        NotificationRow(
            id=str(r.id),
            channel=r.channel,
            subject=r.subject,
            recipient_email=r.recipient_email,
            recipient_phone=r.recipient_phone,
            status=r.status,
            template_code=r.template_code,
            queued_at=r.queued_at,
            sent_at=r.sent_at,
            error_message=r.error_message,
        )
        for r in rows
    ]


@router.get("/api/admin/notifications/stats")
async def notification_stats(
    _admin: User = Depends(require_role("admin", "staff")),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    since = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    totals = (
        await db.execute(
            select(Notification.status, func.count(Notification.id))
            .where(Notification.queued_at >= since)
            .group_by(Notification.status)
        )
    ).all()
    return {"since": since.isoformat(), "by_status": {s: c for s, c in totals}}
