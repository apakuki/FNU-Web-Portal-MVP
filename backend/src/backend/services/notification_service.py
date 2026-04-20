"""Stub notification service — logs notifications in dev, queues in production.

In development, notifications are logged to console and stored in the
notifications table. In production, this will integrate with SMTP and SMS providers.
"""

import logging

from src.backend.db.models import Notification
from src.backend.db.session import async_session_factory

logger = logging.getLogger(__name__)


async def send_notification(
    *,
    channel: str = "email",
    recipient_email: str | None = None,
    recipient_phone: str | None = None,
    recipient_user_id: object | None = None,
    subject: str | None = None,
    body: str,
    template_code: str | None = None,
) -> None:
    logger.info(
        "Notification [%s] to=%s subject=%s",
        channel,
        recipient_email or recipient_phone or str(recipient_user_id),
        subject,
    )

    async with async_session_factory() as session:
        notification = Notification(
            recipient_user_id=recipient_user_id,
            recipient_email=recipient_email,
            recipient_phone=recipient_phone,
            channel=channel,
            template_code=template_code,
            subject=subject,
            body=body,
            status="sent",
        )
        session.add(notification)
        await session.commit()
