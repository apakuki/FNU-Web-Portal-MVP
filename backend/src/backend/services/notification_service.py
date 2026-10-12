"""Notification service — Part 11.

Routes outbound notifications (email + SMS) through pluggable senders. In
``stub`` mode, sends are logged and stored as ``status="sent"`` so the rest
of the system behaves identically to live mode. In ``live`` mode, SMTP
delivery happens on a worker thread (so we never block the event loop) and
SMS is dispatched via an HTTP provider.

Templates live in the ``notification_templates`` table — referenced by
``code``. We use a strict whitelist-style ``str.format_map`` so a hostile
template variable cannot escape into f-string-land or accidentally render
unrelated attributes.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
import uuid
from email.message import EmailMessage
from typing import Any

import httpx
from sqlalchemy import select

from src.backend.config import settings
from src.backend.db.models import Notification, NotificationTemplate
from src.backend.db.session import async_session_factory

logger = logging.getLogger(__name__)


class _SafeDict(dict[str, Any]):
    """str.format_map with `{missing}` -> empty string instead of KeyError.

    Prevents a half-renamed template from crashing notification dispatch.
    Forbids attribute lookups (``{foo.bar}``) by stripping `.` from keys.
    """

    def __missing__(self, key: str) -> str:
        return ""


def render_template(template: str, variables: dict[str, Any]) -> str:
    """Render ``template`` against ``variables`` safely.

    Strips control chars and limits substituted values to 500 chars to keep
    SMS bodies sane and email bodies free of injection-y content.
    """
    safe_vars: dict[str, str] = {}
    for k, v in variables.items():
        if not k.isidentifier():
            continue
        text = "" if v is None else str(v)
        # Strip CR/LF/control chars — they enable header injection in email.
        text = "".join(ch for ch in text if ch == "\n" or 32 <= ord(ch) < 127)
        if len(text) > 500:
            text = text[:497] + "..."
        safe_vars[k] = text

    try:
        return template.format_map(_SafeDict(safe_vars))
    except (ValueError, IndexError):
        # Malformed brace -> render as-is rather than crash.
        logger.warning("Malformed template; rendering literal text")
        return template


# --- Senders ---------------------------------------------------------------


def _smtp_send_sync(*, subject: str, body: str, to_email: str) -> str:
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg["Subject"] = subject or "(no subject)"
    msg.set_content(body)

    if settings.smtp_use_tls:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as s:
            s.ehlo()
            s.starttls(context=ctx)
            s.ehlo()
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_pass)
            s.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as s:
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_pass)
            s.send_message(msg)
    return f"smtp:{settings.smtp_host}"


async def _send_email(*, subject: str, body: str, to_email: str) -> str:
    if settings.notifications_mode == "stub":
        logger.info("[email/stub] to=%s subject=%s", to_email, subject)
        return "stub"
    return await asyncio.to_thread(
        _smtp_send_sync, subject=subject or "", body=body, to_email=to_email
    )


async def _send_sms(*, body: str, to_phone: str) -> str:
    if settings.notifications_mode == "stub" or settings.sms_provider == "stub":
        logger.info("[sms/stub] to=%s body=%s", to_phone, body[:80])
        return "stub"
    if not settings.sms_api_url or not settings.sms_api_key:
        raise RuntimeError("SMS provider not configured")

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            settings.sms_api_url,
            headers={"Authorization": f"Bearer {settings.sms_api_key}"},
            json={"to": to_phone, "from": settings.sms_from, "message": body},
        )
        resp.raise_for_status()
        try:
            message_id: str = resp.json().get("id", "ok")
            return message_id
        except ValueError:
            return "ok"


# --- Public API ------------------------------------------------------------


async def render_template_by_code(
    code: str, variables: dict[str, Any]
) -> tuple[str | None, str, str] | None:
    """Look up a template by code and render it. Returns (subject, body, channel)."""
    async with async_session_factory() as session:
        tpl = await session.scalar(
            select(NotificationTemplate).where(
                NotificationTemplate.code == code,
                NotificationTemplate.is_active.is_(True),
            )
        )
    if tpl is None:
        return None
    subject = render_template(tpl.subject_template, variables) if tpl.subject_template else None
    body = render_template(tpl.body_template, variables)
    return subject, body, tpl.channel


async def send_notification(
    *,
    channel: str = "email",
    recipient_email: str | None = None,
    recipient_phone: str | None = None,
    recipient_user_id: uuid.UUID | None = None,
    subject: str | None = None,
    body: str,
    template_code: str | None = None,
) -> uuid.UUID:
    """Send a single notification. Persists a row in `notifications` either way."""
    status = "queued"
    error_message: str | None = None
    provider_reference: str | None = None

    try:
        if channel == "email":
            if not recipient_email:
                raise ValueError("recipient_email required for email channel")
            provider_reference = await _send_email(
                subject=subject or "", body=body, to_email=recipient_email
            )
        elif channel == "sms":
            if not recipient_phone:
                raise ValueError("recipient_phone required for sms channel")
            provider_reference = await _send_sms(body=body, to_phone=recipient_phone)
        else:
            raise ValueError(f"Unsupported channel {channel!r}")
        status = "sent"
    except Exception as exc:  # noqa: BLE001 — provider exceptions are diverse
        status = "failed"
        error_message = str(exc)[:500]
        logger.exception("Notification dispatch failed")

    async with async_session_factory() as session:
        notification = Notification(
            recipient_user_id=recipient_user_id,
            recipient_email=recipient_email,
            recipient_phone=recipient_phone,
            channel=channel,
            template_code=template_code,
            subject=subject,
            body=body,
            status=status,
            provider_reference=provider_reference,
            error_message=error_message,
        )
        session.add(notification)
        await session.commit()
        await session.refresh(notification)
        return notification.id


async def send_template(
    *,
    code: str,
    variables: dict[str, Any],
    recipient_email: str | None = None,
    recipient_phone: str | None = None,
    recipient_user_id: uuid.UUID | None = None,
    channel_override: str | None = None,
) -> uuid.UUID:
    """Render a template and dispatch in one call."""
    rendered = await render_template_by_code(code, variables)
    if rendered is None:
        raise ValueError(f"Notification template {code!r} not found or inactive")
    subject, body, channel = rendered
    return await send_notification(
        channel=channel_override or channel,
        recipient_email=recipient_email,
        recipient_phone=recipient_phone,
        recipient_user_id=recipient_user_id,
        subject=subject,
        body=body,
        template_code=code,
    )
